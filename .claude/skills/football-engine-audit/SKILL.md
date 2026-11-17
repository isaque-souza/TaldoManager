---
name: football-engine-audit
description: Auditar as regras de futebol do motor de partida do TaldoManager (app/domain/partida.py e afins) — cartões, expulsões, suspensões, lesões, substituições, gols, pênaltis, notas, fadiga, copa. Use ao investigar se uma regra está certa, coerente com as estatísticas, ou ao avaliar R10 (2º amarelo sem expulsão).
---

# football-engine-audit

Antes de tudo, leia `.claude/auditoria/REGRAS.md` e `rng-determinism` (qualquer
mudança no motor altera a sequência de sorteios).

## Onde estão as regras

- `app/domain/partida.py`: a partida minuto a minuto. Falta e cartão em
  `_registrar_falta` / `_expulsar`; fadiga; substituições; `adicionar_evento`.
- `app/domain/jogador.py` (suspensão, lesão, `registrar_amarelo`),
  `campeonato.py` (rodada da liga), `copa.py` (copa isolada com
  `_isolar_da_liga`, que só mantém `energia` e `rodadas_lesao`),
  `evolucao.py`, `pos_jogo.py` (notas).
- Eventos gravados em `lance` (`tipo`: gol, cartao_amarelo, expulsao,
  substituicao, lesao, penalti...); atuações em `atuacao`.

## Procedimento para uma regra

1. **Ler a regra no código** e escrever em português o que ela faz, com arquivo:linha.
2. **Comparar com a regra do futebol** (Regras do Jogo da IFAB) e com
   `PRODUCT.md`/`DESIGN.md`. Divergência intencional de design não é bug, mas
   deve estar documentada.
3. **Medir numa temporada simulada** (banco temporário, várias seeds): contagens
   em `lance`, coerência com `jogador.amarelos`/`vermelhos`/suspensões e com
   `atuacao` (ex.: expulso no minuto X não pode ter evento depois de X).
4. **Efeitos colaterais**: suspensão na rodada seguinte, nota, penalidade de
   expulsão do clube (`penalidade_expulsao`), estatísticas de temporada.
5. **Registrar** em `AUDITORIA/NN_*.md`: fato, medição, impacto e, se for o caso,
   teste `xfail(strict=True)` que descreve o comportamento correto.
6. **Não corrigir.** Uma correção de regra muda o baseline (ver
   `AUDITORIA/02_BASELINE_SIMULACAO.md`) e não pode vir junto com a de R1.

## R10 — ponto de partida

`partida.py:682-685`: 2º amarelo expulsa só com `random.random() < 0.6`
("o juiz às vezes releva"). Numa temporada de seed 5: 93 jogadores com 2
amarelos no jogo, 36 sem expulsão, seguindo em campo. Perguntas abertas: o 3º
amarelo é possível? A suspensão por acúmulo conta os dois? Era intencional?
