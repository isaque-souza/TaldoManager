# Plano de implementação — dados reais

Revisão 2 — 2026-11-18, com as decisões aprovadas sobre a auditoria
([AUDIT-FOOTBALL-DATA.md](AUDIT-FOOTBALL-DATA.md)). Um PR por fase, a suíte
inteira (`pytest -n auto`, baseline **994 passando**) antes de cada merge, e
paro para revisão nas fases marcadas com ⚠.

## Decisões aprovadas

| # | Decisão | Consequência no plano |
|---|---|---|
| 1 | **Sem fotos e escudos** por enquanto | Nenhum download de imagem. O formato do mundo reserva o lugar (`midia`: vazio), para receber depois com licença |
| 2 | **API-Football no plano grátis primeiro** | Piloto e medição no grátis; um mês pago só para a importação completa, se a conta mostrar que precisa. O jogo nunca depende de assinatura |
| 3 | **Brasileirão 2017 fica** | Não é reimportado nem alterado. Um Brasileirão recente pode entrar depois como liga/mundo **a mais** |
| 4 | **Carreiras ficam no mundo em que nasceram** | Mundos versionados e imutáveis; a virada não puxa ligas de outro mundo |
| 5 | **Piloto só com a Premier atual** | Expansão para as outras 13 ligas só depois do piloto validado de ponta a ponta |

Requisitos adicionais:

- **A. Identidade do jogador**: id interno (o `jogador.id` do banco), id
  externo estável (`apif:<id>`), nome só para exibição. Dois "João Silva" são
  dois jogadores.
- **B. Versionamento imutável**: cada mundo com id, data, origem, temporadas,
  contagens, hash dos arquivos e histórico de alterações; mundos antigos
  sempre disponíveis para os saves que os usam.

Restrições mantidas: banco sem reset (migrações aditivas; cenário limpo só em
cópia isolada), seeds atuais intocadas, sem importação completa por ora.

## Os três mundos

| Mundo | Conteúdo | Situação |
|---|---|---|
| **v1 — Base histórica** | as 8 ligas de hoje (Taldo, Taldo B, Premier 23/24, Championship, La Liga, Segunda, Brasileirão 2017, Série B 2017) | congelado; todo save existente fica nele |
| **v2 — Premier atual** | v1 com a Premier trocada pela temporada atual, vinda da API-Football | piloto |
| **v3 — Universo expandido** | 14 ligas, ~7.000 jogadores; Brasileirão 2017 mantido | futuro |

---

## Fase 0 — Proteção (sem mudança de comportamento)

- Baseline registrado: 994 passando (`-n auto`, ~3 min).
- `pytest-xdist` no `requirements.txt` (PR separado; o Dockerfile já descarta
  as linhas `pytest*` do servidor).
- Antes de cada deploy com migração: `bash ~/taldo/deploy/backup.sh antes-<fase>`
  na VPS (o backup diário de 14 dias já existe; este é um ponto de retorno
  nomeado).
- `.gitignore` para `backend/data/fontes/api-football/` (respostas brutas fora
  do Git até confirmar os termos).

## Fase 1 — Mundos versionados ⚠ (antes de qualquer importação)

> **Feita** (branch `feat/mundos-versionados`). Como ficou: [MUNDOS.md](MUNDOS.md).
> Diferenças do desenho abaixo: o manifesto do v1 fica em
> `data/mundos/v1/manifesto.json` (raiz `seeds`), como todo mundo; o v1 não
> tem histórico de alterações (é o começo); erro de mundo responde 503.

O objetivo: um save nascido no mundo X carrega **exatamente** os arquivos de X,
para sempre, e é impossível alterar X sem o teste acusar.

### 1.1 Onde os mundos ficam

```
backend/data/
  seeds/                  ← NÃO muda: é o conteúdo do mundo v1, nos lugares de hoje
  mundos/
    v1.json               ← manifesto do v1 (aponta para data/seeds/)
    v2/
      manifesto.json
      ligas/premier/{clubes,jogadores,livres}.json
      ligas/taldo/...     ← cópias exatas do v1 (mesmo hash)
```

- O **v1 não é movido** nem reescrito: o manifesto dele descreve os arquivos
  de `data/seeds/` como estão hoje.
- Mundos novos têm pasta própria e **cópia** dos arquivos das ligas que não
  mudaram (1–3 MB por mundo; simples e à prova de "alguém mexeu na pasta do
  outro"). Os hashes iguais deixam claro que são as mesmas ligas.
- Os mundos vão na imagem Docker (o Dockerfile já copia `backend/` inteiro).

### 1.2 O manifesto (requisito B)

```json
{
  "id": "v2",
  "formato": 1,
  "nome": "Premier League atual",
  "criado_em": "2026-11-20T14:03:00Z",
  "base": "v1",
  "ligas": {
    "premier": {
      "nome": "Premier League", "pais": "Inglaterra", "divisao": 1,
      "origem": "API-Football v3", "temporada": "2025/26",
      "obtido_em": "2026-11-19", "clubes": 20, "jogadores": 460, "livres": 40
    },
    "taldo": { "origem": "fictícia (gerar_dados.py)", "temporada": null, "...": "..." }
  },
  "totais": { "ligas": 8, "clubes": 160, "jogadores": 3900, "livres": 320 },
  "arquivos": { "ligas/premier/clubes.json": "sha256:…", "...": "…" },
  "gerado_por": { "script": "scripts/mundos.py criar", "commit": "abc1234" },
  "midia": {},
  "alteracoes": {
    "resumo": "Premier 23/24 → 2025/26",
    "clubes": { "entraram": ["…"], "sairam": ["…"] },
    "jogadores": { "entraram": 210, "sairam": 190, "mudaram_de_clube": 35 }
  }
}
```

- `alteracoes` é o histórico em relação ao `base` (por `ref` quando houver;
  por nome no v1, que não tem `ref`). O histórico completo é a cadeia
  v1 → v2 → v3.
- `midia` fica vazio (decisão 1): lugar reservado para fotos/escudos futuros.

### 1.3 Imutabilidade, garantida por teste

- `scripts/mundos.py criar <id> --base v1 --liga premier=<pasta>` monta a
  pasta, calcula os hashes e escreve o manifesto. Nunca sobrescreve um mundo
  que já existe.
- `data_loader` confere os hashes de um mundo na primeira carga do processo
  (com cache); arquivo diferente do manifesto = erro claro, nunca carga
  silenciosa.
- Teste na suíte: **todo mundo do repositório bate com o próprio manifesto**.
  Editar `data/seeds/` (ou qualquer mundo) quebra a suíte. Correção de dado =
  mundo novo.
- Os scripts antigos que escrevem em `data/seeds/` (`gerar_dados`,
  `ampliar_elencos`, `gerar_funcoes`, `gerar_ligas`, `importar_*`) passam a
  recusar escrever lá (ou escrevem numa pasta de trabalho que vira mundo novo).

### 1.4 O save sabe o seu mundo

- Migração aditiva: `simulacao.mundo TEXT NOT NULL DEFAULT 'v1'`. Todo save
  existente vira v1 sem tocar em nenhuma linha.
- Jogo novo grava o mundo escolhido (padrão: o marcado como `atual` no
  índice de mundos; no início, continua sendo v1 até o v2 ser validado).
- A virada da carreira copia o `mundo` da temporada anterior.

### 1.5 Tudo que lê seed passa a receber o mundo

| Hoje | Depois |
|---|---|
| `LIGAS` fixo em `data_loader` | ligas lidas do manifesto do mundo |
| `carregar_campeonato(ligas)` | `carregar_campeonato(ligas, mundo)` |
| `carregar_campeonato_do_save(sim)` | usa `sim["mundo"]` |
| `rivais_do_seed()` (cache único) | cache por mundo |
| `TODAS_AS_LIGAS` (rotas, jogo novo, lista de clubes, elenco do clube) | ligas do mundo pedido |
| `divisoes.do_save_na_virada(ligas, TODAS_AS_LIGAS)` | só ligas do **mesmo** mundo (decisão 4) |
| nomes da seed em `carreira_service` (linha 55) | do mundo do save |

A API ganha `mundo` opcional no jogo novo e um `GET /mundos` (id, nome,
ligas, temporadas) para a tela de novo jogo poder oferecer épocas diferentes
mais tarde. Sem `mundo`, tudo responde como hoje.

### 1.6 Mundo que sumiu

Save que aponta para um mundo ausente: erro claro ("o mundo v2 não está
instalado"), nunca 500 genérico. Na subida do app, um aviso no log lista
mundos referenciados por saves e ausentes no disco. Mundo nunca é apagado do
repositório.

### 1.7 Testes desta fase

- Suíte inteira igual ao baseline (mesma seed → mesmos resultados no v1).
- Save antigo (sem coluna `mundo`) migra para v1, abre, avança e vira.
- Mundo de teste com clube renomeado/novo/removido não afeta save do v1.
- Carreira no v1 não recebe liga que só existe noutro mundo.
- Hash adulterado → erro; mundo ausente → erro claro.
- Migração em cópia de banco com saves reais (cópia isolada no scratchpad,
  nunca o banco real).

## Fase 2 — Identidade do jogador (requisito A) ⚠

Hoje o nome é a chave do jogador dentro do save: `estado_json` (elencos por
nome), `xi_preferido`, `plano.xi`, `negociacao.jogador`, `emprestimo.jogador`,
`observado.nome`, `movimento_virada.jogador`, mensagens — e o frontend manda
nomes de volta (escalação, substituições, mercado). Por isso os importadores
forçam nomes únicos no mundo inteiro.

Para "dois João Silva, dois jogadores" sem refatorar tudo de uma vez:

1. **Seed**: cada jogador de mundo novo ganha `ref` (`apif:12345`; os
   fictícios, `taldo:<id da seed>`), `nome` (exibição, pode repetir) e
   `chave` (única no mundo; igual ao nome quando não há repetição,
   `"João Silva·apif:12345"` quando há). O importador gera a chave; o
   relatório lista os repetidos.
2. **Domínio e banco**: a chave entra onde o nome entra hoje — é a mesma
   string que o código já usa como identidade, então o motor e os snapshots
   não mudam de lógica. Ganham `nome_exibicao` e `ref` o `Jogador`, a tabela
   `jogador` (colunas aditivas) e o snapshot.
3. **API e frontend**: as respostas passam a mandar `chave` e `nome`; a tela
   mostra `nome` e devolve `chave` nas ações. No v1 chave = nome, então os saves
   antigos não percebem diferença.
4. **Nacionalidade**: entra no `Jogador` (já existe nas seeds reais; opcional).

Isso é pré-requisito do piloto (a Premier atual tem nomes repetidos com outros
mundos/ligas) e indispensável para o v3.

## Fase 3 — Cliente da API, offline ⚠ (chave da API)

`backend/scripts/football_data/`, rodado à mão, nunca pelo site:

- `provedor.py`: interface do fornecedor (`ligas`, `temporadas`, `clubes`,
  `elenco`, `jogadores`/estatísticas).
- `api_football.py`: chave só em `API_FOOTBALL_KEY`; timeout; retry com
  espera; teto por minuto e por dia (para antes de estourar e retoma no dia
  seguinte); valida a resposta; conta as requisições gastas.
- `cache.py`: cada resposta em `data/fontes/api-football/<endpoint>/<params>.json`
  com data. Com cache presente, não chama a API → reexecutar é grátis e
  idempotente; falha no meio retoma de onde parou.
- Testes só com fixtures (`tests/fixtures/api_football/`): timeout, 429,
  limite diário, resposta inválida/incompleta, cache.
- **Medição** (decisão 2): conferir em `/leagues/seasons` quais temporadas o
  grátis cobre; contar requisições do piloto; projetar para 14 ligas.
- Você cria a conta e põe a chave numa variável de ambiente local.

## Fase 4 — Piloto: mundo v2 com a Premier atual ⚠

`scripts/importar_api_football.py` (no molde de `importar_premier.py`), lendo
só do cache:

- clubes: nome, país; torcida/dinheiro pelos parâmetros da liga; `identidade`
  do clube do v1 quando o nome bate, senão gerada como hoje;
- jogadores: `ref`, nome, chave, idade (nascimento), setor (posição da API),
  camisa, nacionalidade; função/secundárias estimadas como hoje; **campo
  ausente fica ausente** (nunca 0) e conta no relatório;
- `overall`: a estimativa atual (força do clube, camisa, idade, teto,
  estrelas à mão) mais minutos e nota média da temporada anterior quando a API
  tiver;
- relatório (`data/fontes/api-football/relatorio-<data>.md`): encontrados,
  novos, ignorados, erros, nomes repetidos, sem estatística;
- `scripts/mundos.py criar v2 --base v1 --liga premier=…`.

Validação (a lista aprovada):

| Item | Como |
|---|---|
| Clubes e jogadores importados | relatório + teste de contagem/integridade do mundo |
| Ids externos | todo jogador do v2 com `ref` único |
| Nomes repetidos | teste com dois jogadores de mesmo nome no mesmo save |
| Relacionamentos | todo id de titular/reserva existe; ninguém em dois clubes |
| Geração das seeds | rodar duas vezes = mesmos arquivos (mesmo hash) |
| Criação de carreira | jogo novo no v2 (API e tela), banco no scratchpad |
| Simulação | temporada inteira; tabela, artilharia e notas plausíveis |
| Virada | v2 → temporada 2 continua no v2 |
| Saves anteriores | save do v1 abre, avança e vira, igual ao baseline |

Só depois disso o v2 vira o mundo padrão de jogo novo.

## Fase 5 — v3: universo expandido ⚠ (custo e desempenho)

- Com a medição da Fase 3, decidir se paga um mês da API; importar as 13
  ligas restantes para o cache local (fica guardado; a assinatura acaba).
- Ligas novas (Itália, Alemanha, França A/B; Championship, La Liga e Segunda
  reais): `divisoes`, pesos de economia, copa nacional por país, nomes no
  frontend — tudo lido do manifesto do mundo.
- Brasileirão 2017 e Liga Taldo copiados do v1.
- **Medir antes de publicar**: tempo de rodada e tamanho do `estado_json`
  com ~7.000 jogadores. Se passar do aceitável, simplificar as partidas sem o
  técnico ou deixar o técnico escolher as ligas do save.

## Depois (não planejado em detalhe)

- **Sincronização**: baixar de novo + reimportar = mundo novo (v4...), com
  `alteracoes` contando transferências reais por `ref`. Nada é apagado.
- **Brasileirão recente**: liga a mais num mundo novo, sem tocar no 2017.
- **Mídia**: só com licença; usa o `midia` reservado no manifesto, com cache
  no servidor e fallback para a identidade desenhada.
- **Competições continentais reais**: projeto à parte, partindo da copa entre
  ligas da v2.6.

## Testes obrigatórios (onde entram)

| Teste | Fase |
|---|---|
| Migração em banco com saves antigos; save antigo abre/avança/vira | 1 (e em todas as seguintes) |
| Mundo adulterado / ausente | 1 |
| Rollback de migração | 1 — por backup (as migrações do projeto não têm "down") |
| Jogadores com nome igual | 2, 4 |
| API fora do ar / 429 / limite / resposta inválida / falha no meio | 3 |
| Importação duplicada (mesmo hash) | 4 |
| Jogador sem campos | 4 |
| Transferência real / mudança de elenco entre mundos | 4 (v1 → v2), sincronização |
| Motor: mesmos resultados com a mesma seed no v1 | 1–5 |
| Rodada com 14 ligas dentro do tempo-alvo | 5 |

## Fora do escopo

Trocar SQLite, ORM ou o sistema de migrações; resetar o banco; reescrever o
motor; resultados de partidas reais; imagens sem licença.
