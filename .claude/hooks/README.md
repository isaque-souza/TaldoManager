# Hooks de proteção do TaldoManager

Configurados em `.claude/settings.json`; lógica em `guarda.py` (Python 3.9+,
só biblioteca padrão); testes em `test_guarda.py`
(`python3 .claude/hooks/test_guarda.py -v`). Os testes são herméticos: rodam
uma cópia do `guarda.py` num repositório git temporário, com um `docker` falso.

Princípios:
- **nenhum hook bloqueia trabalho legítimo em definitivo.** Operação crítica
  vira **pedido de aprovação** ("ask"): o Claude Code mostra o motivo e você
  decide. Só duas coisas são **negadas** ("deny"), porque nunca são legítimas
  na auditoria.
- **falha interna nunca libera operação sensível em silêncio** (Auditoria 03).
  Se a análise quebrar, uma checagem de reserva, mais ampla, decide: comando
  ou arquivo sensível → "ask" com o erro; comando comum (`ls`, `cat`, `grep`)
  passa, com aviso no stderr. O hook `fim` só avisa e nunca trava.

## O que cada hook faz

| Evento | Quando | Decisão | Motivo |
|---|---|---|---|
| PreToolUse `Bash` | `pytest` com `TALDO_DB` no banco padrão | **deny** | testes nunca usam o banco padrão |
| | `git commit` com arquivos em `backend/` | roda `tests/auditoria` no Docker (~15 s); falhou → **deny** | verificar testes antes de commit |
| | `git commit` com código de produção (ver lista abaixo) | **ask**, com o resultado dos testes | produção exige autorização |
| | comando que altera um arquivo de proteção (ver abaixo) | **ask** | os hooks não podem ser desligados sem você ver |
| | push, `gh pr create/merge`, merge, rebase, `reset --hard`, `clean -f`, `branch -D`, `stash`, `git rm`, `checkout/restore` que descarta (`.`, `--`, `-f`, `--source`) | **ask** | operações críticas ou destrutivas (também com `git -P`, `-C`, `--git-dir`...) |
| | `git -c`/`--config-env` com pager, editor, alias, ssh...; `--exec-path` | **ask** | o git executaria um comando |
| | `rm -rf`, `ssh`/`scp`/`rsync`, `deploy/*.sh`, `docker compose up/down`, `/dados/`, `docker volume rm` | **ask** | infraestrutura e produção |
| | `sqlite3` com escrita; qualquer comando que mexa no banco padrão | **ask** | dados |
| | `pip install`, `npm install` | **ask** | dependências |
| | `--no-verify`, `--dangerously...`, bypass de permissões | **ask** | proteções |
| PreToolUse `Edit\|Write\|NotebookEdit` | arquivo de proteção | **ask** | idem |
| | arquivo de produção | **ask** | "R1, R2 e R10 ainda não autorizados" |
| Stop | fim de cada resposta | aviso (`systemMessage`) | lista arquivos de produção alterados e não commitados |

**Arquivos de produção:** `backend/app/`, `backend/scripts/`, `backend/data/`,
`backend/requirements.txt`, `frontend/`, `deploy/`, `Dockerfile`.

**Arquivos de proteção:** `.claude/hooks/`, `.claude/settings*.json`,
`.claude/auditoria/` (REGRAS, AGENTES), `.claude/agents/` (as ferramentas de
cada agente) e `~/.claude/settings*.json` (onde dá para desligar hooks e
plugins). No Bash, ler, comparar, `git add/diff/log` e rodar o próprio
`guarda.py`/`test_guarda.py` passam; qualquer outro comando que cite esses
caminhos (ou `guarda.py`, `settings.json`, `REGRAS.md`, `AGENTES.md`) pede
aprovação: `sed -i`, `>`, `tee`, `cp`, `mv`, `rm`, `chmod`, `ln`,
`git checkout/restore`, `python -c`, `perl -i`, `find -delete`...

**Livres:** `backend/tests/`, `AUDITORIA/`, `.claude/skills/`.

## Commit: quais arquivos entram

O hook roda **antes** do comando. Para enxergar o que vai para o commit, ele
junta: o que já está preparado (`git diff --cached`), os caminhos de cada
`git add` do mesmo comando (`-A`, `.`, pastas, globs, `git -C dir add`, relativos
à pasta atual do Bash) e as formas `git commit -a`/`-am` e
`git commit <caminho>`. Se não der para identificar, pede aprovação.

## Heredoc e mensagens

Só a mensagem do commit é ignorada na análise: `-m "..."` e o heredoc de
`git commit -F - <<EOF`. O conteúdo de qualquer outro heredoc
(`bash <<EOF`, `sqlite3 x.db <<SQL`, `python3 - <<EOF`) **é analisado**. Uma
mensagem com `$(...)` ou crase não é ignorada (o shell executa isso).

## Permissões do projeto

`.claude/settings.json` também:
- **desliga o modo bypass** (`disableBypassPermissionsMode`): não dá para
  rodar sem permissões neste projeto;
- nega leitura de `.env*` (hoje não existe nenhum; é prevenção).

## Limitações conhecidas

- **"ask" no auto mode:** o hook pede aprovação, mas com o auto mode ligado
  quem responde pode ser o classificador do Claude Code, não você. Na
  Auditoria 03, edições em arquivos de proteção que o hook marcou como "ask"
  foram aplicadas sem recusa. Para que "ask" signifique aprovação humana,
  trabalhe com o auto mode desligado.
- Os padrões são expressões regulares e uma análise simples do shell (com
  `cd`, globs, `$(...)` aninhado e caminhos normalizados): um comando
  ofuscado de propósito (variável definida em outro comando, `eval`, base64,
  um script em arquivo) escapa. É uma rede contra acidente e contra o caminho
  óbvio, não uma sandbox.
- Comandos que reescrevem arquivos sem citá-los — `git apply`, `git am`,
  `git pull`, `git cherry-pick`, `patch`, `tar x`, `unzip` — não são
  analisados quanto à proteção (o efeito depende do conteúdo do patch/arquivo).
- Proteção forte de verdade exige uma camada fora do texto do comando (ver
  `AUDITORIA/03_CORRECOES_CODE_REVIEW.md`, "Riscos restantes").
- Alterar arquivo de **produção** pelo Bash (`sed -i backend/app/...`) não
  pede aprovação na hora; o hook `fim` avisa no fim da resposta.
- O teste antes do commit precisa da imagem local `taldo-auditoria:py312`.
  Sem ela (ou com o Docker quebrado), o commit vira "ask" com o aviso.
- Commits feitos fora do Claude Code (no seu terminal) não passam por estes hooks.
- Commit só com documentos ou `.claude/` não roda os testes, de propósito.
- `TALDO_GUARDA_FALHA_TESTE` simula uma falha interna, só para os testes;
  ela só leva à checagem de reserva (nunca libera mais do que o normal).

## Desligar ou ajustar

- Ver e desligar: `/hooks` no Claude Code.
- Tudo de uma vez (emergência): `"disableAllHooks": true` em
  `.claude/settings.local.json` — feito por você; pelo Claude, pede aprovação.
- Mudar regras: editar `CRITICOS`/`PRODUCAO`/`PROTEGIDOS` em `guarda.py` e
  rodar os testes.
