# Métricas de insights — o que a API devolve hoje

Lista **descoberta contra a API**, não copiada de documentação: cada nome foi pedido
individualmente e classificado pela resposta. Métrica ausente desta lista derruba o request
inteiro com `(#100) The value must be a valid insights metric`.

> **A família de impressões morreu e foi renomeada.** `page_impressions`,
> `post_impressions`, `page_fans`, `page_engaged_users` e parentes são rejeitados com
> `#100` em todas as versões, em todas as páginas e com qualquer token. O que os substitui
> é a família **`media_view`**, que a API devolve como *"Visualizações no Facebook"*:
>
> | Conceito antigo | Nome vivo hoje |
> |---|---|
> | `page_impressions` (impressões da página) | `page_media_view` |
> | `page_impressions_unique` (alcance da página) | `page_total_media_view_unique` |
> | `post_impressions` (impressões do post) | `post_media_view` |
> | `post_impressions_unique` (alcance do post) | `post_total_media_view_unique` |
>
> Não é falta de permissão: `read_insights` funciona, como provam as métricas abaixo.
> Insights é a única parte do conector que **não** está bloqueada.

## Page insights — responderam

| Métrica | Período | Significado (título da API) |
|---|---|---|
| `page_media_view` | day | Visualizações no Facebook — substitui `page_impressions` |
| `page_total_media_view_unique` | day | Alcance — substitui `page_impressions_unique` |
| `page_lifetime_engaged_followers_unique` | day | Seguidores engajados (lifetime) |
| `page_fan_adds_by_paid_non_paid_unique` | day | Daily New likes by paid and non-paid |
| `page_posts_impressions_organic` | day | Daily Organic impressions of your posts |
| `page_post_engagements` | day | Daily Post Engagements |
| `page_follows` | day | Lifetime Total Follows |
| `page_daily_follows` | day | Daily New Follows |
| `page_daily_follows_unique` | day | Daily New Follows |
| `page_daily_unfollows_unique` | day | Daily New Unfollows |
| `page_views_total` | day | Daily Total views count per Page |
| `page_video_views` | day | Daily Total Video Views |
| `page_video_views_unique` | day | Deprecated above Graph API v25: Daily Total Unique Video Views |
| `page_video_views_paid` | day | Daily Total Promoted Views |
| `page_video_views_organic` | day | Daily Total Organic Views |
| `page_video_view_time` | day | Daily Total Video View Time (in MS) |
| `page_video_complete_views_30s` | day | Daily Total 30-Second Views |
| `page_actions_post_reactions_total` | day | Daily: total post reactions of a page. |
| `page_actions_post_reactions_like_total` | day | Daily total post like reactions of a page. |
| `page_total_actions` | day | Daily Total: total action count per Page |

## Page insights — rejeitadas nesta condição

`page_impressions`, `page_impressions_unique`, `page_impressions_paid`, `page_impressions_paid_unique`, `page_impressions_organic_v2`, `page_impressions_organic_unique_v2`, `page_impressions_viral`, `page_impressions_viral_unique`, `page_impressions_nonviral`, `page_impressions_nonviral_unique`, `page_posts_impressions`, `page_posts_impressions_unique`, `page_posts_impressions_paid`, `page_posts_impressions_paid_unique`, `page_posts_impressions_organic_unique`, `page_posts_impressions_viral`, `page_posts_impressions_viral_unique`, `page_posts_impressions_nonviral`, `page_posts_impressions_nonviral_unique`, `page_posts_served_impressions_organic_unique`, `page_engaged_users`, `page_consumptions`, `page_consumptions_unique`, `page_consumptions_by_consumption_type`, `page_negative_feedback`, `page_negative_feedback_unique`, `page_fans`, `page_fan_adds`, `page_fan_adds_unique`, `page_fan_removes`, `page_fan_removes_unique`, `page_fans_country`, `page_fans_city`, `page_fans_locale`, `page_fans_gender_age`, `page_fans_online`, `page_fans_online_per_day`, `page_views_logged_in_total`, `page_views_logout`, `page_video_views_10s`, `page_cta_clicks_logged_in_total`, `page_places_checkin_total`, `page_content_activity`, `page_content_activity_by_action_type`, `page_tab_views_login_top_unique`, `page_posts_impressions_frequency_distribution`

## Post insights — responderam (post de vídeo)

| Métrica | Período | Significado (título da API) |
|---|---|---|
| `post_media_view` | lifetime | Visualizações — substitui `post_impressions` |
| `post_total_media_view_unique` | lifetime | Alcance — substitui `post_impressions_unique` |
| `post_clicks` | lifetime | Lifetime Matched Audience Targeting Consumptions on Post |
| `post_clicks_by_type` | lifetime | Lifetime Matched Audience Targeting Consumptions by Type |
| `post_reactions_like_total` | lifetime | Lifetime Total Like Reactions of a post. |
| `post_reactions_love_total` | lifetime | Lifetime Total Love Reactions of a post. |
| `post_reactions_wow_total` | lifetime | Lifetime Total wow Reactions of a post. |
| `post_reactions_haha_total` | lifetime | Lifetime Total haha Reactions of a post. |
| `post_reactions_sorry_total` | lifetime | Lifetime Total sad Reactions of a post. |
| `post_reactions_anger_total` | lifetime | Lifetime Total anger Reactions of a post. |
| `post_reactions_by_type_total` | lifetime | Lifetime Total post Reactions by Type. |
| `post_activity_by_action_type` | lifetime | Lifetime Post Stories by action type |
| `post_video_views` | lifetime | Lifetime Total Video Views |
| `post_video_views_unique` | lifetime | Deprecated above Graph API v25: Lifetime Unique Video Views |
| `post_video_views_organic` | lifetime | Lifetime Organic Video Views |
| `post_video_views_organic_unique` | lifetime | Lifetime Organic Video Views |
| `post_video_views_paid` | lifetime | Lifetime Paid Video Views |
| `post_video_views_15s` | lifetime | Lifetime Total Video 15s Views |
| `post_video_avg_time_watched` | lifetime | Lifetime Average time video viewed |
| `post_video_complete_views_30s` | lifetime | Lifetime Total 30-Second Views |
| `post_video_view_time` | lifetime | Lifetime Total Video View Time (in MS) |
| `post_video_view_time_organic` | lifetime | Lifetime Total Organic Video View Time (in MS) |
| `post_video_retention_graph` | lifetime | Lifetime Percentage of views at each interval (video post) |
| `post_video_views_by_distribution_type` | lifetime | Lifetime Video Views by Distribution Type (page_owned/shared) |

## Post insights — rejeitadas (post de vídeo)

`post_impressions`, `post_impressions_unique`, `post_impressions_paid`, `post_impressions_paid_unique`, `post_impressions_organic`, `post_impressions_organic_unique`, `post_impressions_viral`, `post_impressions_viral_unique`, `post_impressions_nonviral`, `post_impressions_nonviral_unique`, `post_impressions_fan`, `post_impressions_fan_unique`, `post_impressions_by_story_type`, `post_engaged_users`, `post_engaged_fan`, `post_negative_feedback`, `post_negative_feedback_unique`, `post_negative_feedback_by_type`, `post_clicks_unique`, `post_activity`, `post_activity_unique`, `post_video_views_10s`, `post_video_social_actions`, `post_video_followers`, `blue_reels_play_count`

## Post insights — responderam (post de foto)

| Métrica | Período | Significado (título da API) |
|---|---|---|
| `post_clicks` | lifetime | Lifetime Matched Audience Targeting Consumptions on Post |
| `post_clicks_by_type` | lifetime | Lifetime Matched Audience Targeting Consumptions by Type |
| `post_reactions_like_total` | lifetime | Lifetime Total Like Reactions of a post. |
| `post_reactions_love_total` | lifetime | Lifetime Total Love Reactions of a post. |
| `post_reactions_wow_total` | lifetime | Lifetime Total wow Reactions of a post. |
| `post_reactions_haha_total` | lifetime | Lifetime Total haha Reactions of a post. |
| `post_reactions_sorry_total` | lifetime | Lifetime Total sad Reactions of a post. |
| `post_reactions_anger_total` | lifetime | Lifetime Total anger Reactions of a post. |
| `post_reactions_by_type_total` | lifetime | Lifetime Total post Reactions by Type. |
| `post_activity_by_action_type` | lifetime | Lifetime Post Stories by action type |
| `post_video_views` | lifetime | Lifetime Total Video Views |
| `post_video_views_unique` | lifetime | Deprecated above Graph API v25: Lifetime Unique Video Views |
| `post_video_views_organic` | lifetime | Lifetime Organic Video Views |
| `post_video_views_organic_unique` | lifetime | Lifetime Organic Video Views |
| `post_video_views_paid` | lifetime | Lifetime Paid Video Views |
| `post_video_views_15s` | lifetime | Lifetime Total Video 15s Views |
| `post_video_complete_views_30s` | lifetime | Lifetime Total 30-Second Views |
| `post_video_view_time_organic` | lifetime | Lifetime Total Organic Video View Time (in MS) |
| `post_video_retention_graph` | lifetime | Lifetime Percentage of views at each interval (video post) |
| `post_video_views_by_distribution_type` | lifetime | Lifetime Video Views by Distribution Type (page_owned/shared) |

## Post insights — rejeitadas (post de foto)

`post_impressions`, `post_impressions_unique`, `post_impressions_paid`, `post_impressions_paid_unique`, `post_impressions_organic`, `post_impressions_organic_unique`, `post_impressions_viral`, `post_impressions_viral_unique`, `post_impressions_nonviral`, `post_impressions_nonviral_unique`, `post_impressions_fan`, `post_impressions_fan_unique`, `post_impressions_by_story_type`, `post_engaged_users`, `post_engaged_fan`, `post_negative_feedback`, `post_negative_feedback_unique`, `post_negative_feedback_by_type`, `post_clicks_unique`, `post_activity`, `post_activity_unique`, `post_video_views_10s`, `post_video_avg_time_watched`, `post_video_view_time`, `post_video_social_actions`, `post_video_followers`, `blue_reels_play_count`

## O que a produção extrai hoje

O conector oficial, no sync de 2026-10-14, grava exatamente **5 métricas por post**:
`post_clicks`, `post_clicks_by_type`, `post_media_view`, `post_reactions_by_type_total` e
`post_total_media_view_unique` — e as grava para **todos os posts da página**, não só os
recentes. Um único arquivo de 159 KB da Texaco traz 3.954 linhas, cerca de 697 posts.

## Nomes testados e mortos na família nova

`page_media_view_unique`, `page_total_media_view`, `post_media_view_unique`,
`post_total_media_view`, `post_media_view_organic`, `post_media_view_paid`, `post_views`,
`post_total_views`, `post_engagement`, `page_views_unique`, `page_content_views`,
`page_fans_by_like_source`, `page_negative_feedback_by_type`, `page_tab_views_login_top`.
Só existem `*_media_view` e `*_total_media_view_unique` — sem recorte orgânico/pago.

## Reel insights — `/{reel_id}/video_insights`

| Métrica | Significado |
|---|---|
| `blue_reels_play_count` | reproduções do reel |
| `fb_reels_total_plays` | reproduções em toda a duração |
| `fb_reels_replay_count` | repetições |
| `post_video_avg_time_watched` | média de tempo assistido (ms) |
| `post_video_view_time` | tempo total de visualização (ms) |
| `post_video_social_actions` | comentários, partilhas e reações no reel |
| `post_video_retention_graph` | curva de retenção por intervalo (JSON, não escalar) |

As métricas de post (`post_media_view`, `post_total_media_view_unique`, reações) vêm pela
stream `post`, já que o reel também é post. Aqui só entra o que o post não tem.

## Story — `/{page-id}/stories` e `/{media_id}/video_insights`

Inventário: `status`, `creation_time` (unix), `media_type`, `media_id`, `post_id`, `url`.
Métrica: `total_video_views` pelo `media_id`. Não existe campo `id` e o `post_id` não é
endereçável como objeto.

## Leitura dos resultados

- **Todo valor de post é `lifetime`** — é por isso que o mesmo post muda de número a cada
  leitura e por isso existe `snapshot_date`.
- **Reação por tipo responde bem** (`post_reactions_*_total` e
  `post_reactions_by_type_total`), então sentimento por reação é viável sem impressões.
- **Vídeo é a família mais rica** e responde também em post de foto, devolvendo zero: filtrar
  por tipo de conteúdo no silver evita série de zeros.
- `page_video_views_unique` e `post_video_views_unique` vêm com *"Deprecated above Graph API
  v25"* na própria descrição: não entram na lista final.
- `post_video_retention_graph` e `post_video_views_by_distribution_type` devolvem estrutura
  aninhada, não escalar — tratar como JSON, não como número.
