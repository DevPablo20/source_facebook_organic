# Facebook Organic — conector Airbyte

Conteúdo **orgânico** de páginas do Facebook: página, insights, posts, reels, stories e
**comentários** — com janela de extração configurável e snapshot datado.

Substitui o `source-facebook-pages` oficial, que não tem modo incremental: ele relê todos os
posts da página a cada sync e pede insights post a post, então a extração cresce com a idade
da página e nenhum registro diz *quando* aquele número foi lido.

Medido na mesma página: o oficial lê **~697 posts por sync** com 5 métricas; este lê **19**
com 21 métricas, no sync diário.

📘 **[Guia completo de uso](https://github.com/DevPablo20/source_facebook_organic/blob/main/docs/connector.md)** ·
💻 **[Código](https://github.com/DevPablo20/source_facebook_organic)**

---

## Instalação

No Airbyte: **Settings → Sources → New connector → Add a custom connector**

| Campo | Valor |
|---|---|
| Connector display name | `Facebook Organic` |
| Docker repository name | `devpablo20/source-facebook-organic` |
| Docker image tag | `0.1.1` |
| Connector documentation URL | `https://github.com/DevPablo20/source_facebook_organic` |

> O painel *Setup Guide* do Airbyte só exibe documentação de conectores do registry oficial e
> fica vazio para qualquer conector customizado. Aqui a documentação está nas **descrições
> dos campos**, que o formulário de configuração renderiza, e no guia acima.

---

## Requisitos

Token de **usuário de sistema** do Business Manager — o conector deriva sozinho o Page Access
Token a cada sync.

**Permissões do App:** `pages_show_list`, `pages_read_engagement`, `pages_read_user_content`
(comentários), `read_insights`, `business_management`.

**Tasks da página** (em *Gerir atribuições*), o erro mais comum:

- **Estatísticas** → insights de página, post e reel
- **Atividade da comunidade** → conteúdo dos comentários

Sem a segunda, a API devolve a *contagem* de comentários mas lista vazia. O conector detecta
e loga um aviso nomeando a página, em vez de registrar "post sem comentário".

---

## Configuração

| Campo | Default | O que faz |
|---|---|---|
| `access_token` | — | token de usuário de sistema |
| `page_id` | — | **uma página por conexão** |
| `start_date` | — | corte histórico. Data além da retenção da plataforma é truncada com log, nunca rejeitada |
| `lookback_window_days` | 28 | idade máxima de post que ainda tem insights reextraídos — **governa a duração do sync** |
| `comment_window_days` | 90 | idade máxima de post vigiado por comentário novo |
| `include_replies` | true | respostas na mesma stream, ligadas por `parent_id` |
| `api_version` | v26.0 | validada; v24 e v25 respondem igual |
| `page_metrics`, `post_metrics_list`, `reel_metrics` | validadas | vazio usa a lista padrão; métrica inexistente é descartada com aviso |

Métrica de post é `lifetime` e continua crescendo após a publicação: ~80–90% do alcance
acontece em 48–72h, com cauda até ~28 dias — daí o default do lookback. Post fora da janela
**congela**: não é consultado de novo.

---

## Streams

| Stream | O que responde | Grão | Modo |
|---|---|---|---|
| `page` | seguidores, categoria, identificação da página | 1 linha por dia | full refresh |
| `page_insights` | performance da página em cada dia | métrica × dia | incremental |
| `post` | o que foi publicado, quando, texto e link | 1 linha por post | incremental |
| `post_metrics` | evolução de reações, comentários e compartilhamentos | post × snapshot | incremental |
| `post_insights` | alcance, visualizações, cliques e reações por post | métrica × post × snapshot | incremental |
| `reel_insights` | reproduções, repetições e retenção dos reels | métrica × reel × snapshot | incremental |
| `comment` | o que o público diz, com a thread montada | 1 linha por comentário | incremental |
| `story` | stories publicadas enquanto estão no ar | story × snapshot | full refresh |

**Reel é post.** O reel aparece em `post` com `permalink_url = facebook.com/reel/{reel_id}/`;
daí saem `content_type` e `reel_id`. A stream `reel_insights` traz só o que o post não tem.

**Comentário não tem autor.** A Graph API devolve `from: null` para comentário de usuário em
página — não é permissão nem versão. O `permalink_url` leva ao comentário no Facebook.

**Story existe por 24h.** Sem conexão horária, não há dado: não existe backfill.

---

## Métricas

Impressão e alcance **mudaram de nome** na Graph API. `page_impressions`, `post_impressions`,
`page_fans` e `page_engaged_users` não existem mais — a API rejeita com `#100`.

| Conceito | Nome vivo |
|---|---|
| Impressões da página | `page_media_view` |
| Alcance da página | `page_total_media_view_unique` |
| Impressões do post | `post_media_view` |
| Alcance do post | `post_total_media_view_unique` |

Também disponíveis: engajamento e seguidores da página, reações por tipo, cliques, família
completa de vídeo e, para reels, `blue_reels_play_count`, `fb_reels_total_plays`,
`fb_reels_replay_count` e `post_video_retention_graph`.

A lista completa, com o significado de cada métrica, está no
[guia](https://github.com/DevPablo20/source_facebook_organic/blob/main/docs/connector.md#5-métricas-e-significados).

---

## Como os dados chegam

Todo registro carrega `page_id` e `extracted_at`; streams de métrica acumulada carregam
`snapshot_date`. Cada linha de insight tem `value_numeric` **ou** `value_json` — escalares de
um lado, estruturas (reações por tipo, curva de retenção) do outro.

Use **Append**: destinos de data lake não deduplicam, e a série datada é o que permite
reconstruir a evolução de um post. A deduplicação é de quem consome, pela chave natural:

| Stream | Chave natural |
|---|---|
| `page` | `page_id + snapshot_date` |
| `page_insights` | `page_id + metric + period + date` |
| `post` | `post_id` |
| `post_metrics` | `post_id + snapshot_date` |
| `post_insights` | `post_id + metric + period + snapshot_date` |
| `reel_insights` | `reel_id + metric + snapshot_date` |
| `comment` | `comment_id` |
| `story` | `media_id + snapshot_date` |

Conexões recomendadas: uma **diária** com todas as streams, uma **horária** só de `story`, e
uma **horária sob demanda** com `post`, `post_metrics` e `comment` para acompanhamento de
crise.

---

## Limitações conhecidas

- Comentário não traz autor — `from` é sempre nulo
- Post de terceiro no mural fica fora: a stream usa `/published_posts`
- Post fora da janela de lookback não é reextraído
- Insights de página têm ~2 anos de retenção
- Mudar `start_date`, as janelas ou a lista de métricas exige *Clear data* dos streams

---

## Versões

| Tag | Novidade |
|---|---|
| `0.1.1` | spec autodocumentada, campo a campo |
| `0.1.0` | 8 streams, janela de lookback, snapshot datado, comentários |

Licença e código: [github.com/DevPablo20/source_facebook_organic](https://github.com/DevPablo20/source_facebook_organic)
