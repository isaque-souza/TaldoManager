---
name: concurrency-audit
description: Auditar condições de corrida no TaldoManager (FastAPI com rotas def em threadpool + SQLite cru). Use ao investigar requisições simultâneas, duplo clique, duas abas, atualização perdida, rodada/virada em dobro (R2) ou qualquer fluxo ler-simular-gravar.
---

# concurrency-audit

Antes de tudo, leia `.claude/auditoria/REGRAS.md`.

## Arquitetura que importa

- Rotas FastAPI são `def` síncronas: rodam **em paralelo** no threadpool do
  uvicorn (1 worker, ~40 threads). Não existe trava por save.
- SQLite via `sqlite3` cru (`app/db/conexao.py`): transação **deferida**,
  `timeout=15`. Duas threads podem ler o mesmo estado e gravar depois.
- O save é `simulacao.estado_json` (blob) + tabelas projetadas. Cada pedido
  recarrega as seeds das ligas e aplica o blob com `restaurar_estado`.
- Padrão perigoso: **ler → simular fora de transação → `UPDATE ... WHERE id=?`**
  sem checar versão (`temporada_service.avancar`). Na virada, a checagem
  `sucessora()` acontece antes do `with conn:` (`carreira_service.py`).
- Jogador é atualizado por **nome** (`WHERE simulacao_id=? AND nome=?`), sem UNIQUE.

## Procedimento

1. **Mapear o fluxo**: para a rota alvo, liste leituras, cálculo e escritas, e
   onde abre e fecha cada `with conn:`. Anote a linha de cada passo.
2. **Achar a janela**: entre a leitura que decide e a escrita que confirma, o que
   outra thread pode fazer? (mesma rota; rota vizinha do mesmo save; leitura de
   outro save, que mexe no RNG global, ver `rng-determinism`.)
3. **Reproduzir de forma determinística**: em `backend/tests/auditoria/`,
   force a intercalação com `threading.Barrier`/`Event`, usando os ganchos
   em `pytest.MonkeyPatch.context()`. Modelo:
   `test_auditoria_r2_concorrencia.py::_sincronizar_avanco`.
4. **Controle**: o mesmo cenário em sequência deve dar o resultado correto.
5. **Medir o dano** com contagens (`_contagens(sid)`) e, quando gravar dados,
   com `AUDITORIA/scripts/diagnostico_integridade.py` sobre o banco temporário.
6. **Corrida natural (opcional)**: `AUDITORIA/scripts/corrida_natural.py`
   contra um uvicorn local num banco descartável, para provar que acontece sem
   ganchos.
7. **Registrar**: evidência em `AUDITORIA/NN_*.md` e teste `xfail(strict=True)`.

## Pares ainda não testados (candidatos)

compra/venda × `avancar`; escalação/tática × `avancar`; calendário × `avancar`;
proposta da CPU × aceitar oferta; dois logins da mesma conta.

## Soluções já catalogadas

Ver `AUDITORIA/01_CONCORRENCIA_RNG.md`: R2-A (`WHERE rodada_atual=?` otimista),
R2-B (`BEGIN IMMEDIATE`), R2-C (lock por save em memória), R2-D (UNIQUE —
só depois do diagnóstico histórico), R2-E (chave de idempotência). **Propor,
não implementar.**
