---
name: rng-determinism
description: Auditar sorteio e determinismo da simulação do TaldoManager — random global (R1), estado do RNG salvo no blob, reprodutibilidade por seed, PYTHONHASHSEED. Use ao mexer ou investigar qualquer random.* do motor, seeds, ou divergência entre transmissão e jogo gravado.
---

# rng-determinism

Antes de tudo, leia `.claude/auditoria/REGRAS.md`.

## Como o RNG funciona hoje

- O motor usa o **módulo** `random` global: 46 chamadas diretas
  (42 em `app/domain/partida.py`, 2 em `campeonato.py`, 1 em `jogador.py`, 1 em `copa.py`).
- Também mexem no global: `random.seed(seed)`/`random.seed()` em
  `simulacao_service.py:133-135` e `carreira_service.py:173-175` (início de
  temporada e virada); `campeonato.py:79,177` (`getrandbits`) e `:98-103`
  (getstate → seed → setstate).
- Usam **instância própria** `random.Random(...)` (não afetados pelo R1):
  `mercado_cpu.py`, `ofertas.py`, `disputa.py`, `base.py` e o calendário
  (`campeonato.py:13,519`). Confirmar a cada auditoria; não presumir.
- O estado do RNG vai no blob: `snapshot_estado` grava `random.getstate()` em
  `estado_json["rng"]`; `restaurar_estado` faz `setstate`.
- Leituras fazem **getstate → setstate(save) → setstate(antigo)**:
  `temporada_service.proxima_rodada` e `pre_jogo`, `mercado_service._carregar`
  (usado por 11 serviços), `transmissao_service`, `pos_jogo_service`.
  Com duas threads, uma troca o RNG da outra no meio da rodada (R1).
- `avancar` grava `getstate()` no blob: a contaminação **persiste** nas rodadas seguintes.
- `_Contexto.gravar` (mercado) preserva o rng do blob.

## Procedimento

1. **Inventário**: `grep -rn "random\.\|from random\|Random(" backend/app`.
   Para cada chamada: arquivo:linha, função, e se usa `sample` sobre `set` ou
   itera `set`/`dict` de objetos (ordem por id ou hash é risco entre processos).
2. **Determinismo no processo**: mesma seed, sem interferência → mesmos
   resultados. Controle: `test_controle_mesma_seed_da_a_mesma_rodada`.
3. **Determinismo entre processos**: rodar a mesma seed com `PYTHONHASHSEED`
   = 0, 1, 2 e aleatório, e comparar os hashes de placares, lances, notas,
   tabela e `blob["rng"]`. Verificado em 17/11/2026 para a Liga Taldo, seed 7,
   5 rodadas (`AUDITORIA/02_BASELINE_SIMULACAO.md`).
4. **Interferência**: reproduzir com `_intercalar` (`test_auditoria_r1_rng.py`).
5. **Para correções**: exigir o baseline (`AUDITORIA/02_BASELINE_SIMULACAO.md`)
   gravado **antes**. Meta preferida: um RNG por save com a **mesma
   sequência** (`random.Random().setstate(estado_do_blob)`), e todos os hashes iguais.

## Armadilhas

- `print`/`redirect_stdout` no motor não afetam o RNG, mas vazam saída.
- Uma "leitura" que chama `random` (mesmo sem gravar) consome a sequência.
- Não trocar a ordem dos sorteios ao refatorar: muda todos os resultados seguintes.
- `random.seed(x)` em teste altera o global do processo inteiro do pytest.
