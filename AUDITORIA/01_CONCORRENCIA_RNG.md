# 01 — Concorrência, RNG e determinismo: investigação

**Data:** 17/11/2026 · **Branch:** `auditoria/01-concorrencia-rng` (a partir de `main` em `9c12e51`)
**Escopo:** reproduzir o R1 e o R2 do [reconhecimento](00_RECONHECIMENTO.md). Nenhuma linha de
produção foi alterada. Os resultados medidos estão em
[01_CONCORRENCIA_RESULTADOS.md](01_CONCORRENCIA_RESULTADOS.md).

**Arquivos criados**

| Arquivo | O que é |
|---|---|
| `backend/tests/auditoria/roteiro.py` | `Fio` (thread com nome que guarda resultado ou erro) e esperas com prazo |
| `backend/tests/auditoria/test_auditoria_r1_rng.py` | 4 reproduções do R1 + 3 controles |
| `backend/tests/auditoria/test_auditoria_r2_concorrencia.py` | 3 reproduções do R2 + 2 controles |
| `AUDITORIA/scripts/corrida_natural.py` | Corrida sem roteiro: HTTP contra um uvicorn de verdade, só biblioteca padrão |

Como rodar:

```bash
cd backend
python -m pytest tests/auditoria -rxX              # 5 passed, 7 xfailed (estado atual)
python -m pytest tests/auditoria --runxfail        # mostra a inconsistência de cada reprodução

# corrida natural: servidor com banco temporário + o script
TALDO_DB=/tmp/auditoria.db uvicorn app.main:app --port 8000 &
python -I ../AUDITORIA/scripts/corrida_natural.py http://127.0.0.1:8000 /tmp/auditoria.db 10
```

As reproduções afirmam o comportamento **correto** e estão marcadas
`xfail(strict=True)`. Hoje elas falham, e a suíte continua verde. Quando o
defeito for corrigido, elas passam a passar, e o `strict` transforma isso em
falha, para lembrar de tirar a marca.

---

## Regras seguidas

- Só arquivos novos: `git status` mostra apenas `AUDITORIA/` e `backend/tests/auditoria/`.
- Os testes usam o SQLite temporário do `conftest.py`. A corrida natural usa
  `TALDO_DB=/tmp/auditoria.db` dentro de um container descartável, com o
  repositório montado **só para leitura**.
- Nenhum acesso a banco de produção ou ao banco local de desenvolvimento.
- Os ganchos de sincronização entram por `pytest.MonkeyPatch.context()` dentro
  do teste e saem ao fim do roteiro.

---

## R1 — RNG global compartilhado entre requisições

### Hipótese

As rotas são `def` síncronas, e o FastAPI roda cada uma numa thread do pool.
O motor sorteia com o `random` **global** do processo. Uma requisição que
põe a corrente do save dela no `random` no meio da rodada de outra
requisição muda os sorteios da outra.

### Mapa do RNG [FATO]

**Quem sorteia no `random` global** (chamadas diretas `random.random/randint/choice/...`):

| Módulo | Chamadas |
|---|---|
| `domain/partida.py` | 42 (todo o jogo) |
| `domain/campeonato.py` | 2 (inclui `getrandbits(64)`, a semente da partida do técnico) |
| `domain/jogador.py` | 1 |
| `domain/copa.py` | 1 |

A virada passa o próprio módulo `random` como "rng" para `envelhecer`,
`aposentar`, `livres.cpu_contrata` e `livres.completar`
(`carreira_service.py:195-216`). Na prática, também é o global.

**Quem troca o estado do `random` global:**

| Onde | O quê | Quando roda |
|---|---|---|
| `domain/temporada.py:140` `restaurar_estado` | `setstate(blob["rng"])` | Toda reconstrução de save |
| `domain/temporada.py:73` `snapshot_estado` | `getstate()` → **vai para o blob** | Fim de `iniciar`, `avancar`, `_avancar_copa`, virada |
| `domain/campeonato.py:98-103` | `getstate` → `seed(semente)` → `setstate(fora)` | Partida do técnico, em toda rodada |
| `domain/copa.py:517-527` | idem | Jogo de copa ao vivo |
| `services/temporada_service.py:173-175` `iniciar` | `seed(seed)` ou `seed()` | Novo jogo |
| `services/simulacao_service.py:133-135` `_rodar` | `seed(...)` | Temporada inteira de uma vez |
| `services/carreira_service.py:173-175` | `seed(...)` | Virada |
| `services/temporada_service.py:275-280` `proxima_rodada` | `getstate` → restaura o save → `setstate` | **Leitura**: tela da rodada / Início |
| `services/temporada_service.py:444-449` `pre_jogo` | idem | **Leitura**: pré-jogo |
| `services/mercado_service.py:157-162` `_carregar` | idem | Mercado e **outros 11 serviços** que o usam (contrato, empréstimo, estádio, marketing, calendário, escalação, base, planos, olheiro, relatório, observados) |
| `services/transmissao_service.py:61-86` | idem (e re-simula a rodada) | Transmissão ao vivo, a cada pedido |
| `services/pos_jogo_service.py:342-347` | idem | Pós-jogo |

O padrão "leitura" (`getstate` → `setstate(save)` → `setstate(antigo)`) foi
feito para não deixar rastro. Isso vale com **uma** thread. Com duas, a
janela entre o `setstate(save)` e o `setstate(antigo)` vaza para a outra
thread, e o `setstate(antigo)` final ainda **rebobina** a outra thread para
um ponto anterior.

O `mercado_service._Contexto.gravar` se protege: regrava o `rng` lido do blob
(`mercado_service.py:99-102`). Já o `avancar` grava `random.getstate()` do
fim da rodada. Por isso uma interferência fica salva (ver resultados).

### Metodologia

**1. Roteiro determinístico** (`_intercalar`, em `test_auditoria_r1_rng.py`).
Duas threads com nome ("A" e "B") e quatro `threading.Event`. Os ganchos
envolvem `temporada_service.restaurar_estado` e `Partida.simular_partida`,
chamam a função original e só param quando o nome da thread manda:

1. A restaura o save dele (o `random` fica com a corrente de A) e para.
2. B entra numa **leitura de outro save** (`pre_jogo` ou `proxima_rodada`):
   `getstate` guarda a corrente de A, `restaurar_estado` põe a de B, e B
   para ali dentro.
3. A segue: sorteia a semente da partida do técnico, joga o 1º jogo da
   rodada com o `random` que está no processo (o de B) e para.
4. B termina: o `finally` devolve ao `random` a foto do passo 2.
5. A termina a rodada.

Esse é um entrelaçamento que o escalonador pode produzir sozinho: o GIL
troca de thread a cada ~5 ms e uma rodada leva centenas de ms. O roteiro só
garante que ele aconteça sempre, no mesmo ponto.

**Referência:** um save idêntico (mesma seed, mesmo clube) jogado sozinho.

**Controles** (precisam passar, senão o método inventaria diferença):
- mesma seed, sem leitura de outro save → mesma rodada;
- leitura de outro save em outra thread **sem sobrepor** → mesma rodada;
- transmissão sem interferência → jogo gravado = jogo transmitido (o
  invariante de `test_transmissao.py`).

**2. Corrida natural, sem roteiro** (`corrida_natural.py`). Um uvicorn de
verdade com as **8 ligas**, falando HTTP. Por tentativa:
- a rodada 1 de um save (seed `s`) jogada sozinha (referência);
- de novo sozinha (controle);
- de novo enquanto outro "técnico" abre `GET /rodadas/proxima` de outro
  save em laço.

São 10 tentativas, com seeds de 100 a 109.

**Limitação:** os testes de pytest usam o padrão do serviço, que é só a Liga
Taldo (20 clubes), para rodar em segundos. A corrida natural cobre as 8
ligas pela API.

### Possíveis soluções (não implementadas)

| # | Solução | Riscos |
|---|---|---|
| A | **RNG por save:** uma instância `random.Random` passada pelo motor (`Campeonato` → `Partida` → `Jogador`/`copa`) no lugar do módulo global. O blob continua igual, porque `Random.getstate()` tem o mesmo formato | É a mudança certa, mas grande: 46 chamadas diretas e as funções que recebem `random` como "rng". A **ordem** dos sorteios precisa ficar idêntica, senão os saves em andamento mudam de rumo, e a transmissão depende disso. Precisa de testes de regressão de placar por seed **antes** de mexer |
| B | **Trava global de processo** em volta de toda seção que toca o `random` global (restaurar → simular → snapshot), nas rotas de jogo e de leitura | Simples e rápida. Mas serializa todos os técnicos: uma rodada de ~0,75 s bloqueia as leituras dos outros. Uma trava não reentrante pode travar em chamadas aninhadas (serviço que chama serviço). Não vale com mais de um worker (hoje há 1). Aproveita para cobrir o `redirect_stdout` |
| C | Rotas de jogo como `async def` (rodam no event loop, uma de cada vez) | Funciona por acidente: bloqueia o event loop inteiro durante a simulação, inclusive os arquivos estáticos e o login. Não recomendo |
| D | Vários workers do uvicorn | **Não resolve**: dentro de cada processo continua havendo threads. Só reduz a chance |

Caminho provável: **B** como contenção de curto prazo e **A** como correção,
com testes de placar por seed antes.

---

## R2 — Nada impede dois pedidos de processar o mesmo turno

### Hipótese

O `avancar` lê o save, simula fora de transação e grava com
`UPDATE simulacao ... WHERE id = ?`, sem conferir a rodada lida. A tabela
`partida` não tem `UNIQUE`. Dois `POST /rodadas` no mesmo save jogariam a
mesma rodada duas vezes. Na virada, `sucessora()` é conferida antes da
transação de escrita, e na primeira virada (save sem carreira) nem há o que
conferir.

### Pontos do código [FATO]

- Rota: `POST /simulacoes/{id}/rodadas` → `temporada_service.avancar` (`routes.py:344-372`).
  Não há trava nem idempotência.
- `avancar`: `buscar` (`temporada_service.py:489`) → simula → `with conn:`
  (`:620`) → `atualizar_estado(... WHERE id = ?)` (`simulacao_repository.py:41-57`).
- O SQLite está no modo padrão do `sqlite3`: a transação só abre na primeira
  escrita, e `timeout=15` faz a segunda escrita **esperar e seguir**, não falhar.
- O frontend desabilita o botão "Jogar" (`rodada.js:421`). Isso não cobre duas
  abas, duplo envio de rede nem outro cliente.
- Virada: `POST /simulacoes/{id}/proxima-temporada` →
  `carreira_service.proxima_temporada`: `sucessora()` (`:131`) e o cargo
  (`:135`) vêm antes de `with conn:` (`:157`).

### Metodologia

**1. Roteiro determinístico** (`test_auditoria_r2_concorrencia.py`). Duas
threads no **mesmo** save:
- uma barreira (`threading.Barrier(2)`) logo antes do bloco de escrita
  garante que as duas leram o estado inicial antes de qualquer gravação;
- uma trava em volta da simulação (restaurar → serializar) faz uma simular de
  cada vez, para o R1 não contaminar a medida;
- depois da barreira, as duas gravam como em produção.

São contadas as partidas por rodada, os lances, as atuações, as mensagens e
a `rodada_atual`, comparadas com o mesmo save jogando uma rodada sozinho.

**Virada:** a barreira fica no `cargo_da_temporada` (logo depois da checagem
de `sucessora()`). São dois cenários: save da temporada 1 **sem** carreira, e
save que já é a temporada 1 de uma carreira (carreira criada pelos
repositórios na preparação do teste).

**Controles:**
- dois avanços em sequência jogam as rodadas 1 e 2;
- a segunda virada em sequência é recusada com `CarreiraInvalida`.

**2. Corrida natural** (`corrida_natural.py`). Dois `POST /rodadas` soltos
juntos por uma barreira no **cliente**, 10 tentativas, 8 ligas. A contagem é
feita com leitura só (`mode=ro`) no banco temporário.

### Possíveis soluções (não implementadas)

| # | Solução | Riscos |
|---|---|---|
| A | **Concorrência otimista:** `UPDATE simulacao SET ... WHERE id = ? AND rodada_atual = ?` (ou uma coluna `versao`) **como primeira escrita** da transação. Se `rowcount = 0`, levantar exceção → `with conn` desfaz tudo → 409 | Barata e localizada. Mas **todo** escritor do blob precisa usar a mesma versão (mercado `gravar`, escalação, calendário, base, transmissão...), senão sobram atualizações perdidas entre esses fluxos e o `avancar`. O perdedor simulou à toa (custo de CPU) |
| B | `BEGIN IMMEDIATE` antes de ler o save, segurando a escrita durante a simulação | Correto, mas trava o **banco inteiro** (todos os técnicos) por ~0,75 s+ por rodada. Sob carga, as outras escritas estouram o `timeout=15` com "database is locked" |
| C | **Trava por save em memória** (`dict[simulacao_id] → Lock`) na rota/serviço, relendo o estado depois de pegar a trava | Simples e não bloqueia os outros saves. Só vale com **1 processo** (hoje é assim). Uma trava esquecida num caminho novo reabre o buraco |
| D | **Rede de segurança no banco:** `UNIQUE(simulacao_id, rodada, mandante_id)` em `partida` e `UNIQUE(carreira_id, temporada)` em `simulacao` | Não evita o trabalho duplicado, só a gravação dupla (vira erro 500 se não for tratado). **A migração falha se a produção já tiver duplicatas**: é preciso verificar antes, numa cópia do backup. Uma partida de copa ou caso especial com a mesma chave precisa ser mapeado |
| E | Chave de idempotência no `POST` (o frontend manda um id por clique) | Resolve duplo envio de rede, mas não duas abas com ações diferentes. Complementar, não substituto |

Caminho provável: **A** (ou **C**) mais **D** como rede de segurança,
depois de checar se a produção já tem duplicatas.

---

## Achados colaterais (não pedidos, registrados)

1. **`redirect_stdout` não é thread-safe [FATO, observado].** Na corrida
   natural, 14 blocos de texto do motor ("⭐ MELHOR EM CAMPO", 13 "=== ESCALAÇÃO
   ===") vazaram para a saída do servidor. Uma thread restaura o
   `sys.stdout` enquanto a outra ainda imprime. O efeito em si é baixo (log
   sujo), mas confirma que as requisições correm de fato em paralelo no
   processo.
2. **O isolamento do banco nos testes depende do `monkeypatch` [FATO].**
   O `conftest.py` aponta `TALDO_DB` para um arquivo temporário com o
   `monkeypatch` do teste. Na primeira versão destes testes, um
   `monkeypatch.undo()` desfez isso e a conexão seguinte foi para o **banco
   padrão** (`backend/data/database/taldo_manager.db`). Só não criou nem tocou
   em nada porque o repositório estava montado só para leitura no container.
   Corrigido nos testes de auditoria com `MonkeyPatch.context()` próprio. Um
   teste futuro pode cometer o mesmo erro numa máquina de desenvolvimento.
   Uma guarda simples (falhar se `TALDO_DB` não estiver definido durante os
   testes) fecharia isso.
3. **Hipótese a investigar: atualização perdida entre fluxos.** Uma compra
   (`mercado_service`) e o `avancar` no mesmo save, ao mesmo tempo, fazem
   leitura-modificação-escrita do blob inteiro. O último a gravar apaga o
   outro. Não foi reproduzido nesta bateria.
