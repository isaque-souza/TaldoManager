# Agentes de auditoria: quem escreve onde

Os agentes podem investigar em paralelo (ler é livre), mas **cada arquivo tem
um dono só**. Um agente que precisar mudar um arquivo de outro dono devolve a
sugestão no relatório; quem integra é a sessão principal.

| Agente | Arquivo | Escreve somente em |
|---|---|---|
| Concurrency Engineer | `concurrency-engineer.md` | `AUDITORIA/concorrencia/`, `backend/tests/auditoria/test_auditoria_r2_*.py`, `backend/tests/auditoria/test_auditoria_conc_*.py` |
| Simulation Engineer | `simulation-engineer.md` | `AUDITORIA/simulacao/`, `backend/tests/auditoria/test_auditoria_r1_*.py`, `backend/tests/auditoria/test_auditoria_motor_*.py`, `backend/tests/auditoria/baseline/` |
| Database Engineer | `database-engineer.md` | `AUDITORIA/banco/`, `AUDITORIA/scripts/diagnostico_integridade.py`, `backend/tests/auditoria/test_auditoria_diagnostico.py`, `backend/tests/auditoria/test_auditoria_banco_*.py` |
| QA Engineer | `qa-engineer.md` | `AUDITORIA/qualidade/`, `backend/tests/auditoria/test_auditoria_qualidade_*.py` |
| Security Engineer | `security-engineer.md` | `AUDITORIA/seguranca/` (só documentos) |
| Performance Engineer | `performance-engineer.md` | `AUDITORIA/desempenho/`, `AUDITORIA/scripts/stress_*.py`, `AUDITORIA/scripts/bench_*.py` |

**Só a sessão principal** edita os arquivos compartilhados:
`.claude/**`, `AUDITORIA/0*.md`, `backend/tests/auditoria/conftest.py`,
`protecao.py`, `roteiro.py`, `test_auditoria_protecao_banco.py`.

**Ninguém** (agente ou sessão) edita código de produção sem autorização
explícita: ver `REGRAS.md`.

## Paralelismo

- Dois agentes podem rodar ao mesmo tempo, porque as áreas não se cruzam.
- Um agente que precisa rodar a suíte usa o Docker com o repositório **só
  leitura** (`-v "$PWD":/repo:ro`), e o banco fica em `/tmp` do container.
  Execuções paralelas não colidem.
- Para trabalho com escrita em paralelo na mesma área, use `isolation: worktree`
  e integre depois.
