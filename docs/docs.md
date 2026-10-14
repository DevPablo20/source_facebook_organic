# Documentação de referência e achados de API

Fontes usadas para desenhar o conector, com o que cada uma resolve e o extrato que importa.
A seção final registra o que foi **verificado contra a API real** com o token do projeto —
tem precedência sobre a documentação quando divergirem.

## Airbyte — desenvolvimento de conector

| Link | Resolve |
|---|---|
| https://docs.airbyte.com/platform/connector-development/cdk-python | Python CDK: `AbstractSource`, `HttpStream`, `IncrementalMixin`, slicing, state, backoff |
| https://docs.airbyte.com/platform/connector-development/ | visão geral, scaffolding do gerador, `metadata.yaml`, Dockerfile |
| https://docs.airbyte.com/platform/connector-development/testing-connectors/connector-acceptance-tests-reference | testes de aceitação (CAT): `spec`, `check`, `discover`, `read`, incremental |
| https://docs.airbyte.com/integrations/sources/facebook-pages | conector base que estamos adaptando: streams, spec e limitações |
| https://docs.airbyte.com/integrations/destinations/s3 | destino S3/MinIO: formatos, path format, **modos de sync suportados** |
| https://docs.airbyte.com/platform/using-airbyte/getting-started/add-a-connector | registrar conector customizado por imagem Docker na instância |

Pontos que condicionam o desenho:

- **O destino S3 não oferece `Incremental + Dedup`.** Os modos são full refresh
  overwrite/append e incremental append. Logo o conector entrega append com `snapshot_date`
  e a deduplicação é do bronze — não é contorno, é o desenho certo para data lake.
- **Instalação por `abctl`** roda Airbyte em Kubernetes (kind). Imagem de conector
  customizado precisa estar disponível ao cluster (carregar a imagem no nó do kind ou
  publicar em registry alcançável). **(a confirmar na primeira publicação)**
- O conector base é mantido como manifest declarativo com lista de métricas fixa — é o que
  impede ajustar métricas e janela sem fork.

## Meta Graph API — página

https://developers.facebook.com/docs/graph-api/reference/v24.0/page/#overview

- Objeto da página: `id`, `name`, `username`, `link`, `category`, `fan_count`,
  `followers_count`, `about`, `verification_status`.
- `access_token` é campo do objeto: `GET /{page-id}?fields=access_token` com token de System
  User devolve o **Page Access Token**. É assim que o conector obtém o token das edges.
- `/me/accounts?fields=id,name,access_token,tasks` lista as páginas que o token alcança, com
  o token de cada uma e as *tasks* atribuídas.

## Meta Graph API — insights de página

https://developers.facebook.com/docs/graph-api/reference/v24.0/page/insights

- `GET /{page-id}/insights?metric=...&period=...&since=...&until=...`
- `period`: `day`, `week`, `days_28`, `month`, `lifetime`. A resposta é série temporal:
  um objeto por métrica, com lista de `values` (`value`, `end_time`) e, muito útil para
  catalogar, `title` e `description` legíveis.
- **Janela máxima por request** em torno de 93 dias para `period=day` — exige fatiar o
  intervalo entre `start_date` e hoje em pedaços. **(a confirmar)**
- **Retenção** de aproximadamente 2 anos: `start_date` mais antigo é truncado.
- Métrica descontinuada derruba o request inteiro, e a mensagem de erro **não** enumera as
  válidas (só `(#100) The value must be a valid insights metric`). Daí a descoberta métrica
  por métrica.

## Meta Graph API — feed, posts, reels e stories

https://developers.facebook.com/docs/graph-api/reference/v24.0/page/feed

- `/{page-id}/published_posts` traz só o que a página publicou — é o que usamos.
  `/{page-id}/feed` traz também posts de terceiros no mural; fora de escopo por decisão.
- Aceita `since` / `until` sobre `created_time` — é o que viabiliza `start_date` e janela.
- Campos de interesse: `id`, `created_time`, `updated_time`, `message`, `permalink_url`,
  `status_type`, `is_published`, `is_hidden`, `is_expired`, `full_picture`,
  `shares.count`, `reactions.summary(total_count)`, `comments.summary(total_count)`.
- Insights de post: `GET /{post-id}/insights?metric=...` — métricas são `lifetime`
  acumuladas, logo o mesmo post devolve valor diferente em dias diferentes.
- **Reels são edge própria:** `GET /{page-id}/video_reels`. Métricas de reel ficam em
  `/{video-id}/video_insights`. Não existe parâmetro `content_type` no feed — a separação
  por tipo de conteúdo se faz escolhendo a edge.
- **Stories são edge própria:** `GET /{page-id}/stories`, e só existem enquanto estão no ar
  (24h). Sem coleta horária, não há dado nenhum.

### Comentários

https://developers.facebook.com/docs/graph-api/reference/v24.0/object/comments

- `GET /{post-id}/comments`
- `filter=toplevel` (só 1º nível) ou `stream` (tudo achatado); `order=chronological` ou
  `reverse_chronological`; `summary=total_count` devolve o total sem paginar.
- Campos usados: `id`, `created_time`, `message`, `from`, `like_count`, `comment_count`,
  `parent.id`, `permalink_url`, `is_hidden`, `can_hide`, `attachment.type`.
- Campo **deliberadamente não usado**: `attachment.media` (URL de CDN que expira).
- Respostas por field expansion aninhada na própria listagem de posts, com `limit`
  explícito nos dois níveis. **(a confirmar quais limites a API aceita aninhados)**
- Comentário removido pelo autor ou pela página simplesmente deixa de aparecer; detectar
  remoção exige recontagem — ver pendência de soft-delete no plano.

## Meta Graph API — plataforma

| Link | Resolve |
|---|---|
| https://developers.facebook.com/docs/graph-api/guides/versioning | ciclo de vida das versões; a versão é parâmetro do conector |
| https://developers.facebook.com/docs/graph-api/changelog | o que morreu em cada versão — consultar antes de fixar métricas |
| https://developers.facebook.com/docs/graph-api/overview/rate-limiting | limites e headers `x-app-usage`, `x-business-use-case-usage` |
| https://developers.facebook.com/docs/graph-api/batch-requests | até 50 sub-requests por POST — usado para insights de post em lote |
| https://developers.facebook.com/docs/graph-api/results | paginação por cursor e por tempo (`since`/`until`) |
| https://developers.facebook.com/docs/graph-api/field-expansion | expansão de campos e aninhamento com `limit` |
| https://developers.facebook.com/docs/permissions | permissões e Advanced Access |
| https://developers.facebook.com/docs/pages/access-tokens | tasks de página (`ANALYZE`, `MODERATE`, …) e o que cada uma libera |
| https://developers.facebook.com/docs/graph-api/reference/debug_token | conferir escopos e *granular scopes* de um token |

### Permissões necessárias

| Permissão | Para que |
|---|---|
| `pages_show_list` | listar páginas do token e derivar o Page Access Token |
| `pages_read_engagement` | objeto da página, posts publicados, reels, stories |
| `pages_read_user_content` | **comentários de usuários** |
| `read_insights` | insights de página, de post e de reel |
| `business_management` | páginas via Business Manager com token de System User |

Permissão concedida ao App não basta: o System User precisa da *task* correspondente em
cada página. `ANALYZE` libera leitura e insights; conteúdo gerado por usuário exige task de
moderação.

### Rate limit

Páginas usam limite por caso de uso de negócio, informado em `x-business-use-case-usage`,
com uma entrada por página contendo `type: pages`, `call_count`, `total_cputime`,
`total_time` e `estimated_time_to_regain_access`. O conector lê esse header e faz backoff;
`sleep` fixo é proibido. Requests por sync ≈ 1 (token) + fatias de `page_insights` +
posts na janela ÷ tamanho do batch + posts com comentário novo.

## Achados verificados contra a API

Medições e validações datadas ficam em
[plans/connector-v1.md](plans/connector-v1.md); aqui fica só o que é comportamento
permanente da plataforma:

- Edge de página (`published_posts`, `feed`, `video_reels`, `stories`, `comments`) **recusa
  token de System User** com erro 190 ou 210; aceita Page Access Token derivado dele.
  `GET /{page-id}` e `/{page-id}/videos` respondem com os dois.
- `/{post-id}/comments` pode devolver `summary.total_count` preenchido e `data: []` vazio
  quando falta permissão/task: contador e conteúdo têm gates diferentes.
- `filter=stream` conta comentário + resposta; `filter=toplevel` só o 1º nível. A diferença
  entre os dois totais é a quantidade de respostas, sem custo de paginação.
- `debug_token` distingue `scopes` (o que o App tem) de `granular_scopes` (o que vale para
  os ativos): permissão que aparece só em `scopes` não funciona na prática.
