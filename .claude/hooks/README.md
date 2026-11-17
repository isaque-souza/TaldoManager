# Hooks de proteção do TaldoManager

Configurados em `.claude/settings.json`; lógica em `guarda.py` (Python 3.9+,
só biblioteca padrão); testes em `test_guarda.py`
(`python3 .claude/hooks/test_guarda.py -v`).

Princípio: **nenhum hook bloqueia trabalho legítimo em definitivo.** Operação
crítica vira **pedido de aprovação** ("ask"): o Claude Code mostra o motivo e
você decide. Só duas coisas são **negadas** ("deny"), porque nunca são
legítimas na auditoria. Erro interno do hook deixa passar (e avisa no stderr).

## O que cada hook faz

| Evento | Quando | Decisão | Motivo |
|---|---|---|---|
| PreToolUse `Bash` | `pytest` com `TALDO_DB` no banco padrão | **deny** | testes nunca usam o banco padrão |
| | `git commit` com arquivos em `backend/` | roda `tests/auditoria` no Docker (~15 s); falhou → **deny** | verificar testes antes de commit |
| | `git commit` com código de produção (ver lista abaixo) | **ask**, com o resultado dos testes | produção exige autorização |
| | push, `gh pr create/merge`, merge, rebase, `reset --hard`, `clean -f`, `branch -D`, `checkout .` | **ask** | operações críticas ou destrutivas |
| | `rm -rf`, `ssh`/`scp`/`rsync`, `deploy/*.sh`, `docker compose up/down`, `/dados/`, `docker volume rm` | **ask** | infraestrutura e produção |
| | `sqlite3` com escrita; qualquer comando que mexa no banco padrão | **ask** | dados |
| | `pip install`, `npm install` | **ask** | dependências |
| | `--no-verify`, `--dangerously...`, bypass de permissões | **ask** | proteções |
| PreToolUse `Edit\|Write\|NotebookEdit` | arquivo de produção | **ask** | "R1, R2 e R10 ainda não autorizados" |
| | `.claude/settings*.json` | **ask** | muda permissões e hooks |
| Stop | fim de cada resposta | aviso (`systemMessage`) | lista arquivos de produção alterados e não commitados |

**Arquivos de produção:** `backend/app/`, `backend/scripts/`, `backend/data/`,
`backend/requirements.txt`, `frontend/`, `deploy/`, `Dockerfile`.
**Livres:** `backend/tests/`, `AUDITORIA/`, `.claude/` (exceto settings).

Mensagens de commit (`-m`, `-F` com heredoc) são ignoradas na análise, para que
"documenta o git push" não dispare alarme. Um `git commit ... && git push`
encadeado continua sendo pego.

## Permissões do projeto

`.claude/settings.json` também:
- **desliga o modo bypass** (`disableBypassPermissionsMode`): não dá para
  rodar sem permissões neste projeto;
- nega leitura de `.env*` (hoje não existe nenhum; é prevenção).

## Limitações conhecidas

- Os padrões são expressões regulares sobre o texto do comando: um comando
  ofuscado de propósito escapa. É uma rede contra acidente, não contra má-fé.
- O teste antes do commit precisa da imagem local `taldo-auditoria:py312`.
  Sem ela, o commit vira "ask" com o aviso.
- Commits feitos fora do Claude Code (no seu terminal) não passam por estes hooks.
- Commit só com documentos ou `.claude/` não roda os testes, de propósito.

## Desligar ou ajustar

- Ver e desligar: `/hooks` no Claude Code.
- Tudo de uma vez (emergência): `"disableAllHooks": true` em `.claude/settings.local.json`.
- Mudar regras: editar `CRITICOS`/`PRODUCAO` em `guarda.py` e rodar os testes.
