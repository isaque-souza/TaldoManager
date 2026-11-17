# 01 — Concorrência, RNG e determinismo: resultados

**Data:** 17/11/2026 · **Branch:** `auditoria/01-concorrencia-rng` · **Base:** `main` em `9c12e51`.
Metodologia, mapa do RNG e soluções: [01_CONCORRENCIA_RNG.md](01_CONCORRENCIA_RNG.md).

**Ambiente:** Docker `python:3.12-slim` com as dependências de
`requirements.txt`. Repositório montado só para leitura. Banco: o SQLite
temporário do `conftest.py` (testes) e `/tmp/auditoria.db` no container
(corrida natural).

## Placar

| Risco | Veredito | Roteiro determinístico | Corrida natural (HTTP, 8 ligas, sem ganchos) |
|---|---|---|---|
| **R1** RNG global | **Reproduzido** | 4 de 4 cenários, em 5 de 5 execuções, com a mesma diferença sempre | **10 de 10** tentativas divergiram (54 a 78 dos 80 jogos); controle: 0 |
| **R2** rodada dupla | **Reproduzido** | 1 de 1, em 5 de 5 execuções | **10 de 10** tentativas gravaram a rodada 1 duas vezes |
| **R2** virada dupla | **Reproduzido** | 2 de 2 cenários, em 5 de 5 execuções | Não testado por HTTP |

Estado da suíte de auditoria: `5 passed, 7 xfailed` (os 5 controles passam e
as 7 reproduções falham como esperado). Os 994 testes originais não foram
tocados.

---

## R1 — RNG global compartilhado

### Evidências do roteiro determinístico

Saída de `pytest tests/auditoria --runxfail`. Seed 5, com o 1º clube de
`listar_clubes()` como clube dirigido; o outro técnico está no save de seed 99.

**1. Leitura do pré-jogo de outro save no meio da rodada** (`test_r1_pre_jogo_...`)

> 10 de 10 jogos mudaram (referência → intercalado):
> Sport Taldo × Taldo Legends 4×0 → **4×1** · Atlético Taldo × Taldo Stars 4×0 → **3×2** ·
> Taldo Internacional × FC Taldo 1×1 → **2×0** · Taldo Sporting × EC Taldo 2×0 → **3×1** ·
> Taldo City × Taldo Rangers 3×1 → **1×0** · Taldo Athletic × Taldo Galaxy 0×0 → **1×2** ·
> Taldo Dragons × Taldo Empire 1×2 → **2×1** · Taldo Royals × Taldo United 3×3 → **0×2** ·
> Taldo Nacional × Taldo FC 3×0 → **2×0** · Real Taldo × Taldo Warriors 4×0 → **3×1**

**2. A tela da rodada de outro save no meio da rodada** (`test_r1_proxima_rodada_...`).
É a leitura mais comum do jogo, e o resultado foi o mesmo: a rodada saiu diferente.
O primeiro jogo diferente foi Sport Taldo × Taldo Legends, 4×0 → 4×1.

**3. O técnico assiste a um jogo e o banco grava outro** (`test_r1_o_jogo_gravado_...`)

> transmissão **1×1** × gravado **2×0**; eventos transmitidos 10, gravados 6

Sem interferência, o controle confirma que transmissão e gravação batem
(`test_controle_transmissao_sem_interferencia_e_o_jogo_gravado` passa).

**4. A corrente errada fica salva** (`test_r1_a_corrente_errada_fica_gravada_...`)

> jogos diferentes nas rodadas 2, 3 e 4: **[9, 9, 10]** (de 10)

Depois de **uma** interferência na rodada 1, as rodadas 2 a 4, jogadas sem
ninguém por perto, continuam diferentes da mesma seed. O motivo é que o
`avancar` grava `random.getstate()` no blob. O desvio não se corrige: a
temporada inteira daquele save segue outro rumo.

### Evidências da corrida natural

`corrida_natural.py`, 10 tentativas, servidor uvicorn real, 8 ligas (80 jogos por rodada):

| Seed | Jogos diferentes, controle (sozinho × sozinho) | Jogos diferentes, com vizinho lendo | Leituras do vizinho durante a rodada |
|---|---|---|---|
| 100 | 0 | 54 | 7 |
| 101 | 0 | 78 | 5 |
| 102 | 0 | 68 | 6 |
| 103 | 0 | 76 | 4 |
| 104 | 0 | 76 | 7 |
| 105 | 0 | 75 | 4 |
| 106 | 0 | 73 | 6 |
| 107 | 0 | 77 | 6 |
| 108 | 0 | 71 | 4 |
| 109 | 0 | 76 | 4 |

Basta **um outro técnico com a tela da rodada aberta** (4 a 7 `GET` durante
a rodada) para a rodada sair diferente. Sem ninguém por perto, o resultado é
idêntico em todas as tentativas.

### Reprodutibilidade

- Roteiro: 5 execuções → 5 reproduções, com o **mesmo** placar divergente
  sempre (as saídas foram comparadas linha a linha).
- Corrida natural: 10 de 10. Não depende de sorte nesta carga.

### Impacto

- **Determinismo perdido em produção:** com dois técnicos online, a mesma
  seed não reproduz a mesma temporada. Bugs reportados por jogadores ficam
  impossíveis de reproduzir pela seed.
- **Inconsistência visível ao jogador:** a transmissão ao vivo mostra um
  resultado, e a tabela e o pós-jogo mostram outro. O técnico tomou decisões
  em cima de um jogo que não existiu.
- **Persistente:** a corrente errada é salva, e o save inteiro diverge dali
  em diante.
- **Integridade dos dados:** não houve corrupção estrutural (placares e
  tabelas continuam coerentes entre si). O dano é à fidelidade da simulação.
- **Ocorrência em produção:** não verificada. Não acessei a produção, e o
  banco não guarda o que permitiria provar isso depois do fato.

---

## R2 — Turno processado em dobro

### Evidências: rodada dupla

Roteiro determinístico (`test_r2_dois_avancos_...`), Liga Taldo:

| | Referência (1 rodada, 1 pedido) | Dois pedidos simultâneos |
|---|---|---|
| Respostas | — | as duas com **200**, as duas `rodada_jogada = 1` |
| `rodada_atual` (blob/tabela `simulacao`) | 2 | **2** |
| Partidas da rodada 1 | 10 | **20** |
| Lances | 132 | **264** |
| Atuações | 249 | **498** |
| Mensagens no save | 3 | 2 (diferença observada, não investigada) |

Corrida natural, 8 ligas, 10 tentativas: **todas** com as duas respostas
`200 / rodada_jogada = 1`, **160 partidas na rodada 1** (o normal é 80) e
`rodada_atual = 2`.

**Leitura:** o save diz que só jogou uma rodada, mas há duas cópias dela em
`partida`, `lance` e `atuacao`. As estatísticas acumuladas de clubes e
jogadores (`UPDATE` com o estado final) não dobram: o último a gravar vence.
Ficam duplicados o histórico de jogos, o game log, a página da partida e
tudo o que conta linhas de `partida`/`atuacao`.

### Evidências: virada dupla

**Temporada 1 sem carreira** (`test_r2_virada_dupla_da_temporada_1_...`):

> temporadas 2: id 2 (carreira 1) e id 3 (carreira 2) · carreiras no banco: **2** ·
> os dois pedidos responderam com sucesso

O mesmo save virou **duas carreiras**, cada uma com a sua temporada 2.
`simulacao.carreira_id` do save original ficou apontando só para a última.

**Save que já é a temporada 1 de uma carreira** (`test_r2_virada_dupla_dentro_...`):

> temporadas 2 da carreira 1: ids 2 e 3 · os dois pedidos responderam com sucesso

A checagem `sucessora()` existe, mas as duas threads passam por ela antes
de qualquer gravação. A carreira fica com **duas "temporada 2"**, e
`sucessora()` (que espera uma linha) passa a ter duas.

Em sequência, o controle mostra que a segunda virada **é** recusada com
`CarreiraInvalida`.

### Reprodutibilidade

- Roteiro: 5 de 5 execuções, nos três cenários. Só muda qual thread fica com
  qual id, o que é esperado depois da barreira.
- Corrida natural (rodada): 10 de 10, sem gancho nenhum.

### Impacto

- **Saves com histórico duplicado:** é corrupção silenciosa. Nada falha, e
  o jogador vê jogos repetidos no histórico.
- **Carreira bifurcada:** duas temporadas seguintes vivas. O jogador pode
  seguir as duas, e a conta gasta duas vagas do limite de 10 jogos.
- **Gatilho realista:** duas abas abertas, duplo toque no celular com rede
  lenta ou reenvio do navegador. O botão desabilitado no frontend não cobre
  esses casos.
- **Ocorrência em produção:** não verificada. Dá para verificar sem tocar no
  servidor, numa **cópia do backup**, com uma consulta só de leitura:
  `SELECT simulacao_id, rodada, mandante_id, COUNT(*) FROM partida GROUP BY 1,2,3 HAVING COUNT(*) > 1`
  e `SELECT carreira_id, temporada, COUNT(*) FROM simulacao WHERE carreira_id IS NOT NULL GROUP BY 1,2 HAVING COUNT(*) > 1`.
  Recomendo fazer isso **antes** de escolher uma correção que crie
  constraints `UNIQUE`.

---

## Limitações

- Os testes de pytest usam só a Liga Taldo (o padrão do serviço). As 8 ligas
  foram cobertas pela corrida natural via HTTP.
- No roteiro do R2, a simulação das duas threads foi **serializada** de
  propósito, para isolar o R2 do R1. Em produção os dois se somam: as duas
  cópias da rodada podem até sair com placares diferentes entre si.
- A virada dupla não foi testada por HTTP, só pelo serviço. O caminho da rota
  é direto (`routes.py` → `carreira_service.proxima_temporada`), sem trava no meio.
- Não testei outros pares de fluxos concorrentes, como compra × rodada e
  calendário × rodada (ver os achados colaterais em `01_CONCORRENCIA_RNG.md`).
- O docker rodou no macOS (Apple Silicon). O GIL e o escalonador podem se
  comportar diferente na VPS. Os roteiros determinísticos não dependem disso;
  a corrida natural pode ter outra taxa por lá, mas o mecanismo é o mesmo.

## Próximos passos sugeridos (aguardando decisão)

1. Verificar R2 numa **cópia do backup** de produção (as consultas acima),
   só leitura.
2. Escolher a contenção para R1 e R2. Ver as tabelas de soluções em `01_CONCORRENCIA_RNG.md`.
3. Antes de qualquer correção no motor (R1-A), criar testes de regressão de
   placar por seed: "seed X, rodadas 1 a N → estes placares". Assim a
   correção prova que não mudou a simulação.
4. Bateria seguinte: atualização perdida entre fluxos (compra/escalação ×
   rodada), que é o achado colateral 3.
