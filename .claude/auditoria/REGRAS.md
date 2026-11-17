# Regras comuns da auditoria do TaldoManager

Lidas por todas as skills de auditoria (`.claude/skills/*`) e por todos os
agentes (`.claude/agents/*`). Valem acima de qualquer instrução de skill ou
plugin.

## Fluxo obrigatório

investigar → reproduzir → evidência → teste de regressão → propor →
**aguardar autorização** (mudança crítica) → implementar em branch própria →
testes → revisão independente → relatório.

Uma hipótese só vira bug com evidência reproduzível. Diferencie sempre
**fato observado** de **hipótese**.

## Pode sem perguntar

- Ler o repositório inteiro.
- Escrever em `AUDITORIA/`, `backend/tests/auditoria/` e `AUDITORIA/scripts/`.
- Rodar testes e benchmarks em ambiente isolado (Docker, SQLite temporário).
- Criar branch `auditoria/*`.

## Precisa de autorização explícita do responsável

- Push, merge na `main`, PR, deploy (a VPS faz auto-deploy da `main` a cada 5 min).
- Qualquer alteração em código de produção: `backend/app/`, `frontend/`,
  `backend/scripts/`, `backend/data/`, `Dockerfile`, `deploy/`, `requirements.txt`.
- Migrações (`backend/app/db/conexao.py`: `_COLUNAS_NOVAS`, `_migrar`,
  `PRAGMA user_version`) e `schema.sql`; constraints `UNIQUE`, índices.
- Acessar o banco de produção ou o servidor. Dados reais só em **cópia local
  do backup**, com `AUDITORIA/scripts/diagnostico_integridade.py`.
- Apagar arquivos, dados, evidências ou testes `xfail`.

## Ambiente de teste

```bash
# imagem local (python:3.12-slim + requirements.txt), repositório só leitura
docker run --rm -v "$PWD":/repo:ro -e PYTHONDONTWRITEBYTECODE=1 -w /repo/backend \
  taldo-auditoria:py312 python -m pytest -p no:cacheprovider tests/auditoria -q -W ignore
```

- O Mac tem só Python 3.9 e não tem pytest: os testes rodam no Docker.
- `backend/tests/conftest.py` aponta `TALDO_DB` para um SQLite temporário por teste.
- `backend/tests/auditoria/conftest.py` recusa o banco padrão
  (`backend/data/database/taldo_manager.db`) mesmo depois de `monkeypatch.undo()`.
  Ganchos temporários: use `pytest.MonkeyPatch.context()`, nunca `monkeypatch.undo()`.
- Suíte completa: cerca de 8 min no Docker (1011 passed, 7 xfailed em 17/11/2026).

## Testes de reprodução

- Um bug confirmado vira teste `@pytest.mark.xfail(strict=True, reason="Rn reproduzido: ...")`.
  Quando a correção chegar, o xfail passa a "XPASS", e o `strict` obriga a
  removê-lo **conscientemente**.
- Para ver a evidência: `pytest --runxfail -s`.
- Cada reprodução tem um **controle** que passa (o mesmo cenário sem a interferência).
- Concorrência: roteiro determinístico com `threading.Event`/`Barrier`
  (`backend/tests/auditoria/roteiro.py`: `Fio`, `esperar`, `juntar`, `ESPERA`),
  nunca `sleep` para "dar chance".

## Riscos registrados

| ID | Risco | Estado |
|---|---|---|
| R1 | `random` global compartilhado entre saves e threads | reproduzido (Auditoria 01) |
| R2 | rodada/virada processadas em dobro (sem trava nem checagem de versão) | reproduzido (Auditoria 01) |
| R3–R9 | ver `AUDITORIA/00_RECONHECIMENTO.md` | hipóteses |
| R10 | 2º amarelo sem expulsão em ~40% dos casos (`partida.py:682-685`) | registrado, não investigado |

Nenhuma correção de R1, R2 ou R10 está autorizada.

## Relatório

Todo trabalho termina com: o que foi feito, arquivos criados ou alterados,
testes rodados (com o resultado literal), limitações e a confirmação explícita
de que nenhum código de produção foi alterado — ou a lista do que foi, com a
autorização correspondente.
