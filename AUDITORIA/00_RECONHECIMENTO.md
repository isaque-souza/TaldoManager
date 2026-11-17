# 00 — Reconhecimento técnico do TaldoManager (v2.6)

**Data:** 17/11/2026 · **Commit analisado:** `9c12e51` (main) · **Escopo:** só leitura.
Nenhum arquivo do projeto foi alterado. Os testes rodaram num container
descartável (`python:3.12-slim`) com o repositório montado só para leitura,
cada teste num SQLite temporário (`tests/conftest.py`).

**Legenda**

- **[FATO]** — visto no código, ou medido rodando.
- **[HIPÓTESE]** — conclusão provável a partir do código, ainda não reproduzida.
  Precisa de prova na auditoria aprofundada.

---

## 1. Arquitetura encontrada

| Camada | Onde | Tamanho [FATO] | Papel |
|---|---|---|---|
| API | `backend/app/api/` | 3.379 linhas (`routes.py` 1.297, `schemas.py` 1.960 com 190 classes, `contas.py` 122) | FastAPI. Rotas `def` síncronas, schemas Pydantic e login por cookie |
| Serviços | `backend/app/services/` | 7.418 linhas, 24 módulos | Orquestram o caso de uso: abrem conexão, restauram o campeonato, chamam o domínio e gravam |
| Domínio (motor) | `backend/app/domain/` | 10.061 linhas, 38 módulos | Regras do jogo em Python puro: `Partida` (1.757), `caixa` (940), `copa` (659), `Campeonato` (613)... |
| Repositórios | `backend/app/repositories/` | 1.552 linhas, 22 módulos | SQL à mão (`sqlite3`), um módulo por tabela |
| Banco | `backend/app/db/` | `schema.sql` 448, `conexao.py` 265 | Schema `CREATE IF NOT EXISTS` + migrações ad hoc na subida |
| Seeds/carga | `backend/scripts/` + `backend/data/seeds/` | 2.303 linhas; 8 ligas × 20 clubes, 3.679 jogadores | `data_loader.py` é usado **em produção** pelos serviços; os outros scripts geram ou importam seeds |
| Frontend | `frontend/` | JS 8.797 (40 módulos ES), CSS 2.549, HTML 577 | Sem build e sem framework, servido pela própria API (`StaticFiles` em `/`) |
| Deploy | `deploy/`, `Dockerfile` | 60 linhas | 1 container (uvicorn, 1 worker), volume `/dados`, Caddy na frente, cron de auto-deploy a cada 5 min |
| Testes | `backend/tests/` | 14.551 linhas, 75 arquivos | pytest, banco temporário por teste, `TestClient` do FastAPI |

**Dependências [FATO]:** `fastapi==0.141.1`, `uvicorn[standard]==0.52.4`,
`pydantic==2.13.5`, `pytest==9.1.1` e `httpx2==2.12.0`, todas fixadas. Não
existem lockfile, linter, type checker, CI (`.github/` não existe) nem testes
de frontend.

**Arquivos vazios [FATO]:** `app/core/exceptions.py` e
`app/services/campeonato_service.py` (0 linhas).

**Modelo de estado [FATO]:** um save (`simulacao`) em andamento guarda o
**estado vivo do motor num blob JSON** (`simulacao.estado_json`, ver
`app/domain/temporada.py:snapshot_estado`). O blob inclui o estado do RNG
global (`random.getstate()`). As tabelas relacionais (`clube`, `jogador`,
`partida`, `lance`, `atuacao`...) guardam a **projeção** para consulta. A cada
ação, o serviço recria o campeonato a partir das seeds JSON, aplica o blob por
cima (`restaurar_estado`), joga e regrava blob e tabelas.

---

## 2. Mapa dos módulos

### 2.1 Dependências entre camadas [FATO, por análise de imports]

```
frontend (fetch)  ──HTTP──▶  api/routes.py ─┬─▶ services/*  ─┬─▶ domain/*   (sem I/O)
                             api/contas.py ─┘                ├─▶ repositories/* ─▶ db/conexao.py ─▶ SQLite
                                                             └─▶ scripts/data_loader.py ─▶ data/seeds/*.json
```

- O domínio **não** importa serviço, repositório nem banco. A separação está limpa.
- Os repositórios não importam serviços.
- A camada `app` depende de `scripts/`: `routes`, `simulacao_service`,
  `temporada_service`, `carreira_service`, `mercado_service`,
  `transmissao_service` e `pos_jogo_service` importam `scripts.data_loader`.
  Ou seja, o carregador das seeds faz parte do runtime, mas mora fora de `app/`.
- Há ciclos diretos de import entre serviços, contornados com import dentro da
  função (9 lugares comentados "evita import circular"):
  `temporada_service ↔ base_service`, `temporada_service ↔ olheiro_base_service`,
  `temporada_service ↔ plano_service`, `carreira_service ↔ base_service`,
  `base_service ↔ olheiro_base_service` e `mercado_service ↔ emprestimo_service`.
- Funções "privadas" usadas de fora do módulo: `simulacao_service._configurar_clube` (6×),
  `_serializar` (5×), `_montar_visao` (2×), `_cru_do_banco` (2×), `mercado_service._carregar` (4×)...
  Na prática, `simulacao_service` é uma biblioteca compartilhada com API implícita.
- Serviços mais importados por outros serviços: `mercado_service` (11),
  `temporada_service` (8), `simulacao_service` (6) e `copa_service` (5).

### 2.2 Módulos-chave

| Módulo | Responsabilidade principal |
|---|---|
| `domain/partida.py` | Simula 90 min + acréscimos: ataque, finalização, faltas, cartões, lesões, substituições, decisões do técnico ao vivo, notas |
| `domain/campeonato.py` | Calendário (v1/v3 sorteado), `jogar_rodada` das 8 ligas lado a lado, classificação por liga, copas no meio da semana |
| `domain/copa.py` | `Copa`/`Copas`, chaveamento, pênaltis e o isolamento da liga (`_isolar_da_liga`) |
| `domain/temporada.py` | Snapshot e restauração do estado vivo (incluindo o RNG) |
| `domain/carreira.py`, `divisoes.py`, `evolucao.py`, `livres.py` | Virada: envelhecer, aposentar, contratos, acesso e rebaixamento |
| `domain/caixa.py` | Mensagens da caixa de entrada (940 linhas de texto e regra misturados) |
| `services/temporada_service.py` | `iniciar`, `proxima_rodada`, `pre_jogo`, **`avancar`** (o turno do jogo) e `_avancar_copa` |
| `services/simulacao_service.py` | Temporada inteira de uma vez, serialização motor→linhas, visão da temporada, consultas |
| `services/carreira_service.py` | **`proxima_temporada`** (a virada) |
| `services/transmissao_service.py` | Jogo ao vivo: re-simula a partida do técnico até o minuto pedido |
| `services/mercado_service.py` | Compra, venda, negociação em 2 etapas, livres e lista (1.345 linhas, o maior serviço) |
| `services/calendario_service.py` | Dia a dia, "Continuar" até o próximo evento, ofertas no caminho |

---

## 3. Fluxo de execução do jogo

### 3.1 Como uma partida é simulada [FATO]

`Campeonato.jogar_rodada` → `Partida(clube1, clube2)` → `partida.publico = estadio.publico(...)`
→ `partida.simular_partida()` (`preparar_partida` → `executar_simulacao` minuto
a minuto → `finalizar_partida`: notas, estatísticas, classificação, clean sheets)
→ `Campeonato.registrar_partida`.

- O RNG é o **módulo global `random`**. A partida do técnico roda numa
  sub-corrente própria: `semente = random.getrandbits(64)` antes da rodada, e
  `random.seed(semente)`/`setstate(fora)` em volta dela
  (`campeonato.py:79-103`). Assim, uma decisão ao vivo do técnico não muda os
  outros jogos.
- O domínio usa `print()` (escalação, eventos, resultado). Os serviços abafam a
  saída com `contextlib.redirect_stdout(io.StringIO())`.

### 3.2 Como uma rodada é processada (`temporada_service.avancar`) [FATO]

1. `conectar()` → `simulacao_repo.buscar`. Se o estado não for `em_andamento`, levanta `TemporadaConcluida`.
2. Se `copa_pendente`, o fluxo desvia para `_avancar_copa` (o jogo de copa do técnico, "na quarta").
3. `carregar_campeonato_do_save(sim)` relê **as seeds das 8 ligas do disco** e
   `restaurar_estado` aplica o blob (inclusive `random.setstate`).
4. Configura o clube do técnico (tática, formação, XI, posicionamento).
5. `campeonato.jogar_rodada(..., adiar_copa=True)` joga todas as ligas e as
   fases de copa do dia em que o técnico não joga.
6. Monta as mensagens (caixa de entrada), resolve as disputas perdidas (v1.9),
   o sonho recusado e a janela da CPU (`mercado_cpu.negociar`).
7. `_serializar` transforma o motor em dicts de linhas.
8. Numa transação (`with conn:`): data do calendário, relatórios dos olheiros,
   treino da base, `UPDATE` de clubes e jogadores (por `(simulacao_id, nome)`),
   `INSERT` de partidas, lances e atuações, expiração de negociações e ofertas,
   mensagens, ofertas novas, `copa_pendente` e, por fim, `atualizar_estado`
   (novo blob ou `concluida`).
9. `_montar_visao(_cru_do_banco(...))` relê tudo do banco para a resposta.

### 3.3 Como as 8 ligas são orquestradas [FATO]

- `scripts/data_loader.LIGAS` define as 8. Todo jogo novo usa `TODAS_AS_LIGAS`.
  Os saves antigos guardam `simulacao.ligas` (NULL = só a Taldo).
- Cada clube tem `liga`. O calendário é o turno e returno de cada liga lado a
  lado (a rodada N joga todas). A classificação, a premiação e a meta são por liga.
- Acesso e rebaixamento ficam em `domain/divisoes.py` (4 sobem, 4 caem por
  país), aplicados só na virada.
- Os livres de todas as ligas formam uma lista única.

### 3.4 Como as copas são processadas [FATO]

- `Copas` agrupa a continental e as 4 nacionais. Cada fase tem a chave
  `"copa:fase"` e uma rodada da liga depois da qual é jogada.
- Na rodada, as fases sem o técnico saem na hora. A fase com o técnico vira
  `copa_adiada` → `simulacao.copa_pendente`, e o próximo `POST /rodadas` joga
  só ela (`_avancar_copa`) sem andar a liga.
- O jogo de copa é uma `Partida` comum dentro de `_isolar_da_liga`: tira uma
  foto de **todo atributo int/float/bool** dos clubes e jogadores e, na saída,
  devolve tudo menos `FICA_DA_COPA = {"energia", "rodadas_lesao"}` (`copa.py:104, 568-600`).
- `copa.normalizar` converte saves antigos (copa Taldo × Premier) para o formato novo.

### 3.5 Como a carreira avança de temporada (`carreira_service.proxima_temporada`) [FATO]

Valida (concluída, com clube, sem sucessora, sem demissão). Lê as tabelas
finais e, dentro de `with conn:`, faz: `random.seed(seed_da_temporada)` → seeds
das ligas da virada (o mundo cresce para 8 ligas) → nomes sem repetição →
acesso e rebaixamento → envelhecer → história/ídolos → aposentar → contratos →
CPU contrata livres → base → completar livres → sonhos → obras da CPU →
migração de economia v1→v2 → novo calendário → copas pela tabela anterior →
novo `simulacao` + clubes + jogadores + movimentos + mensagens + ofertas →
copiar planos, observados, base e olheiros da base.

### 3.6 Como o frontend consome a API [FATO]

- `js/nucleo.js` guarda o estado global da tela (`estado`), a pilha do
  "Voltar" e `pedir()` (fetch + tratamento de 401 e erro).
- 7 módulos também chamam `fetch` direto (rodada, mercado, marketing, editor,
  estádio, base, aovivo).
- Caminhos relativos e cookie HttpOnly (`SameSite=Lax`) no mesmo endereço, então não há CORS.
- Os módulos se importam em ciclo (`nucleo.js` importa `temporada.js`,
  `rodada.js`, `clube.js`..., que importam `nucleo.js`). Com ES modules e só
  funções, isso funciona.

---

## 4. Fluxo de persistência

### 4.1 Gravação [FATO]

- **Toda ação de jogo grava na hora.** Não existe "salvar" manual: o save é o
  banco. Rodada, compra, renovação e obra fazem cada uma seu próprio
  `conectar()` e `with conn:` (79 chamadas a `conectar()` em 21 serviços).
- **Autosave da escalação (v0.9):** `js/rodada.js:458-545`. 800 ms sem mudança
  → `PATCH /simulacoes/{id}/decisao`. As chamadas são encadeadas numa promise
  (`emVoo`), e `pagehide` manda o pendente com `keepalive`. Antes de jogar, o
  pendente é cancelado e vai junto no corpo do `POST /rodadas`.
- Transações: `sqlite3` no modo padrão (transação *deferred*, aberta no
  primeiro write). Não há `BEGIN IMMEDIATE`, WAL nem lock por save. O `timeout=15`
  em `conectar()` só faz uma escrita esperar a outra.
- Em `avancar`, a leitura (`buscar`) e toda a simulação acontecem **fora** da
  transação de escrita. O `UPDATE simulacao ... WHERE id = ?` não confere a
  rodada que foi lida.
- O jogador é identificado **pelo nome** dentro do save: `UPDATE ... WHERE
  simulacao_id = ? AND nome = ?`. Quem não vem na lista é marcado `livre = 1`
  (`jogador_repository.py:58-107`). O índice `(simulacao_id, nome)` **não é UNIQUE**.
- `partida` não tem UNIQUE por `(simulacao_id, rodada, mandante)`.

### 4.2 Recuperação de saves antigos [FATO]

- `init_db()` roda a cada subida da API (lifespan) e em todo teste:
  `executescript(schema.sql)` + `_migrar`.
- `_migrar`:
  - recria `transferencia` (v1.7), desligando `foreign_keys` e dando `commit` no meio;
  - adiciona as 84 colunas de `_COLUNAS_NOVAS` quando faltam;
  - aplica 2 `UPDATE`s de normalização;
  - `_renomear_jogadores`: `REPLACE` de nomes em **toda coluna TEXT de toda
    tabela**, inclusive JSONs, uma vez só (controlado por `PRAGMA user_version = 1`).
- Não há tabela de versão de migração. Só o `user_version`, usado para uma única migração.
- No nível do blob: `restaurar_estado` tolera blobs antigos (versão do
  calendário, ligas que mudaram). `copa.normalizar` converte a copa antiga;
  `economia` 1→2 migra na virada; `ligas_do_save` dá o padrão "só a Taldo".
- Em produção, o `deploy/atualizar.sh` faz backup (`sqlite3.backup`) antes do
  `git pull` e do build. As migrações rodam sozinhas quando o container sobe.

---

## 5. Estado dos testes

### 5.1 Números

| Medida | Valor |
|---|---|
| Testes coletados pelo pytest **[FATO, medido]** | **994** (o README dizia ~960; contei 957 funções `test_` mais parametrizações) |
| Distribuição (funções `test_`) **[FATO]** | domain 489 · services 380 · api 59 · raiz/seeds 17 · db 8 · repositories 4 |
| Arquivos com mais testes | `api/test_rotas.py` 48 · `domain/test_partida.py` 34 · `services/test_estadio.py` 33 · `test_simulacao_service.py` 28 · `test_carreira_service.py` 28 |
| Resultado da execução **[FATO, medido]** | **994 passed**, 0 falhas, 0 erros. 1 `skip` condicional existe no código, mas não disparou nesta seed |
| Cobertura de linhas de `app/` **[FATO, medido]** | **96%** (9.636 de 10.024 linhas) |

### 5.2 Execução e cobertura [FATO, medido]

Execução: `pytest --cov=app --cov=scripts` em `python:3.12-slim` (Docker no
macOS, com cobertura ligada) levou **26 min 37 s**. Sem cobertura e fora do
Docker deve ser mais rápido; não medi.

| Camada | Cobertura de linhas |
|---|---|
| `app/db` | 100% |
| `app/repositories` | 100% (369/370) |
| `app/domain` | 97% (4.121/4.267) |
| `app/services` | 96% (3.100/3.236) |
| `app/api` | 95% (1.952/2.055) |
| `scripts/` | 25%: os geradores e importadores de seed (`gerar_ligas`, `importar_brasileirao`, `baixar_*`, `gerar_*`, `ampliar_elencos`) têm 0%. São ferramentas offline |

Arquivos de `app/` com menor cobertura:

| Arquivo | Cobertura |
|---|---|
| `domain/campeonato.py` | 76% (58 linhas sem teste, boa parte são os `mostrar_*` de console) |
| `api/routes.py` | 81% (103 linhas, em geral os ramos de erro 400/404/409) |
| `domain/clube.py` | 86% |
| `domain/relatorio.py` | 88% |
| `services/emprestimo_service.py` | 88% |
| `services/plano_service.py` | 91% |

Ressalvas:

- A medida é de **linha**, não de ramo (branch).
- Cobertura alta aqui quer dizer "a linha rodou", não "o resultado foi
  conferido" (ver os falsos positivos abaixo).
- Nenhum teste exercita concorrência, então R1 e R2 não aparecem em cobertura nenhuma.

Tempo: os 30 testes mais lentos somam **865 s (54% do total)**. São quase
todos de API e carreira que jogam temporadas inteiras com 8 ligas. O mais
lento é `test_rodada_a_rodada_ate_o_fim_via_api`, com 77 s. Uma suíte de quase
meia hora desestimula rodar tudo antes de cada commit, e isso agrava o R3.

### 5.3 Qualidade da suíte

- **Isolamento [FATO]:** fixture `autouse` aponta `TALDO_DB` para um arquivo
  temporário e roda `init_db()`. O banco real nunca é tocado. O login é
  desligado por `dependency_overrides` fora de `test_contas.py`.
- **Integração [FATO]:** a maioria dos testes de `services/` e `api/` são
  testes de integração reais: criam save, jogam rodadas e temporadas inteiras
  (`_jogar_ate_o_fim`) e viram temporada, contra SQLite de verdade.
- **Regressão e determinismo [FATO]:** há testes que comparam dois saves com a
  mesma seed (ex.: `test_contexto_nao_muda_o_resultado_da_rodada_adiante`) e
  testes de migração (`db/test_conexao.py`: colunas novas, `transferencia`
  refeita, nomes trocados).
- **Fragilidade por seed [FATO]:** o próprio `conftest.py` tem
  `cargo_garantido`, criado porque "com a seed fixa, o técnico pode acabar
  demitido... a cada ajuste do motor". `test_transmissao.py:334` faz
  `pytest.skip("sem zagueiro no banco nesta seed")`. Mudanças no motor podem
  quebrar ou pular testes que não têm a ver com a mudança.
- **Possíveis falsos positivos [FATO no código; impacto = HIPÓTESE]:** 46
  testes só têm `assert` dentro de `for`/`if`. Quando a coleção vem vazia, eles
  passam sem verificar nada. Dois exemplos:
  - `test_carreira_service.py:296 test_aposentados_somem_da_temporada_seguinte`
    não exige que alguém tenha se aposentado;
  - `test_pre_jogo.py:153 test_desfalque_nao_aparece_no_xi` não exige que
    tenha havido algum desfalque.
  Muitos dos 46 percorrem seeds que nunca vêm vazias e estão corretos; a lista
  precisa de triagem.
- **Duplicados [FATO]:** não há nomes repetidos no mesmo arquivo (nenhum teste
  é sombreado). Há 2 nomes repetidos entre arquivos (domínio × serviço), o que
  é esperado.
- **Lacunas [FATO]:**
  - nenhum teste de concorrência (nenhum uso de thread ou async nos testes);
  - nenhum teste de frontend;
  - nenhum teste de deploy, backup ou restore;
  - `repositories/` tem só 4 testes diretos (eles são exercitados
    indiretamente pelos serviços).

---

## 6. Principais riscos técnicos

Ordenados por gravidade estimada.

### R1 — RNG global compartilhado entre requisições simultâneas (alto)

- **[FATO]** As rotas são `def` síncronas, então o FastAPI as roda num pool de
  threads e várias requisições correm em paralelo no mesmo processo.
- **[FATO]** O motor usa o `random` global. `avancar` faz `setstate(blob)` e
  depois simula. Leituras como `proxima_rodada`, `pre_jogo`,
  `mercado_service._carregar` e `transmissao_service` fazem
  `getstate → setstate(blob do save delas) → setstate(antigo)`
  (`temporada_service.py:275-280, 445-450`, `mercado_service.py:156-161`,
  `transmissao_service.py:65-86`). A virada faz `random.seed(...)`.
- **[HIPÓTESE]** Com dois técnicos jogando ao mesmo tempo, ou o mesmo técnico
  com uma leitura em voo, uma thread troca o estado do RNG no meio da simulação
  da outra. Consequências prováveis:
  - resultados não reproduzíveis;
  - a transmissão ao vivo, que **re-simula** a partida esperando o mesmo
    resultado, pode divergir do que foi gravado;
  - o pré-jogo pode prever um público ou escalação diferente do apito.
- **[FATO]** O `redirect_stdout` também troca o `sys.stdout` global, que não é
  thread-safe. O efeito é baixo (só os prints).

### R2 — Turno sem controle de concorrência no mesmo save (alto)

- **[FATO]** `avancar` lê o save, simula fora da transação e grava com
  `UPDATE ... WHERE id = ?`, sem conferir `rodada_atual`.
- **[FATO]** `partida` não tem constraint UNIQUE.
- **[FATO]** O frontend desabilita o botão "Jogar" (`rodada.js:421`), mas duas
  abas ou um retry da rede passam.
- **[HIPÓTESE]** Dois `POST /rodadas` quase simultâneos no mesmo save jogariam
  a mesma rodada duas vezes: partidas, lances e atuações duplicadas, e o último
  blob vence.
- **[FATO]** O mesmo padrão aparece na virada: `sucessora()` é conferida antes
  da transação. **[HIPÓTESE]** Dois `POST` de "Próxima temporada" criariam duas
  "temporada 2".

### R3 — Auto-deploy da main sem portão de testes (alto, operacional)

- **[FATO]** O cron na VPS publica qualquer commit novo da `main` a cada 5 min.
  Não há CI, a imagem não leva os testes (`.dockerignore` exclui
  `backend/tests`), e as migrações rodam sozinhas no banco de produção ao subir.
- O backup antes de atualizar existe, mas um `|| true` deixa a atualização
  seguir se o backup falhar (`atualizar.sh:5`).

### R4 — Identidade do jogador pelo nome (médio-alto)

- **[FATO]** Os saves ligam jogador ↔ linha por `(simulacao_id, nome)` e por
  `(clube, nome)` nos mapas. Há código dedicado a evitar nomes repetidos
  (`_sem_nomes_repetidos`, `renomeados.py`, `_nomes_usados`). A migração de
  nomes faz `REPLACE` textual no banco inteiro.
- **[HIPÓTESE]** Qualquer caminho que gere dois jogadores com o mesmo nome no
  mesmo save (base, livres gerados, importação nova) faz o `UPDATE` atingir as
  duas linhas, corrompendo estatísticas e clube em silêncio.

### R5 — Isolamento da copa por "foto e devolve" (médio)

- **[FATO]** `_isolar_da_liga` reverte **todo** atributo numérico de clube e
  jogador, menos `energia` e `rodadas_lesao`.
- **[HIPÓTESE]** Qualquer atributo numérico novo que deveria mudar num jogo de
  copa (fama, humor, titularidades, contadores de papel, dinheiro aplicado
  durante o jogo) é desfeito em silêncio, a menos que alguém lembre de
  incluí-lo em `FICA_DA_COPA` ou de aplicá-lo depois do bloco.

### R6 — Estado duplicado entre blob e tabelas (médio)

- **[FATO]** O mesmo dado vive no `estado_json` e nas tabelas. Os serviços de
  leitura usam um ou outro. Toda ação reconstrói o mundo a partir das seeds do
  disco + blob.
- **[HIPÓTESE]**
  - Uma seed alterada num deploy muda saves em andamento, onde o blob não
    cobre o campo.
  - Divergência blob × tabela depois de falha parcial.
  - Custo de CPU por requisição: 8 ligas recarregadas do JSON a cada GET de
    pré-jogo ou mercado.

### R7 — Acoplamento e responsabilidades misturadas (médio)

- **[FATO]**
  - `avancar` tem ~260 linhas e mistura motor, mercado, disputas, base,
    olheiros, mensagens e persistência.
  - `simulacao_service` serve de biblioteca com funções `_privadas` usadas por
    outros módulos.
  - Há 6 ciclos de import entre serviços.
  - `domain/caixa.py` (940 linhas) mistura texto e regra.
  - `schemas.py` tem 1.960 linhas.
  - O domínio faz `print`.
  - `scripts/data_loader` é runtime.
- O efeito é que fica difícil testar uma regra sem jogar uma rodada inteira.

### R8 — Tratamento de erro inconsistente (baixo-médio)

- **[FATO]**
  - Há 21 classes de exceção, parte herdando de `ValueError` e parte de
    `Exception`.
  - "Não encontrado" é sinalizado por `return None`.
  - Cada rota traduz para HTTP à mão (`_erro_de_valor`, `_erro_de_mercado`,
    `_erro_transmissao`, `_resposta_oferta`...).
  - `core/exceptions.py` está vazio.
  - Não há `except Exception` genérico (bom sinal).
- No frontend, `pedir()` mostra "A API está rodando?" para qualquer erro HTTP,
  inclusive 400 e 409.

### R9 — Migrações sem versionamento (baixo-médio)

- **[FATO]** O esquema evolui por "adiciona a coluna se faltar". Só a
  renomeação usa `user_version`. A recriação de `transferencia` dá `commit`
  no meio do `init_db`.
- **[HIPÓTESE]** Uma migração que falhe no meio deixa o banco num estado
  intermediário sem marca. A ordem das migrações não está registrada.

---

## 7. Pontos que precisam de investigação aprofundada

1. **Reproduzir R1:**
   - teste com 2 threads, uma em `avancar` e outra em `pre_jogo` de outro
     save, comparando o placar com uma execução isolada da mesma seed;
   - medir se a transmissão diverge do resultado gravado.
2. **Reproduzir R2:** dois `POST /rodadas` concorrentes no mesmo save, e dois
   `POST /carreiras/...` de virada. Contar as partidas por rodada.
3. **Mapear todos os pontos que tocam o RNG global.** Avaliar se o motor já
   aceita receber um `random.Random` próprio por save.
4. **Unicidade de nomes:** varrer saves gerados em carreiras longas (10+
   temporadas, 8 ligas) procurando `(simulacao_id, nome)` duplicado.
5. **`_isolar_da_liga`:** listar os atributos numéricos de `Clube` e `Jogador`
   e conferir quais deveriam sobreviver a um jogo de copa.
6. **Triagem dos 46 testes** com `assert` só em laço ou condição: quais podem
   passar vazios.
7. **Cobertura por módulo** (seção 5.2): aprofundar nos módulos de pior cobertura.
8. **Migrações:** subir o código atual contra cópias de bancos de versões
   antigas (v1.0, v1.6, v2.0, v2.5) e conferir o resultado.
9. **Desempenho:** perfil de `avancar`, `pre_jogo` e `mercado` com 8 ligas. A
   recarga das seeds a cada requisição é um suspeito.
10. **Segurança:**
    - conferir se toda rota com `simulacao_id`/`carreira_id`/ids filhos passa
      por `exigir_dono` (ex.: um `partida_id` de outro save sob o meu
      `simulacao_id`);
    - revisar o limitador de tentativas em memória.

---

## 8. Recomendações para a próxima etapa

Só diagnóstico. Nada disto foi feito.

1. **Auditoria 01 — Concorrência e determinismo (R1, R2):** escrever primeiro
   os testes que reproduzem (vermelhos), depois decidir a correção. Opções
   prováveis:
   - lock por save;
   - `BEGIN IMMEDIATE` + `WHERE rodada_atual = ?`;
   - RNG por instância.
2. **Auditoria 02 — Persistência e migrações (R4, R6, R9):**
   - unicidade de nomes;
   - coerência blob × tabelas;
   - teste de migração com bancos antigos reais;
   - versionamento das migrações.
3. **Auditoria 03 — Testes:**
   - triagem dos falsos positivos;
   - cobertura dos módulos fracos;
   - reduzir a dependência de seed fixa (`cargo_garantido`, `skip`).
4. **Operação (R3):** CI mínima (pytest na PR) e o deploy só depois dela;
   backup obrigatório (sem `|| true`).
5. **Arquitetura (R5, R7, R8):** depois das anteriores, porque mexer na
   estrutura antes de ter os testes de concorrência e persistência aumenta o
   risco.
