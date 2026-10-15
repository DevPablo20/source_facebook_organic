# Facebook Organic — guia de uso

Guia de quem **configura e opera** o conector no Airbyte. O desenho e as regras internas
estão no [CLAUDE.md](../CLAUDE.md); aqui fica o que você precisa para ligar uma página,
escolher as janelas e entender o que cada stream devolve.

---

## 1. O que este conector resolve

O `source-facebook-pages` oficial não tem modo incremental: a cada sync ele relê **todos**
os posts da página e pede insights post a post. A extração cresce com a idade da página e
nenhum registro diz *quando* aquele número foi lido — então não dá para reconstruir a
evolução de um post nem auditar de onde veio um número.

Este conector:

- corta o histórico com `start_date`;
- só reextrai o que ainda muda, dentro de `lookback_window_days`;
- carimba **toda** métrica acumulada com `snapshot_date` e `extracted_at`, criando série
  temporal em vez de valor sobrescrito;
- adiciona **comentários**, **reels** e **stories**, que o oficial não cobre.

Medido na mesma página: o oficial lê ~697 posts por sync com 5 métricas; este lê 19 posts
com 21 métricas no sync diário.

---

## 2. Antes de configurar

### 2.1 Token

Use um **token de usuário de sistema** do Business Manager. O conector deriva sozinho o
Page Access Token de cada sync — edges de página recusam o token de sistema diretamente.

Permissões necessárias no App:

| Permissão | Para quê |
|---|---|
| `pages_show_list` | listar páginas e derivar o Page Access Token |
| `pages_read_engagement` | objeto da página, posts, reels, stories |
| `pages_read_user_content` | **comentários** |
| `read_insights` | insights de página, post e reel |
| `business_management` | páginas pelo Business Manager |

### 2.2 Tasks da página — o erro mais comum

Permissão concedida ao App **não basta**. Em *Gerir atribuições* da página, o usuário de
sistema precisa de:

- **Estatísticas** → insights de página, post e reel;
- **Atividade da comunidade** → conteúdo dos comentários.

Sem *Atividade da comunidade*, a API devolve a **contagem** de comentários mas uma lista
vazia. O conector detecta isso e loga um aviso nomeando a página, em vez de registrar "post
sem comentário". Se a stream `comment` vier vazia com posts que claramente têm comentário,
é essa task que falta.

> A Meta não oferece task de leitura de comentário sem poder de escrita: *Atividade da
> comunidade* também permite responder e remover. Não há alternativa mais estreita.

### 2.3 Descobrir o `page_id`

```
GET https://graph.facebook.com/v26.0/me/accounts?fields=id,name,tasks&access_token=<token>
```

---

## 3. Campos de configuração

| Campo | Default | O que muda na prática |
|---|---|---|
| `access_token` | — | token de usuário de sistema; o Page token é derivado a cada sync |
| `page_id` | — | **uma página por conexão**. Para N clientes, N conexões |
| `start_date` | — | corte histórico duro. Data anterior ao limite da plataforma (~2 anos para insights de página) é **truncada com log**, nunca rejeitada |
| `lookback_window_days` | 28 | idade máxima de post que ainda tem insights e contadores reextraídos. É o parâmetro que governa a duração do sync |
| `comment_window_days` | 90 | idade máxima de post vigiado por comentário novo |
| `include_replies` | true | `true` usa `filter=stream` e traz respostas na mesma stream, ligadas por `parent_id` |
| `api_version` | v26.0 | validada; v24 e v25 respondem igual, exceto duas métricas obsoletas |
| `page_metrics`, `post_metrics_list`, `reel_metrics` | listas validadas | vazio = default. Métrica inexistente é descartada com aviso, sem derrubar o sync |

### Como escolher as janelas

`lookback_window_days` existe porque métrica de post é **lifetime**: ela cresce depois da
publicação. Cerca de 80–90% do alcance acontece em 48–72h, com cauda até ~28 dias — daí o
default. Aumentar para 90 multiplica o custo do sync por ~3 e só captura cauda longa.
Post fora da janela **congela**: nunca mais é consultado.

`comment_window_days` é separado porque comentário chega em post antigo muito depois do
engajamento ter estabilizado. 90 dias cobre gestão de crise sem reler o histórico — e
posts sem comentário novo custam zero, porque o conector compara o `total_count` antes de
paginar.

> Mudar `start_date`, as janelas ou a lista de métricas exige **Clear data** dos streams
> afetados: o state guardado deixa de corresponder à nova janela.

---

## 4. Streams: o que dá para ler em cada uma

Todo registro de toda stream carrega `page_id` e `extracted_at`. Streams de métrica
acumulada carregam também `snapshot_date`.

| Stream | Pergunta de negócio que responde | Grão | Modo |
|---|---|---|---|
| `page` | como a página está hoje: seguidores, categoria, identificação | 1 linha por dia | full refresh |
| `page_insights` | como a página performou em cada dia | métrica × dia | incremental |
| `post` | o que foi publicado, quando, com que texto e link | 1 linha por post, imutável | incremental |
| `post_metrics` | como reações, comentários e compartilhamentos de cada post evoluem | post × snapshot | incremental |
| `post_insights` | alcance, visualizações, cliques e reações por tipo de cada post | métrica × post × snapshot | incremental |
| `reel_insights` | reproduções, repetições e retenção dos reels | métrica × reel × snapshot | incremental |
| `comment` | o que o público está dizendo, com a thread montada | 1 linha por comentário | incremental |
| `story` | o que foi publicado em stories enquanto está no ar | story × snapshot | full refresh |

### `page`
Foto diária: `name`, `username`, `category`, `link`, `about`, `fan_count`,
`followers_count`, `verification_status`. O `access_token` da página **nunca** é extraído.

### `page_insights`
Série diária, uma linha por métrica por dia, com `title` e `description` vindos da própria
API. A janela é fatiada de 90 em 90 dias porque a Graph API recusa intervalos longos.

### `post`
Só o que **a página publicou** (`/published_posts`). Post de terceiro no mural está fora
por decisão de produto. O post é imutável, então a stream é *append-once*: o cursor é
`created_time` e um post já extraído nunca volta.

**Reel é post.** O reel aparece aqui com `permalink_url = facebook.com/reel/{reel_id}/`. O
conector deriva dois campos disso: `content_type` (`post` ou `reel`) e `reel_id`, que é a
chave de junção com `reel_insights`.

### `post_metrics`
Separado de `post` de propósito: contador muda, texto do post não. Assim a série de
contagem não reescreve a mensagem a cada snapshot. Traz `reactions_count`,
`comments_count` e `shares_count` por `snapshot_date`.

### `post_insights`
O coração do conector. Toda métrica é `lifetime`, então o mesmo post devolve número
diferente a cada leitura — é por isso que existe `snapshot_date`. Só posts dentro de
`lookback_window_days` são consultados.

### `reel_insights`
Só o que o post **não** tem. Alcance, visualizações e reações do reel vêm por `post`/
`post_insights`; aqui ficam reproduções, repetições e curva de retenção.

### `comment`
Comentários e respostas na mesma stream, ligados por `post_id` e `parent_id`.

**Comentário não tem autor.** A Graph API devolve `from: null` para comentário de usuário
em página — e `message_tags` também não vem. Não é permissão nem versão: a identidade não é
exposta. Consequência prática: não dá para saber que 10 comentários são da mesma pessoa.
O `permalink_url` leva ao comentário no Facebook, onde a equipe vê quem escreveu.

Campos: `message`, `created_time`, `like_count`, `comment_count`, `is_hidden`, `can_hide`,
`permalink_url`, `attachment_type` e `attachment_url`. A URL de mídia de CDN fica fora de
propósito: expira em dias.

### `story`
Story existe por **24 horas**. Em sync diário, o que foi publicado e expirou entre as
execuções simplesmente não existe quando o conector olha — por isso a stream pede conexão
**horária**. Não há backfill possível: dia não coletado é dado perdido.

Campos: `media_id` (a chave — a edge não devolve `id`), `post_id`, `status`,
`creation_time`, `media_type`, `url` e `total_video_views` quando é vídeo.

---

## 5. Métricas e significados

> **Impressão e alcance mudaram de nome.** `page_impressions`, `post_impressions`,
> `page_fans` e `page_engaged_users` **não existem mais** — a API rejeita com
> `(#100) The value must be a valid insights metric`. O que os substitui é a família
> `media_view`.

| Conceito | Nome vivo |
|---|---|
| Impressões da página | `page_media_view` |
| Alcance da página | `page_total_media_view_unique` |
| Impressões do post | `post_media_view` |
| Alcance do post | `post_total_media_view_unique` |

### 5.1 `page_insights` — período `day`

| Métrica | Significado |
|---|---|
| `page_media_view` | visualizações de qualquer conteúdo da página |
| `page_total_media_view_unique` | alcance: pessoas distintas atingidas |
| `page_posts_impressions_organic` | impressões orgânicas das publicações |
| `page_post_engagements` | engajamentos em publicações no dia |
| `page_lifetime_engaged_followers_unique` | seguidores engajados (acumulado) |
| `page_follows` | total de seguidores (acumulado) |
| `page_daily_follows`, `page_daily_follows_unique` | novos seguidores no dia |
| `page_daily_unfollows_unique` | deixaram de seguir no dia |
| `page_fan_adds_by_paid_non_paid_unique` | novos likes separando pago de orgânico |
| `page_views_total` | visitas ao perfil da página |
| `page_total_actions` | ações totais na página |
| `page_actions_post_reactions_total` | reações nas publicações |
| `page_actions_post_reactions_like_total` | só curtidas |
| `page_video_views` | visualizações de vídeo |
| `page_video_views_organic` / `page_video_views_paid` | orgânico × promovido |
| `page_video_view_time` | tempo total assistido (ms) |
| `page_video_complete_views_30s` | visualizações de 30 segundos |

### 5.2 `post_insights` — período `lifetime`

| Métrica | Significado |
|---|---|
| `post_media_view` | visualizações do post |
| `post_total_media_view_unique` | alcance do post |
| `post_clicks` | cliques no post |
| `post_clicks_by_type` | cliques por tipo (JSON) |
| `post_reactions_by_type_total` | reações por tipo (JSON) |
| `post_reactions_like_total` … `post_reactions_anger_total` | cada reação isolada: like, love, wow, haha, sorry, anger |
| `post_activity_by_action_type` | compartilhamentos, comentários e likes por tipo de ação (JSON) |
| `post_video_views` | visualizações de vídeo |
| `post_video_views_organic` / `post_video_views_paid` | orgânico × promovido |
| `post_video_views_15s`, `post_video_complete_views_30s` | visualizações por duração |
| `post_video_avg_time_watched` | tempo médio assistido (ms) |
| `post_video_view_time`, `post_video_view_time_organic` | tempo total assistido (ms) |
| `post_video_retention_graph` | curva de retenção por intervalo (JSON) |
| `post_video_views_by_distribution_type` | visualizações por origem de distribuição (JSON) |

Métricas de vídeo respondem também em post de foto, devolvendo zero — filtre por
`content_type`/`status_type` no consumo para não gerar série de zeros.

### 5.3 `reel_insights`

| Métrica | Significado |
|---|---|
| `blue_reels_play_count` | reproduções do reel |
| `fb_reels_total_plays` | reproduções em toda a duração |
| `fb_reels_replay_count` | repetições |
| `post_video_avg_time_watched` | tempo médio assistido (ms) |
| `post_video_view_time` | tempo total de visualização (ms) |
| `post_video_social_actions` | comentários, compartilhamentos e reações (JSON) |
| `post_video_retention_graph` | curva de retenção (JSON) |

### 5.4 Como o valor é gravado

Cada linha de insight tem **dois** campos de valor, nunca os dois preenchidos:

- `value_numeric` — quando a métrica é escalar;
- `value_json` — quando é estrutura (`post_reactions_by_type_total`,
  `post_video_retention_graph`, `post_clicks_by_type`).

Mais `metric`, `period`, `title` (descrição da própria API) e `snapshot_date`.

---

## 6. Destino e consumo

O destino S3/MinIO **não suporta dedup**: toda conexão é **Append**. `Overwrite` apagaria
os arquivos anteriores do stream.

A deduplicação é de quem consome, pela chave natural + `snapshot_date`:

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

O "valor atual" de um post é o último snapshot:

```sql
SELECT * FROM post_insights
QUALIFY ROW_NUMBER() OVER (PARTITION BY post_id, metric ORDER BY snapshot_date DESC) = 1
```

### Conexões recomendadas

| Conexão | Streams | Frequência | Por quê |
|---|---|---|---|
| diária | todas | 1×/dia | sync principal |
| stories | `story` | de hora em hora | story expira em 24h |
| crise | `post`, `post_metrics`, `comment` | de hora em hora, sob demanda | acompanhamento próximo sem pagar o custo o tempo todo |

---

## 7. Limitações conhecidas

- **Comentário não traz autor** — `from` é sempre nulo.
- **Post de terceiro no mural fica fora** — a stream usa `/published_posts`.
- **Post fora da janela congela** — post antigo que volta a engajar não é reextraído.
- **Story só existe 24h** — sem conexão horária, não há dado.
- **Insights de página têm ~2 anos de retenção** — `start_date` mais antigo é truncado.
- **A documentação da Meta lista métricas que a API rejeita** — a lista deste guia foi
  descoberta contra uma página real, métrica por métrica.

---

## 8. Erros comuns

| Sintoma | Causa | O que fazer |
|---|---|---|
| `comment` vazia, mas há comentários | falta a task *Atividade da comunidade* | ligar na página; o log do sync nomeia qual |
| `(#190)` ou `(#210)` em edge de página | token de sistema usado direto | é tratado pelo conector; se persistir, o usuário de sistema não tem acesso à página |
| `(#100) The value must be a valid insights metric` | métrica morta na lista customizada | o conector descarta e avisa; remova da configuração |
| `Please reduce the amount of data` | página de paginação grande demais | o conector reduz sozinho; nada a fazer |
| sync lento demais | `lookback_window_days` ou `start_date` muito largos | reduzir a janela e dar *Clear data* |

---

## 9. Referências

- Métricas descobertas contra a API: [metrics.md](metrics.md)
- Endpoints, limites e permissões: [docs.md](docs.md)
- Decisões, medições e histórico: [plans/connector-v1.md](plans/connector-v1.md)
