# source-facebook-organic

Conector Airbyte (Python CDK) para conteúdo orgânico de páginas do Facebook — página,
insights, posts, reels, stories e comentários — com janela de extração configurável e
snapshot datado. Substitui o `source-facebook-pages` oficial, que não tem modo incremental.

Escopo, regras e decisões: [CLAUDE.md](CLAUDE.md) ·
[docs/docs.md](docs/docs.md) · [docs/metrics.md](docs/metrics.md) ·
[docs/plans/connector-v1.md](docs/plans/connector-v1.md)

## Streams

| Stream | Modo | Chave | Observação |
|---|---|---|---|
| `page` | full refresh | `page_id + snapshot_date` | foto diária |
| `page_insights` | incremental | `page_id + metric + period + date` | fatiado de 90 em 90 dias |
| `post` | incremental | `post_id` | append-once; reel identificado pelo permalink |
| `post_metrics` | incremental | `post_id + snapshot_date` | reações, comentários e compartilhamentos |
| `post_insights` | incremental | `post_id + metric + period + snapshot_date` | só posts na janela de lookback |
| `reel_insights` | incremental | `reel_id + metric + snapshot_date` | reproduções, repetições e retenção |
| `comment` | incremental | `comment_id` | respostas incluídas; sem autor (a API não devolve) |
| `story` | full refresh | `media_id + snapshot_date` | exige sync horário: story expira em 24h |

## Configuração

Token de **usuário de sistema** do Business Manager; o conector deriva o Page Access Token
sozinho. A página precisa das tasks *Estatísticas* e, para comentários, *Atividade da
comunidade*.

| Campo | Default |
|---|---|
| `access_token`, `page_id`, `start_date` | obrigatórios |
| `lookback_window_days` | 28 |
| `comment_window_days` | 90 |
| `include_replies` | true |
| `api_version` | v26.0 |
| `page_metrics`, `post_metrics_list`, `reel_metrics` | listas validadas em `docs/metrics.md` |

## Desenvolvimento

```bash
python -m venv .venv && .venv/bin/pip install -e .
cp .env.example .env            # preencha; secrets/config.json é gerado a partir dele
.venv/bin/python main.py spec
.venv/bin/python main.py check --config secrets/config.json
.venv/bin/python main.py discover --config secrets/config.json
.venv/bin/python main.py read --config secrets/config.json --catalog catalog.json
```

## Publicação

```bash
docker build -t devpablo20/source-facebook-organic:0.1.1 .
docker push devpablo20/source-facebook-organic:0.1.1
```

No Airbyte: Settings → Sources → New connector → nome `Facebook Organic`, imagem
`devpablo20/source-facebook-organic`, tag `0.1.0`, URL da documentação deste repositório.
