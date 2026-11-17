---
name: test-quality-audit
description: Avaliar a qualidade da suíte de testes do TaldoManager (backend/tests, ~1000 testes) — asserts fracos, testes que não falham, isolamento do banco, flakiness, cobertura de regras críticas. Use antes de confiar na suíte para uma correção ou ao revisar testes novos.
---

# test-quality-audit

Antes de tudo, leia `.claude/auditoria/REGRAS.md`.

## Estado conhecido (00_RECONHECIMENTO.md, 17/11/2026)

- 994 testes originais + 24 de auditoria; cobertura de `app/` em 96%
  (db 100, repositories 100, domain 97, services 96, api 95); `scripts/` 25%.
- **46 testes** só têm `assert` dentro de `for`/`if`: podem passar sem
  verificar nada se o laço for vazio.
- Isolamento: `backend/tests/conftest.py` (autouse) aponta `TALDO_DB` para um
  arquivo temporário e roda `init_db()`. Frágil diante de `monkeypatch.undo()`.
  A pasta `tests/auditoria` tem proteção própria.
- `redirect_stdout` no motor vaza saída nos testes ("MELHOR EM CAMPO", "ESCALAÇÃO").

## Checagens

1. **Asserts que podem não rodar**: `assert` só dentro de `for`/`if`/`while`
   sem um `assert` fora; `pytest.raises` sem `match`; `assert x` onde x é
   sempre verdadeiro (lista não vazia de objetos, etc.).
2. **Mutação manual**: escolha uma regra crítica (ex.: pontos por vitória,
   expulsão, caixa) e altere-a **numa cópia temporária** (`git worktree` em
   `/tmp` ou no container), nunca na árvore de trabalho; rode a suíte e veja se
   algum teste falha. Regra sem teste que falha = lacuna.
3. **Flakiness**: rodar a pasta 3 a 5 vezes; com `-p no:randomly` se o plugin
   existir; testes que dependem do RNG global de outro teste.
4. **Isolamento**: algum teste escreve fora do `tmp_path`? Usa o banco padrão?
   Altera estado global (`random.seed`, variáveis de módulo) sem restaurar?
5. **Velocidade**: `--durations=20`; testes lentos candidatos a marcação.
6. **xfail**: todo `xfail` tem `strict=True` e um `reason` com o ID do risco.

## Saída

`AUDITORIA/NN_QUALIDADE_TESTES.md` com a lista (arquivo:linha, problema,
sugestão). Novos testes vão para `backend/tests/auditoria/`; alterar testes
existentes só com autorização.
