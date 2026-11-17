# 02 — Baseline determinístico da simulação

**Data:** 17/11/2026 · **Status:** estratégia. Nada aqui foi implementado no
motor nem na suíte; esta é a proposta para aprovação.

**Problema.** A correção do R1 (solução A: um `random.Random` por save, no
lugar do módulo global) mexe em 46 pontos de sorteio do motor. É fácil mudar
a simulação sem querer: trocar a ordem de dois sorteios, sortear numa
instância diferente, esquecer um `random.choice`. Precisamos de uma rede que
diga **exatamente** o que mudou entre o antes e o depois.

**Ideia.** *Golden master*: rodar cenários fixos na `main` de hoje, gravar
uma impressão digital de tudo o que a simulação produz e comparar, campo a
campo, com a mesma execução depois da correção.

---

## 1. O que já foi verificado

**Determinismo entre processos.** Rodei a mesma seed (7, 5 rodadas, Liga
Taldo) em 5 processos com `PYTHONHASHSEED` = 0, 1, 2, aleatório e aleatório.
As impressões de placares, lances, notas, tabela e estado do RNG saíram
**idênticas** nos 5. Conclusão: nenhum `set` ou `dict` dependente do hash
influencia a simulação nesse cenário. O golden master pode ser gravado num
processo e conferido em outro.

**Determinismo dentro do processo.** Já coberto pelos controles da Auditoria
01 (`test_controle_mesma_seed_da_a_mesma_rodada`): a mesma seed, sem
interferência, dá a mesma rodada.

**Ainda não verificado:**
- as 8 ligas, a copa e a virada no teste entre processos;
- Python 3.13 ou outra versão de SQLite (o container de produção usa 3.12).

O `random` do Python é estável entre versões para `random()`, `choice()`,
`shuffle()` e `randint()`, mas não para `sample()` de conjuntos. O
inventário dos 46 pontos deve confirmar que nenhum usa `sample` sobre `set`.

## 2. Cenários

| # | Cenário | Por quê |
|---|---|---|
| S1 | Liga Taldo, seeds 1, 5, 7, 42, 99; temporada inteira rodada a rodada (`avancar`) | o caminho principal, com o RNG passando pelo blob a cada rodada |
| S2 | as mesmas seeds com `salvar_temporada` (tudo de uma vez) | o caminho sem blob intermediário; S1 e S2 devem continuar dando o mesmo que hoje, iguais ou não entre si |
| S3 | 8 ligas, seed 5, 10 rodadas | todos os motores de liga e a ordem entre ligas |
| S4 | temporada com copa (seed com copa no calendário) | `_isolar_da_liga` e a ordem copa × liga |
| S5 | virada: S1 seed 5 completa → `proxima_temporada` → 5 rodadas | o RNG atravessando a virada (envelhecimento, aposentadoria, renovações) |
| S6 | ações do técnico no meio: venda aceita na rodada 1, troca de tática e escalação na rodada 3 | `_Contexto.gravar`, que preserva o RNG do blob; a ordem dos sorteios depois de uma ação |
| S7 | leituras entre rodadas: `pre_jogo`, `proxima_rodada`, `ver_mercado` e transmissão entre cada `avancar`, **em sequência** | prova que as leituras não consomem nem trocam o RNG do save (hoje elas fazem save/restore do global) |

Cada cenário roda num SQLite temporário novo, como os testes de hoje
(`TALDO_DB` do `conftest`, com a proteção da pasta `tests/auditoria`).

## 3. O que gravar (a impressão digital)

Por cenário e **por rodada**, para que a primeira divergência aponte a
rodada exata:

| Grupo | Conteúdo | Chave de ordenação |
|---|---|---|
| Placares | mandante, visitante, gols | rodada, nome do mandante |
| Eventos | minuto, tipo, nome do jogador, detalhe | rodada, mandante, ordem de inserção (`lance.id` relativo à partida) |
| Atuações | nome, titular, entrou/saiu, nota, gols, assistências | rodada, mandante, nome |
| Classificação | clube, pontos, V/E/D, gols pró e contra, saldo, posição | posição |
| Estatística acumulada | por jogador: gols, assistências, partidas, amarelos, vermelhos, nota média, lesão, energia | nome |
| Economia | caixa, receita e despesa da rodada por clube | nome |
| Estado do RNG | SHA-256 de `blob["rng"]` depois da rodada | — |
| Blob | SHA-256 do `estado_json` canônico (`sort_keys`), **sem** os campos voláteis | — |
| Persistência | SHA-256 das tabelas `clube`, `jogador`, `partida`, `lance`, `atuacao`, `mensagem`, `transferencia`, projetadas por nome e sem `id` | tabela, chave natural |

**Formato.** Um JSON por cenário em `backend/tests/baseline/dados/`, com o
conteúdo legível dos grupos de placares, classificação e RNG, e só hashes nos
grupos grandes. Estimativa: abaixo de 200 KB no total. Se um hash divergir, o
teste regrava os dois lados num diretório temporário e mostra o `diff`
legível.

**Fora da impressão (voláteis):**
- `criada_em`, `atualizada_em` e qualquer carimbo de data/hora;
- ids autoincremento: tudo é projetado por nome;
- `usuario_id` e sessão.

O RNG **entra**: se a correção mudar a forma de guardar o estado, o hash
muda por construção. Ver o item 5.

## 4. Como implementar (quando autorizado)

1. **Gravar na `main` de hoje**, antes de qualquer correção: um script
   `backend/tests/baseline/gerar.py` grava os JSONs, que entram num commit
   próprio, separado da correção.
2. **Teste de regressão** `test_baseline.py`: roda os cenários e compara com
   os JSONs. Relata a primeira rodada e o primeiro campo divergente.
3. **Rodar em processo separado** (`subprocess` com `PYTHONHASHSEED`
   aleatório) em pelo menos um cenário, para manter coberto o achado do
   item 1.
4. **Tempo:** S1 a S7 custam uns 2 a 3 minutos. Marcar com
   `@pytest.mark.baseline`, para rodar no CI e antes de cada correção do
   motor, e não a cada teste local.
5. **Regeneração intencional:** só com `--regerar-baseline` e uma linha de
   justificativa no commit. Um teste que falha não se "conserta" regerando.

## 5. Como usar na correção do R1

A troca do `random` global por um RNG por save pode cair em dois casos:

- **Caso A, sem mudança de comportamento** (meta preferida): o novo RNG é
  semeado e serializado de forma que a sequência de números é idêntica.
  `random.Random()` com `setstate(estado_do_blob)` produz a mesma sequência
  que o módulo global com o mesmo estado. Todos os grupos devem bater,
  **inclusive o hash do RNG**. Qualquer diferença é bug da correção.
- **Caso B, com mudança aceita** (por exemplo, um RNG separado para
  leituras ou para a copa): a sequência muda de propósito. Aí o baseline
  serve para provar que **só** o esperado mudou: as estatísticas
  agregadas (média de gols, cartões e notas em 5 seeds) ficam na mesma
  faixa, e a estrutura (C01–C24 do diagnóstico) segue limpa. O baseline é
  regerado com justificativa.

Recomendo exigir o caso A para a primeira correção. A conferência fica
binária.

Os testes `xfail` da Auditoria 01 (R1) devem passar a **passar** com a
correção. Só então se remove o `xfail`, e um por um, conforme as regras
combinadas.

## 6. Riscos e limitações da estratégia

- O baseline congela também os **bugs** de hoje. Se uma correção de regra
  (por exemplo, o 2º amarelo sem expulsão, ver `02_INTEGRIDADE_HISTORICA.md`)
  vier junto, misturam-se dois motivos de diferença. Uma correção por vez.
- O golden master garante igualdade, não correção: ele não diz se a
  simulação de hoje está certa.
- Dependência de dados: se `data/` (ligas, jogadores) mudar, o baseline
  muda. O gerador grava o SHA-256 dos arquivos de dados junto, e o teste
  avisa quando a causa é essa.
- Os cenários com ações do técnico (S6) dependem das regras de mercado.
  Mudança legítima de regra exige regerar o baseline.
