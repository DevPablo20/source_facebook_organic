"""Ponto de entrada do conector."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, List, Mapping, Optional, Tuple

from airbyte_cdk.sources import AbstractSource
from airbyte_cdk.sources.streams import Stream

from .api import GraphAPI, GraphAPIError
from .streams import (
    Comment, DEFAULT_PAGE_METRICS, Page, PageInsights, Post, PostInsights, PostMetrics,
    ReelInsights, Story,
)

DEFAULT_API_VERSION = "v26.0"


class SourceFacebookOrganic(AbstractSource):
    @staticmethod
    def _client(config: Mapping[str, Any], logger: Optional[logging.Logger] = None) -> GraphAPI:
        return GraphAPI(
            access_token=config["access_token"],
            api_version=config.get("api_version") or DEFAULT_API_VERSION,
            logger=logger,
        )

    def check_connection(self, logger: logging.Logger, config: Mapping[str, Any]) -> Tuple[bool, Any]:
        try:
            datetime.fromisoformat(str(config["start_date"])).replace(tzinfo=timezone.utc)
        except ValueError:
            return False, "start_date precisa estar no formato YYYY-MM-DD."

        page_id = str(config["page_id"])
        api = self._client(config, logger)
        try:
            token = api.page_token(page_id)
            page = api.get(page_id, token=token, fields="id,name")
            logger.info(f"Conectado à página {page.get('name')} ({page.get('id')})")
            api.insights(page_id, token=token, metrics=[DEFAULT_PAGE_METRICS[0]], period="day")
            self._warn_if_comments_are_muted(api, token, page_id, logger)
        except GraphAPIError as exc:
            return False, str(exc)
        return True, None

    @staticmethod
    def _warn_if_comments_are_muted(api: GraphAPI, token: str, page_id: str,
                                    logger: logging.Logger) -> None:
        """total_count sem conteúdo é falta de task de moderação, não ausência de comentário."""
        posts = api.get(
            f"{page_id}/published_posts", token=token, limit=25,
            fields="id,comments.summary(total_count).limit(0)",
        ).get("data", [])
        with_comments = next(
            (p for p in posts if (p.get("comments") or {}).get("summary", {}).get("total_count")), None
        )
        if not with_comments:
            return
        sample = api.get(f"{with_comments['id']}/comments", token=token, limit=1).get("data", [])
        if not sample:
            logger.warning(
                f"A página {page_id} devolve contagem de comentários mas nenhum conteúdo. "
                f"Ligue a task 'Atividade da comunidade' (MODERATE) do usuário de sistema "
                f"nessa página; a stream comment virá vazia até lá."
            )

    def streams(self, config: Mapping[str, Any]) -> List[Stream]:
        api = self._client(config)
        return [
            Page(api, config),
            PageInsights(api, config),
            Post(api, config),
            PostMetrics(api, config),
            PostInsights(api, config),
            ReelInsights(api, config),
            Comment(api, config),
            Story(api, config),
        ]
