# source_facebook_organic

Conector Airbyte (Python CDK) para conteúdo **orgânico** de páginas do Facebook: página,
insights de página, posts, reels, stories, insights de post e **comentários**. Substitui o
`source-facebook-pages` oficial no `binder_etl` — o oficial é aposentado, não mantido em
paralelo.

**Por que existir:** o conector oficial não tem modo incremental. Cada sync varre todo o
histórico de posts e chama insights post a post, então a duração da extração cresce com a
idade da página e nenhum registro diz *quando* aquele número foi observado. Este conector
corta a janela (`start_date`), congela o que já estabilizou (`lookback_window_days`), data
cada leitura (`snapshot_date`) e adiciona comentários — que o oficial não cobre.

**Uso fim:** ETL para a equipe de monitoramento acompanhar páginas, posts e comentários dos
clientes, substituindo ferramentas externas de social listening (Brandwatch, Zing).

## Estado

v1 implementada e validada: as 8 streams rodam pelo Airbyte de desenvolvimento gravando no
MinIO local. Decisões (fechadas e pendentes), status, medições e diário em
[docs/plans/connector-v1.md](docs/plans/connector-v1.md). Referências externas e achados de
API em [docs/docs.md](docs/docs.md).

| Ambiente | Airbyte | MinIO |
|---|---|---|
| Desenvolvimento | `localhost:8080` | `localhost:9000` (console 9001) |
| Produção | — | `192.168.10.80:9000` (console 9001), só leitura para comparação |

## Invariantes

Contradizer uma delas é bug, não escolha de implementação.

1. **Custo de sync é constante, não função da idade da página.** Nenhum stream varre o
   histórico inteiro a cada execução. Toda stream derivada de post opera dentro de uma
   janela de dias configurável.
2. **Métrica acumulada é série, não estado.** Todo valor de insight e todo contador
   (reações, comentários, compartilhamentos) é gravado com `snapshot_date` e
   `extracted_at`. A linha nunca é sobrescrita; o "valor atual" é o último snapshot.
3. **Uma conexão, uma página.** `page_id` é campo único da spec. Ainda assim todo registro
   de toda stream carrega `page_id`, para o lake não depender do caminho do arquivo.
4. **Cada tipo de conteúdo tem sua stream.** Post, reel e story vêm de edges diferentes e
   nunca se misturam numa tabela só.
5. **Comentário não tem autor.** A API devolve `from: null` para comentário de usuário.
   Thread se liga por `post_id`/`parent_id`; não existe identidade a extrair, hashear ou
   proteger.

## Streams da v1

| Stream | Endpoint | Modo | Cursor | Chave natural | Grão |
|---|---|---|---|---|---|
| `page` | `/{page-id}` | Full refresh + Append | — | `page_id + snapshot_date` | foto diária da página |
| `page_insights` | `/{page-id}/insights` | Incremental + Append | `date` | `page_id + metric + period + date` | métrica × dia |
| `post` | `/{page-id}/published_posts` | Incremental + Append | `created_time` | `post_id` | post publicado pela página |
| `post_metrics` | `/{page-id}/published_posts` (campos de contagem) | Incremental + Append | `created_time` do post | `post_id + snapshot_date` | contadores × post × snapshot |
| `post_insights` | `/{post-id}/insights` | Incremental + Append | `created_time` do post | `post_id + metric + period + snapshot_date` | métrica × post × snapshot |
| `reel_insights` | `/{reel-id}/video_insights` | Incremental + Append | `created_time` do reel | `reel_id + metric + snapshot_date` | métrica × reel × snapshot |
| `story` | `/{page-id}/stories` | Full refresh + Append | — | `media_id + snapshot_date` | story enquanto está no ar |
| `comment` | `/{post-id}/comments` | Incremental + Append | `created_time` do comentário, por post | `comment_id` | comentário e resposta |

`post` traz **somente o que a página publicou** (`/published_posts`). Post de terceiro no
mural está fora de escopo por decisão de produto, não por limitação técnica.

`post_metrics` existe separado de `post` porque contador muda e post não: assim `post` fica
append-once e a série de contagem não duplica o texto do post a cada snapshot.

## Regras duras

- **Destino é S3/MinIO, que não suporta dedup.** Toda conexão é **Append**; `Overwrite`
  apaga os arquivos anteriores do stream. A deduplicação acontece no bronze do `binder_etl`,
  pela chave natural da tabela acima + `snapshot_date`.
- **O conector troca o token sozinho.** A spec recebe o token de System User; o Page Access
  Token sai de `GET /{page-id}?fields=access_token` no início do sync. Edge de página
  (`published_posts`, `video_reels`, `stories`, `comments`) **falha com token de System
  User** — erro 190/210. O token derivado nunca é gravado em registro de saída.
- **Reel é post.** O reel aparece em `/published_posts` com id próprio e
  `permalink_url = facebook.com/reel/{reel_id}/`. O fato é sempre `post`; `content_type` sai
  do permalink e a junção com `reel_insights` usa o `reel_id` extraído dele. Não existe
  stream `reel`: só `reel_insights`, com a métrica que o post não tem.
- **Story só existe por 24h.** A stream `story` depende de sync horário; em sync diário a
  story simplesmente não existe quando o conector olha. Story nunca é incremental por
  cursor — é foto do que está no ar.
- **Story não tem `id`.** O edge devolve `status`, `creation_time` (unix), `media_type`,
  `media_id`, `post_id` e `url`. A chave é `media_id`, que é o único endereçável: o `post_id`
  da story não resolve como objeto. Métrica de story vem de
  `/{media_id}/video_insights?metric=total_video_views`.
- **Janela dupla, parâmetros separados.** `lookback_window_days` governa reextração de
  insights/contadores; `comment_window_days` governa até que idade de post os comentários
  continuam sendo vigiados. Não compartilham valor.
- **Fora da janela, congelado.** Post publicado antes de `now - janela` não é consultado de
  novo. Isso é escolha de desenho, não limitação: posts antigos que voltam a engajar são
  perda aceita na v1.
- **Respostas de comentário vêm por field expansion**, não por request por comentário
  (`comments{...}` aninhado). Request por comentário reintroduz o problema que o conector
  existe para resolver.
- **Comentário mudo é erro de configuração, não ausência de dado.** Quando
  `summary.total_count > 0` e `data` volta vazio, falta a task de moderação naquela página: o
  conector loga aviso nomeando a página, e não trata como "post sem comentário".
- **Antes de paginar comentários, confira o total.** `comments.summary(total_count)` na
  listagem de posts custa zero request extra; se o total não mudou desde o último state, o
  post é pulado. O `total_count` responde mesmo quando o conteúdo do comentário não — não
  confundir contador disponível com comentário acessível.
- **`start_date` é configurável e truncado, nunca fixo.** Pedido anterior ao limite da
  plataforma é elevado ao limite (≈2 anos para `page_insights`), com log explícito. O
  conector nunca falha por `start_date` antigo.
- **Versão da Graph API é parâmetro**, com default único em um só lugar do código. Nunca
  hardcode de versão espalhado por stream.
- **Rate limit é tratado por backoff lendo `x-business-use-case-usage`** (tipo `pages`:
  `call_count`, `total_cputime`, `total_time`, `estimated_time_to_regain_access`) e
  `x-app-usage`. `sleep` fixo é proibido.
- **Mudar `start_date`, `lookback_window_days` ou a lista de métricas exige Clear data** dos
  streams afetados no Airbyte.
- **Nenhum token em registro de saída.** `page` nunca extrai `access_token`, e qualquer URL
  em log, erro ou traceback tem o `access_token` redigido.
- **A spec é a documentação que o operador vê.** O painel lateral do Airbyte só serve
  conectores do registry oficial, então regra de negócio de cada campo mora na `description`
  da spec. Mudou o comportamento de um parâmetro, muda a descrição no mesmo commit.
- **Métrica não validada contra a API não entra na lista.** A lista vem de descoberta contra
  página real, não da documentação nem do conector antigo: pedir métrica morta derruba o
  request inteiro, e a mensagem de erro da Graph API **não** enumera as válidas. A
  documentação da Meta lista nomes que a API rejeita — ela não é fonte confiável aqui.
- **Impressão e alcance são `media_view`.** `page_media_view` / `post_media_view` e
  `page_total_media_view_unique` / `post_total_media_view_unique`. Qualquer nome
  `*_impressions*` está morto; não ressuscitar por analogia com o conector antigo.

## Configuração (spec do source)

| Campo | Tipo | Default | Papel |
|---|---|---|---|
| `access_token` | secret | — | token de System User (o conector deriva o Page token) |
| `page_id` | string | — | uma página por conexão |
| `start_date` | date | — | corte histórico duro |
| `lookback_window_days` | int | 28 | reextração de insights e contadores de post |
| `comment_window_days` | int | 90 | idade máxima de post vigiado por comentário |
| `include_replies` | bool | true | respostas de comentário na mesma stream |
| `page_metrics` / `post_metrics_list` | array | lista validada | métricas por stream |
| `api_version` | string | `v26.0` | versão da Graph API |

## Dado pessoal

A questão se resolveu sozinha: a Graph API **não devolve o autor** de comentário de usuário
(`from: null` em todos os casos medidos, `message_tags` idem). Resta o texto do comentário,
que é livre e pode conter dado pessoal digitado por terceiro — inerente à finalidade de
monitoramento, sem mascaramento no conector.

Também fora: **URL de mídia de CDN** (`attachment.media.image.src` e similares) — expira
em dias e rehospedar imagem de terceiro não serve a nenhum requisito. Entram
`attachment.type` e o link de destino; a equipe abre o link quando precisa.

## Integração com binder_etl

O ETL vive em `/var/www/binder_app/binder_etl` (medallion Spark + Delta no MinIO).

- Destino: bucket `raw`, path format **`airbyte/facebook_organic/{page_id}/{stream}`** — a
  mesma convenção que o pipeline já usa hoje, preservada porque a conexão é por página. O
  lake de produção é o MinIO em `192.168.10.80:9000`; em desenvolvimento, o local.
- Três conexões sobre o mesmo source: **diária** (todos os streams, 01:00
  America/Sao_Paulo, antes do DAG `facebook_organic_daily`), **horária de stories**
  (`story`) e **horária de crise** (`post`, `post_metrics`, `comment`), ligada sob demanda.
- As convenções de bronze/silver/gold, nomes e testes seguem o `CLAUDE.md` do `binder_etl`.
  Mudança de schema aqui é mudança lá.

## Documentação

| Arquivo | Quando ler |
|---|---|
| [docs/connector.md](docs/connector.md) | guia de uso: pré-requisitos, campos, o que cada stream responde, métricas e erros comuns |
| [docs/docs.md](docs/docs.md) | links e extratos: Graph API, CDK, destino S3, limites, permissões e achados de API |
| [docs/metrics.md](docs/metrics.md) | quais métricas de insight respondem hoje e o que cada uma significa |
| [docs/plans/connector-v1.md](docs/plans/connector-v1.md) | decisões fechadas e pendentes, próxima ação, medições datadas |

## Onde cada informação mora

| Tipo | Onde |
|---|---|
| Regra que vale sempre | `CLAUDE.md` |
| Como e por que funciona; referência externa | `docs/*.md` — no presente, sem data |
| O que falta, status, decisão em aberto, medição datada | `docs/plans/connector-v1.md` |
