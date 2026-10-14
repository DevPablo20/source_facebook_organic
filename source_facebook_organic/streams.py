"""Streams do conector. Toda stream derivada de post opera dentro de uma janela de dias."""

from __future__ import annotations

import json
from abc import ABC
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional

from airbyte_cdk.models import SyncMode
from airbyte_cdk.sources.streams import IncrementalMixin, Stream

from .api import GraphAPI, GraphAPIError

PAGE_INSIGHTS_RETENTION_DAYS = 730      # ~2 anos de retenção da plataforma
PAGE_INSIGHTS_CHUNK_DAYS = 90           # a API recusa janelas longas em period=day
POST_FIELDS = (
    "id,created_time,updated_time,message,permalink_url,status_type,"
    "is_published,is_hidden,is_expired,full_picture"
)
COUNTER_FIELDS = (
    "id,created_time,shares,"
    "reactions.summary(total_count).limit(0),"
    "comments.summary(total_count).limit(0)"
)
COMMENT_FIELDS = (
    "id,created_time,message,like_count,comment_count,parent,"
    "permalink_url,is_hidden,can_hide,attachment"
)

DEFAULT_PAGE_METRICS = [
    "page_media_view", "page_total_media_view_unique", "page_post_engagements",
    "page_posts_impressions_organic", "page_follows", "page_daily_follows",
    "page_daily_follows_unique", "page_daily_unfollows_unique",
    "page_lifetime_engaged_followers_unique", "page_fan_adds_by_paid_non_paid_unique",
    "page_views_total", "page_total_actions", "page_actions_post_reactions_total",
    "page_actions_post_reactions_like_total", "page_video_views", "page_video_views_organic",
    "page_video_views_paid", "page_video_view_time", "page_video_complete_views_30s",
]
DEFAULT_POST_METRICS = [
    "post_media_view", "post_total_media_view_unique", "post_clicks", "post_clicks_by_type",
    "post_reactions_by_type_total", "post_reactions_like_total", "post_reactions_love_total",
    "post_reactions_wow_total", "post_reactions_haha_total", "post_reactions_sorry_total",
    "post_reactions_anger_total", "post_activity_by_action_type", "post_video_views",
    "post_video_views_organic", "post_video_views_paid", "post_video_views_15s",
    "post_video_avg_time_watched", "post_video_complete_views_30s", "post_video_view_time",
    "post_video_view_time_organic", "post_video_views_by_distribution_type",
]
DEFAULT_REEL_METRICS = [
    "blue_reels_play_count", "fb_reels_total_plays", "fb_reels_replay_count",
    "post_video_avg_time_watched", "post_video_view_time", "post_video_social_actions",
    "post_video_retention_graph",
]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _to_unix(moment: datetime) -> int:
    return int(moment.timestamp())


def _value_pair(value: Any) -> Dict[str, Any]:
    """Métrica escalar vira número; estrutura aninhada vira JSON — nunca os dois."""
    if isinstance(value, bool):
        return {"value_numeric": None, "value_json": json.dumps(value)}
    if isinstance(value, (int, float)):
        return {"value_numeric": value, "value_json": None}
    if value in (None, {}, []):
        return {"value_numeric": None, "value_json": None}
    return {"value_numeric": None, "value_json": json.dumps(value, ensure_ascii=False)}


def _content_type(permalink: Optional[str]) -> Dict[str, Optional[str]]:
    """Reel é post: o permalink carrega o id do reel e identifica o tipo."""
    if permalink and "/reel/" in permalink:
        reel_id = permalink.rstrip("/").rsplit("/", 1)[-1]
        return {"content_type": "reel", "reel_id": reel_id or None}
    return {"content_type": "post", "reel_id": None}


class FacebookStream(Stream, ABC):
    def __init__(self, api: GraphAPI, config: Mapping[str, Any]):
        self.api = api
        self.config = config
        self.page_id = str(config["page_id"])
        self.start_date = datetime.fromisoformat(str(config["start_date"])).replace(tzinfo=timezone.utc)
        self.lookback_days = int(config.get("lookback_window_days", 28))
        self.comment_window_days = int(config.get("comment_window_days", 90))
        self.include_replies = bool(config.get("include_replies", True))
        self._snapshot_date = _utcnow().date().isoformat()
        self._extracted_at = _utcnow().isoformat()

    @property
    def token(self) -> str:
        return self.api.page_token(self.page_id)

    def _envelope(self, record: Dict[str, Any], with_snapshot: bool = True) -> Dict[str, Any]:
        record["page_id"] = self.page_id
        record["extracted_at"] = self._extracted_at
        if with_snapshot:
            record["snapshot_date"] = self._snapshot_date
        return record

    def _list_posts(self, since: datetime, fields: str) -> Iterable[Dict[str, Any]]:
        yield from self.api.paginate(
            f"{self.page_id}/published_posts", token=self.token, limit=100, fields=fields,
            since=_to_unix(since), until=_to_unix(_utcnow()),
        )


class WindowedStream(FacebookStream, IncrementalMixin, ABC):
    """Primeiro sync varre de `start_date`; os seguintes só a janela de lookback."""

    cursor_field = "snapshot_date"

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._state: MutableMapping[str, Any] = {}

    @property
    def state(self) -> MutableMapping[str, Any]:
        return self._state

    @state.setter
    def state(self, value: MutableMapping[str, Any]) -> None:
        self._state = dict(value or {})

    def window_start(self) -> datetime:
        synced_through = self._state.get(self.cursor_field)
        if not synced_through:
            return self.start_date
        previous = datetime.fromisoformat(str(synced_through)).replace(tzinfo=timezone.utc)
        return max(self.start_date, previous - timedelta(days=self.lookback_days))

    def _close_window(self) -> None:
        self._state = {self.cursor_field: self._snapshot_date}


class Page(FacebookStream):
    """Foto diária do objeto da página. `access_token` nunca é pedido."""

    primary_key = ["page_id", "snapshot_date"]
    name = "page"

    def read_records(self, sync_mode: SyncMode, **kwargs: Any) -> Iterable[Mapping[str, Any]]:
        fields = "id,name,username,link,category,about,fan_count,followers_count,verification_status"
        data = self.api.get(self.page_id, token=self.token, fields=fields)
        data.pop("id", None)
        yield self._envelope(data)


class PageInsights(WindowedStream):
    primary_key = ["page_id", "metric", "period", "date"]
    name = "page_insights"
    cursor_field = "date"

    def window_start(self) -> datetime:
        """Trunca ao limite de retenção em vez de falhar com `start_date` antigo."""
        floor = _utcnow() - timedelta(days=PAGE_INSIGHTS_RETENTION_DAYS)
        requested = super().window_start()
        if requested < floor:
            self.logger.info(
                f"start_date {requested.date()} é anterior à retenção de insights de página; "
                f"truncado para {floor.date()}"
            )
            return floor
        return requested

    def read_records(self, sync_mode: SyncMode, **kwargs: Any) -> Iterable[Mapping[str, Any]]:
        metrics = self.config.get("page_metrics") or DEFAULT_PAGE_METRICS
        cursor = self.window_start()
        now = _utcnow()
        while cursor < now:
            chunk_end = min(cursor + timedelta(days=PAGE_INSIGHTS_CHUNK_DAYS), now)
            for item in self.api.insights(
                self.page_id, token=self.token, metrics=metrics, period="day",
                since=_to_unix(cursor), until=_to_unix(chunk_end),
            ):
                for value in item.get("values", []):
                    end_time = value.get("end_time") or ""
                    yield self._envelope({
                        "metric": item.get("name"),
                        "period": item.get("period"),
                        "date": end_time[:10] or None,
                        "title": item.get("title"),
                        "description": item.get("description"),
                        **_value_pair(value.get("value")),
                    })
            cursor = chunk_end
        self._state = {self.cursor_field: self._snapshot_date}


class Post(FacebookStream, IncrementalMixin):
    """Append-once: o post não muda, então nunca é reextraído."""

    primary_key = "post_id"
    name = "post"
    cursor_field = "created_time"

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._state: MutableMapping[str, Any] = {}

    @property
    def state(self) -> MutableMapping[str, Any]:
        return self._state

    @state.setter
    def state(self, value: MutableMapping[str, Any]) -> None:
        self._state = dict(value or {})

    def read_records(self, sync_mode: SyncMode, **kwargs: Any) -> Iterable[Mapping[str, Any]]:
        cursor = self._state.get(self.cursor_field)
        since = (
            datetime.fromisoformat(cursor.replace("+0000", "+00:00")) + timedelta(seconds=1)
            if cursor else self.start_date
        )
        latest = cursor
        for post in self._list_posts(since, POST_FIELDS):
            created = post.get("created_time")
            record = {
                "post_id": post.get("id"),
                "created_time": created,
                "updated_time": post.get("updated_time"),
                "message": post.get("message"),
                "permalink_url": post.get("permalink_url"),
                "status_type": post.get("status_type"),
                "is_published": post.get("is_published"),
                "is_hidden": post.get("is_hidden"),
                "is_expired": post.get("is_expired"),
                "full_picture": post.get("full_picture"),
                **_content_type(post.get("permalink_url")),
            }
            if created and (latest is None or created > latest):
                latest = created
            yield self._envelope(record, with_snapshot=False)
        if latest:
            self._state = {self.cursor_field: latest}


class PostMetrics(WindowedStream):
    """Contadores que mudam: uma linha por post por snapshot."""

    primary_key = ["post_id", "snapshot_date"]
    name = "post_metrics"

    def read_records(self, sync_mode: SyncMode, **kwargs: Any) -> Iterable[Mapping[str, Any]]:
        for post in self._list_posts(self.window_start(), COUNTER_FIELDS):
            yield self._envelope({
                "post_id": post.get("id"),
                "created_time": post.get("created_time"),
                "reactions_count": (post.get("reactions") or {}).get("summary", {}).get("total_count"),
                "comments_count": (post.get("comments") or {}).get("summary", {}).get("total_count"),
                "shares_count": (post.get("shares") or {}).get("count"),
            })
        self._close_window()


class PostInsights(WindowedStream):
    """Métrica lifetime por post: muda a cada leitura, por isso vai datada."""

    primary_key = ["post_id", "metric", "period", "snapshot_date"]
    name = "post_insights"

    def read_records(self, sync_mode: SyncMode, **kwargs: Any) -> Iterable[Mapping[str, Any]]:
        metrics = self.config.get("post_metrics_list") or DEFAULT_POST_METRICS
        post_ids = [p["id"] for p in self._list_posts(self.window_start(), "id") if p.get("id")]
        self.logger.info(f"post_insights: {len(post_ids)} posts na janela de {self.lookback_days} dias")
        for post_id in post_ids:
            for item in self.api.insights(post_id, token=self.token, metrics=metrics):
                for value in item.get("values", []):
                    yield self._envelope({
                        "post_id": post_id,
                        "metric": item.get("name"),
                        "period": item.get("period"),
                        "title": item.get("title"),
                        **_value_pair(value.get("value")),
                    })
        self._close_window()


class ReelInsights(WindowedStream):
    """Só o que o post não tem: reproduções, repetições e retenção."""

    primary_key = ["reel_id", "metric", "snapshot_date"]
    name = "reel_insights"

    def read_records(self, sync_mode: SyncMode, **kwargs: Any) -> Iterable[Mapping[str, Any]]:
        metrics = self.config.get("reel_metrics") or DEFAULT_REEL_METRICS
        floor = self.window_start()
        # A edge de reels não aguenta página de 100; o cliente ainda reduz sozinho se precisar.
        for reel in self.api.paginate(f"{self.page_id}/video_reels", token=self.token,
                                      limit=25, fields="id,created_time"):
            created = reel.get("created_time")
            if created and datetime.fromisoformat(created.replace("+0000", "+00:00")) < floor:
                break  # a edge vem do mais recente para o mais antigo
            for item in self.api.insights(reel["id"], token=self.token, metrics=metrics,
                                          edge="video_insights"):
                for value in item.get("values", []):
                    yield self._envelope({
                        "reel_id": reel["id"],
                        "created_time": created,
                        "metric": item.get("name"),
                        "period": item.get("period"),
                        "title": item.get("title"),
                        **_value_pair(value.get("value")),
                    })
        self._close_window()


class Comment(FacebookStream, IncrementalMixin):
    """Comentário e resposta na mesma stream. Sem autor: a API devolve `from` nulo."""

    primary_key = "comment_id"
    name = "comment"
    cursor_field = "created_time"

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._state: MutableMapping[str, Any] = {}

    @property
    def state(self) -> MutableMapping[str, Any]:
        return self._state

    @state.setter
    def state(self, value: MutableMapping[str, Any]) -> None:
        self._state = dict(value or {})

    def _window_start(self) -> datetime:
        if not self._state.get(self.cursor_field):
            return self.start_date
        return max(self.start_date, _utcnow() - timedelta(days=self.comment_window_days))

    def read_records(self, sync_mode: SyncMode, **kwargs: Any) -> Iterable[Mapping[str, Any]]:
        totals: Dict[str, int] = dict(self._state.get("post_totals") or {})
        latest = self._state.get(self.cursor_field)
        comment_filter = "stream" if self.include_replies else "toplevel"
        skipped = 0

        for post in self._list_posts(self._window_start(), COUNTER_FIELDS):
            post_id = post.get("id")
            total = (post.get("comments") or {}).get("summary", {}).get("total_count", 0)
            if not post_id or not total:
                continue
            if totals.get(post_id) == total:
                skipped += 1
                continue

            seen = 0
            for comment in self.api.paginate(f"{post_id}/comments", token=self.token, limit=100,
                                             filter=comment_filter, order="chronological",
                                             fields=COMMENT_FIELDS):
                seen += 1
                created = comment.get("created_time")
                attachment = comment.get("attachment") or {}
                yield self._envelope({
                    "comment_id": comment.get("id"),
                    "post_id": post_id,
                    "parent_id": (comment.get("parent") or {}).get("id"),
                    "created_time": created,
                    "message": comment.get("message"),
                    "like_count": comment.get("like_count"),
                    "comment_count": comment.get("comment_count"),
                    "is_hidden": comment.get("is_hidden"),
                    "can_hide": comment.get("can_hide"),
                    "permalink_url": comment.get("permalink_url"),
                    "attachment_type": attachment.get("type"),
                    "attachment_url": attachment.get("url") or attachment.get("target", {}).get("url"),
                }, with_snapshot=False)
                if created and (latest is None or created > latest):
                    latest = created

            if seen == 0:
                self.logger.warning(
                    f"Post {post_id} tem {total} comentários no total_count mas nenhum conteúdo: "
                    f"falta a task de moderação na página {self.page_id}."
                )
            else:
                totals[post_id] = total

        self.logger.info(f"comment: {skipped} posts pulados por total_count inalterado")
        self._state = {self.cursor_field: latest, "post_totals": totals}


class Story(FacebookStream):
    """Story some em 24h: é foto do que está no ar, nunca incremental."""

    primary_key = ["media_id", "snapshot_date"]
    name = "story"

    def read_records(self, sync_mode: SyncMode, **kwargs: Any) -> Iterable[Mapping[str, Any]]:
        fields = "status,creation_time,media_type,media_id,post_id,url"
        for story in self.api.paginate(f"{self.page_id}/stories", token=self.token,
                                       limit=100, fields=fields):
            media_id = story.get("media_id")
            views = None
            if media_id and story.get("media_type") == "video":
                try:
                    data = self.api.insights(media_id, token=self.token,
                                             metrics=["total_video_views"], edge="video_insights")
                    if data and data[0].get("values"):
                        views = data[0]["values"][0].get("value")
                except GraphAPIError as exc:
                    self.logger.warning(f"Sem métrica para a story {media_id}: {exc.message}")
            creation = story.get("creation_time")
            yield self._envelope({
                "media_id": media_id,
                "post_id": story.get("post_id"),
                "status": story.get("status"),
                "creation_time": (
                    datetime.fromtimestamp(int(creation), tz=timezone.utc).isoformat()
                    if creation else None
                ),
                "media_type": story.get("media_type"),
                "url": story.get("url"),
                "total_video_views": views,
            })
