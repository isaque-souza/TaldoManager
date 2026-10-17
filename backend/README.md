# Backend — Taldo Manager

API FastAPI + engine de simulação + persistência em SQLite (`sqlite3` puro,
sem ORM). O roadmap do projeto fica no [README raiz](../README.md).

## Rodar

Precisa de **Python 3.10+** (o Python 3.9 que vem com o Xcode não serve).
Com o [uv](https://docs.astral.sh/uv/):

```bash
cd backend
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
source .venv/bin/activate
uvicorn app.main:app --reload
```

- API: `http://localhost:8000`
- Docs interativas: `http://localhost:8000/docs`
- O banco local é criado em `data/database/taldo_manager.db` no primeiro
  start (gitignorado; o schema versionado é `app/db/schema.sql`). Dá pra
  trocar o caminho pela env `TALDO_DB`.

## Testes

```bash
cd backend
python -m pytest -q
```

`tests/conftest.py` dá um SQLite temporário por teste (nunca toca no banco
real).

## Organização

```text
app/
├── api/            rotas + schemas Pydantic
├── core/           config (caminho do banco, etc.)
├── db/             schema.sql + conexao.py (init_db idempotente no lifespan)
├── domain/         Jogador, Clube, Partida, Campeonato — a engine, sem I/O
├── repositories/   uma função pura por tabela, recebe a conn
├── services/       simulacao_service: _rodar -> _serializar -> _montar_visao
└── main.py         app FastAPI + CORS + lifespan
scripts/data_loader.py   monta o Campeonato a partir do seed JSON
```

### Fluxo de uma temporada

`simulacao_service` tem três entradas que produzem a mesma visão:

- `simular_temporada(seed)` — roda e devolve, **não** salva
- `salvar_temporada(seed)` — roda, persiste (simulação + clubes + jogadores
  + partidas + lances + atuações) e devolve o id
- `carregar_temporada(id)` — lê do banco

Mais: `detalhe_clube`, `detalhe_partida` (timeline + escalações com nota) e
`game_log_jogador` (nota partida a partida).

## Endpoints

As escolhas do técnico (só valem com um `clube`): `tatica`
(`ofensivo`/`equilibrado`/`defensivo`), `formacao` (`4-4-2`, `3-5-2`, ...) e
`xi` (nomes do XI titular preferido). A tática mexe nos pesos da engine desse
clube; o XI é uma preferência — cansados cedem lugar a reservas.

`GET /simulacao` usa query params; `POST /simulacoes` usa um **corpo JSON**
(`{seed, clube, tatica, formacao, xi, modo}`, tudo opcional). `modo` é
`"completa"` (padrão) ou `"rodada_a_rodada"` — este cria um save "em
andamento" (parado antes da rodada 1, exige `clube`) que se avança uma
rodada por vez.

| Método | Rota | O quê |
|---|---|---|
| `GET` | `/clubes` | os 20 clubes do seed |
| `GET` | `/clubes/{nome}` | elenco + formações (para montar a escalação) |
| `GET` | `/simulacao?seed=&clube=&tatica=&formacao=` | roda sem salvar (modo rápido) |
| `GET` | `/simulacoes` | lista as salvas (com `estado`/`rodada_atual`) |
| `POST` | `/simulacoes` (corpo JSON) | roda e salva, ou inicia rodada a rodada |
| `GET` | `/simulacoes/{id}` | classificação, rankings, recordes |
| `DELETE` | `/simulacoes/{id}` | apaga (cascata) |
| `GET` | `/simulacoes/{id}/rodadas/proxima` | confrontos da próxima rodada + elenco dirigido |
| `POST` | `/simulacoes/{id}/rodadas` (corpo JSON) | joga a próxima rodada (`{tatica, formacao, xi}` opcionais) |
| `GET` | `/simulacoes/{id}/clubes/{clube_id}` | elenco + 38 jogos |
| `GET` | `/simulacoes/{id}/partidas/{partida_id}` | placar, stats, timeline, escalações |
| `GET` | `/simulacoes/{id}/jogadores/{jogador_id}` | ficha + game log |
| `GET` | `/simulacoes/{id}/mercado?posicao=&valor_max=` | janela, caixa, seu elenco e os jogadores dos outros clubes (só saves em andamento) |
| `POST` | `/simulacoes/{id}/propostas` (corpo JSON) | compra: `{jogador_id, valor}` → aceita / multa / contraproposta / recusada |
| `GET` | `/simulacoes/{id}/jogadores/{jogador_id}/ofertas` | venda: o que cada clube paga (seria titular? é rival?) |
| `POST` | `/simulacoes/{id}/vendas` (corpo JSON) | venda: `{jogador_id, clube}` aceita a oferta daquele clube (recalculada no servidor) |

Regras de negócio quebradas (caixa, elenco, janela fechada...) voltam `400` com o motivo em `detail`; temporada concluída, `409`.
