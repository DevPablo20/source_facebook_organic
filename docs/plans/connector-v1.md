# connector-v1 — escopo e andamento

Rastreabilidade do projeto: o que já está decidido, o que ainda está aberto e quem decide.
Regra deste arquivo: decisão fechada vira regra no `CLAUDE.md` e aparece aqui com data;
medição fica aqui, nunca em `docs/*.md`.

**Status:** escopo fechado e validado contra a API; nenhuma decisão elementar pendente.
**Próxima ação:** passo 1 — esqueleto do conector e `check` autenticando na Texaco.
**Validação final da v1:** rodar a Texaco e comparar com o baseline medido (73 min na CAIXA,
132 min na Loterias, ~697 posts por sync na Texaco).

## Decisões fechadas

| # | Decisão | Data | Nota |
|---|---|---|---|
| D1 | Fork próprio em Python CDK clássico, não low-code nem patch do oficial | 2026-10-14 | lookback, snapshot, sub-stream e batch não cabem bem no declarativo |
| D2 | **Uma conexão por página** (`page_id` único na spec) | 2026-10-14 | revisada: multi-página descartada; mantém o path `{page_id}/{stream}` que o ETL já usa |
| D3 | Janela fixa + snapshot (opção A) para métricas que mudam | 2026-10-14 | `lookback_window_days` default 28; post fora da janela congela |
| D4 | `snapshot_date` + `extracted_at` em toda stream de insight e contador | 2026-10-14 | resolve o rastreio que falta hoje |
| D5 | `start_date` configurável no source, truncado ao limite da plataforma | 2026-10-14 | nunca falhar por data antiga; log do truncamento |
| D6 | Comentários com respostas incluídas (`include_replies` default true) | 2026-10-14 | gestão de crise precisa da thread; respostas por field expansion |
| D7 | Comentário vigiado só em post dentro de `comment_window_days` (default 90) | 2026-10-14 | janela própria, separada do lookback de insights |
| D8 | Checar `comments.summary(total_count)` antes de paginar comentários | 2026-10-14 | evita repaginar post sem comentário novo |
| D9 | **Só posts da própria página** — `/published_posts` | 2026-10-14 | revertida: post de terceiro no mural sai do escopo |
| D10 | **Nome e id do autor de comentário entram**; URL de mídia de CDN fica fora | 2026-10-14 | revisada: LGPD assumida pelo Pablo; link do anexo basta |
| D11 | **Reels e Stories entram, em streams separadas** | 2026-10-14 | revertida; não existe `content_type` no feed — a separação é por edge |
| D12 | Sync em Incremental + Append, dedup no bronze do `binder_etl` | 2026-10-14 | destino S3 não suporta dedup |
| D13 | Três conexões sobre o mesmo source: diária, horária de stories, horária de crise | 2026-10-14 | story só existe 24h; sem sync horário não há dado |
| D14 | Estrutura nova de tabelas; conector oficial é aposentado | 2026-10-14 | sem compatibilidade de schema com o antigo |
| D15 | `post` (append-once) separado de `post_metrics` (série) | 2026-10-14 | não reescrever texto do post a cada snapshot |
| D16 | O conector recebe token de System User e **deriva o Page Access Token** | 2026-10-14 | verificado: edge de página recusa token de System User (190/210) |
| D17 | Métrica entra na lista só depois de responder na API | 2026-10-14 | o erro da Graph API não enumera as válidas; descoberta é métrica por métrica |
| D18 | `page_video_views_unique` e `post_video_views_unique` ficam fora | 2026-10-14 | a própria descrição diz "Deprecated above Graph API v25" |
| D19 | Impressões e alcance vêm da família **`media_view`**, não de `*_impressions` | 2026-10-14 | `page_media_view`, `page_total_media_view_unique`, `post_media_view`, `post_total_media_view_unique` |
| D20 | **Comentário não tem autor.** `from` volta `null` sempre; D10 fica sem efeito | 2026-10-14 | 21 comentários lidos, zero com `from`; `message_tags` também não vem |
| D21 | **Reel é post.** O `permalink_url` do post carrega o id do reel; `reel` existe só para métrica própria | 2026-10-14 | sem dupla contagem: o fato é `post`, `content_type` sai do permalink |
| D22 | Comentário oculto e detecção de remoção ficam fora da v1 | 2026-10-14 | `is_hidden` continua sendo gravado; o que sai é a recontagem para soft-delete |
| D23 | Imagem publicada no **Docker Hub** | 2026-10-14 | mais simples que registry local no kind |
| D24 | `api_version` default **`v26.0`** | 2026-10-14 | medido: responde igual à v24.0 em 44 métricas validadas e nas 3 edges; só rejeita as duas que já tínhamos descartado (D18) |
| D25 | Imagem `devpablo20/source-facebook-organic`, repositório público | 2026-10-14 | versionada `x.y.z` + `latest` |
| D26 | **`reel_insights` entra na v1** | 2026-10-14 | 7 métricas respondem, inclusive retenção; a exclusão anterior vinha de descoberta incompleta |
| D27 | **`story` entra na v1**, em conexão horária | 2026-10-14 | story some em 24h: adiar é perder dado para sempre, não adiar custo |
| D28 | Integração no `binder_etl` sai do escopo deste repositório | 2026-10-14 | feita direto lá |

## Pendências

| # | Pendência | Quem decide | Bloqueia |
|---|---|---|---|
### Elementares — fechar antes de implementar

| # | Pendência | Quem decide |
|---|---|---|
| P7b | Replicar a task *Atividade da comunidade* nas outras 6 páginas | Pablo — **adiado por decisão**: validar a Texaco primeiro |

Nenhuma decisão elementar em aberto. A implementação pode começar.

### Opcionais — não bloqueiam, dá para ligar depois sem retrabalho

| # | Pendência | Nota |
|---|---|---|
| P1 | Enxugar a lista de métricas validada em [docs/metrics.md](../metrics.md) | é parâmetro da spec; o schema é longo (`name`/`period`/`values`) e não muda |
| P16 | Suíte de testes de aceitação (CAT) | qualidade de entrega, não requisito funcional |
| P17 | Conexão horária de crise | configuração no Airbyte, não código |

### Descartadas — fora da v1, com motivo

| Item | Motivo |
|---|---|
| Identidade do autor de comentário, com ou sem hash | a API não devolve `from` (D20) — não é escolha |
| Comentário oculto e soft-delete por recontagem | decisão do Pablo (D22) |
| Posts de terceiros no mural | decisão do Pablo (D9) |
| Métricas `*_impressions*` e demografia de fãs | nomes mortos na API (D19) |
| `page_video_views_unique`, `post_video_views_unique` | "Deprecated above Graph API v25" (D18) |
| Conexão multi-página | decisão do Pablo (D2) |

### Fechadas em rodadas anteriores

- ~~P2~~ pseudonimizar autor: Pablo assume a LGPD; nome e id entram crus (D10).
- ~~P4~~ `page_ids` x descoberta: conexão por página (D2).
- ~~P5~~ volume: medido, ver abaixo — é pequeno.
- ~~P6~~ Reels e Stories: entram, em streams separadas (D11).
- ~~P9~~ mudança no `binder_etl` por multi-página: não é mais necessária (D2).
- ~~P14~~ hipótese de bloqueio de insights: descartada — era renomeação de métrica (D19).
- ~~P3~~ comentário oculto: fora da v1 (D22).
- ~~P10~~ publicação da imagem: Docker Hub (D23).
- ~~P12~~ reel x post: o permalink do post carrega o id do reel (D21).
- ~~P7~~ permissão de comentário: resolvida na Texaco; falta replicar (P7b).

## Passos

Cada passo termina com algo verificável. Nenhum passo começa antes do anterior fechar.

| # | Passo | Entrega | Verificação |
|---|---|---|---|
| 1 | Esqueleto | `pyproject`, `source_facebook_organic/`, `spec.json`, `Dockerfile`, `metadata.yaml` | `spec` devolve a spec completa |
| 2 | Autenticação | derivação do Page Access Token (D16) e `check` | `check` passa na Texaco e falha com mensagem legível sem a task |
| 3 | Streams de página | `page`, `page_insights` com fatiamento de janela e truncamento de `start_date` | `read` devolve série diária desde `start_date` sem erro de janela |
| 4 | Streams de post | `post` (append-once, `content_type` e `reel_id` do permalink), `post_metrics`, `post_insights` com lookback e batch | sync da Texaco cobre a janela e não varre o histórico |
| 5 | Comentários | `comment` com janela própria, gate por `total_count` e respostas por field expansion | comentários da Texaco chegam com thread montada |
| 6 | Empacotamento | imagem `devpablo20/source-facebook-organic:0.1.0` no Docker Hub, conector registrado no Airbyte | sync real gravando em `raw/airbyte/facebook_organic/{page_id}/{stream}` |
| 7 | Comparação com o baseline | medir duração e volume contra os números de 14/10 | ganho demonstrado, não presumido |
| 4b | `reel_insights` | 7 métricas próprias de reel por `/{reel_id}/video_insights` | plays e retenção chegando por reel da janela |
| 5b | `story` | inventário horário + `total_video_views` por `media_id` | story capturada antes de expirar |

A integração no `binder_etl` (bronze/silver/gold das streams novas e aposentadoria do
conector antigo) é feita **no repositório do `binder_etl`**, não aqui.

Opcionais, depois do passo 7: CAT (P16) e a conexão horária de crise (P17).

## Medições

**2026-10-14 — token e acessos.** Token do `.env` é SYSTEM_USER do App `BI_Binder`, sem
expiração, alcançando 7 páginas (CAIXA, CAIXA Investe ×2, Loterias CAIXA, Se liga na Caixa,
Texaco Lubrificantes, Binder), todas com task `ANALYZE` e Page Access Token disponível.
Escopos: `ads_management`, `ads_read`, `business_management`, `instagram_basic`,
`instagram_manage_insights`, `pages_read_engagement`, `pages_read_user_content`,
`pages_show_list`, `public_profile`, `read_insights`. **Granular scopes** não trazem
`read_insights` nem `pages_read_user_content`.

**2026-10-14 — edges.** Com Page Access Token respondem `published_posts`, `feed`,
`video_reels` (3 reels na Texaco), `stories` (vazio — nenhuma no ar) e `videos`. Com token de
System User, todas falham (190/210), exceto `GET /{page-id}` e `/videos`.

**2026-10-14 — volume (Texaco Lubrificantes, 1.786 seguidores).** 20 posts em 30 dias, 74 em
90 dias, 283 em 365 dias. Comentários: zero nos 10 posts mais recentes. Em CAIXA, o post mais
recente tem `toplevel=2` e `stream=4` (2 respostas). **Conclusão:** volume é de ordem de
dezenas de posts por mês por página — rate limit não é restrição; o gargalo do conector
oficial era o varrimento histórico, não o tamanho do dado.

**2026-10-14 — métricas.** 62 nomes de page insights testados: 16 responderam, 46 rejeitadas.
47 nomes de post insights testados em post de vídeo e de foto: 22 e 20 responderam. Lista com
significado em [docs/metrics.md](../metrics.md). `page_impressions` e `post_impressions` são
rejeitados **em todas as versões de v19.0 a v26.0 e em mais de uma página**, o que descarta
deprecação por versão e sustenta a hipótese de permissão (P14).

**2026-10-14 — rate limit.** `x-business-use-case-usage` devolve por página
`{type: pages, call_count, total_cputime, total_time, estimated_time_to_regain_access}`.
Após ~300 requests da descoberta, uso permaneceu em 1% — folga grande para o volume medido.

**2026-10-14 — métricas, correção.** A rejeição de `page_impressions`/`post_impressions` **não
é permissão**: `read_insights` funciona. Os nomes foram substituídos pela família
`media_view` (D19), descoberta ao inspecionar o parquet de produção. A hipótese anterior de
bloqueio de insights está descartada; o único bloqueio real é o de comentários.

**2026-10-14 — lake real (192.168.10.80:9000).** `raw/airbyte` tem 3,8 GiB em 899 objetos:
`facebook_organic` 1,7 GiB/396 — **o maior prefixo do lake** —, `instagram_organic`
1,5 GiB/317, `tiktok` 376 MiB/96, `meta` 301 MiB/76, `kwai` 20 MiB/14. Por página:
CAIXA 799 MiB/190, Loterias CAIXA 643 MiB/134, Texaco 298 MiB/72. Por stream na CAIXA:
`post` 365 MiB/79, `post_insights` 344 MiB/83, `page` 80 MiB/21, `page_insights` 10 MiB/7 —
ou seja, **89% do volume está nas duas streams de post**, exatamente as que não têm
incremental.

**2026-10-14 — duração real do sync.** CAIXA em 14/10: 04:06 → 05:20, **73 minutos**.
Loterias CAIXA em 08/10: 00:02 → 02:14 em `post_insights`, **132 minutos** e 171 MiB num
único sync. Texaco: menos de 1 minuto. Além disso, `post` e `post_insights` da Loterias
**não gravam nada desde 08/10**, enquanto `page` e `page_insights` da mesma página rodaram
em 13/10 — sintoma de falha ou estouro de tempo nos streams pesados.

**2026-10-14 — baseline de produção.** O conector oficial grava 5 métricas por post
(`post_clicks`, `post_clicks_by_type`, `post_media_view`, `post_reactions_by_type_total`,
`post_total_media_view_unique`) para **todos os posts da página**: 3.954 linhas num arquivo
de 159 KB da Texaco, ~697 posts por sync, contra 283 posts publicados em 365 dias. É a
medida exata do desperdício que a janela elimina.

**2026-10-14 — reels e stories.** `/{reel_id}/video_insights` responde 7 métricas:
`blue_reels_play_count` (71), `fb_reels_total_plays` (75), `fb_reels_replay_count` (4),
`post_video_avg_time_watched` (8.228 ms), `post_video_view_time` (584.217 ms),
`post_video_social_actions` e `post_video_retention_graph` (curva de retenção por intervalo).
Stories: havia 7 ativas no momento da medição (Texaco 3, Loterias 5, CAIXA 5, Se liga 1). O
edge devolve `status`, `creation_time` (unix), `media_type`, `media_id`, `post_id` e `url` —
**sem campo `id`**, e o `post_id` não é endereçável como objeto. O `media_id` é: devolve
`created_time`, `length`, `permalink_url` e aceita `total_video_views` em `video_insights`.

**2026-10-14 — versões.** As 20 métricas de página e 24 de post validadas respondem igual em
`v24.0`, `v25.0` e `v26.0`; `published_posts`, `video_reels`, `stories` e `comments` também.
A única diferença na `v26.0` é a rejeição de `page_video_views_unique` e
`post_video_views_unique` — as duas que D18 já descartava.

**2026-10-14 — permissão validada.** Com a task de moderação ligada na Texaco,
`pages_read_user_content` passou a aparecer nos granular scopes e os comentários voltam com
conteúdo: `message`, `created_time`, `like_count`, `comment_count`, `is_hidden`, `can_hide`,
`permalink_url`. **`from` volta `null` em 21 de 21 comentários lidos**, e `message_tags` não
vem — não há identidade de autor a extrair. A Texaco ficou com todas as tasks
(`MANAGE`, `CREATE_CONTENT`, `MODERATE`, …); nas demais páginas basta *Atividade da
comunidade*.

**2026-10-14 — reel x post.** Os 10 reels da Texaco não casam com `published_posts` por id
nem por `created_time` (defasagem de 5 a 12 segundos), mas **o `permalink_url` do post é
`facebook.com/reel/{reel_id}/`**. O post é o fato, o permalink dá o `content_type` e a chave
de junção com o reel. `/video_reels` só agrega métrica própria — das testadas, apenas
`blue_reels_play_count` respondeu, via `/{id}/video_insights`.

## Diário

**2026-10-14** — Escopo levantado e fechado (D1–D19), com reversões do Pablo em D2, D9, D10 e
D11. Lido o `binder_etl` para alinhar convenções. Descoberta executada contra a API real com
o token do projeto: edges, volume, shape de comentário e lista de métricas. Três achados mudam o plano: o conector
precisa derivar o Page Access Token (D16); impressões e alcance mudaram de nome para a
família `media_view` (D19), o que só apareceu ao ler o parquet de produção; e o conteúdo dos
comentários está bloqueado por task de página (P7). Medido no MinIO real: `facebook_organic`
é o maior prefixo do lake e um sync chega a 132 minutos numa página só. Ao fim do dia, a
permissão foi ligada na Texaco e validada: comentários leem, mas sem autor (D20); e ficou
provado que reel é post (D21). Criados `CLAUDE.md`, `docs/docs.md`,
`docs/metrics.md`, este plano, `.env.example` e `.gitignore`. Scripts da descoberta ficaram no
scratchpad da sessão, não no projeto.
