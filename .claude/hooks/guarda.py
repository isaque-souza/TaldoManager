#!/usr/bin/env python3
"""Hooks de proteção da auditoria do TaldoManager.

Uso (chamado pelo Claude Code, JSON do evento no stdin):
    python3 .claude/hooks/guarda.py bash      # PreToolUse  Bash
    python3 .claude/hooks/guarda.py arquivo   # PreToolUse  Edit|Write|NotebookEdit
    python3 .claude/hooks/guarda.py fim       # Stop

Decisões (ver .claude/hooks/README.md):
- "deny": só para o que nunca é legítimo na auditoria (pytest contra o banco
  padrão; commit com testes de auditoria falhando).
- "ask": operação crítica, destrutiva ou que mexe nas próprias proteções. O
  Claude Code pede a sua aprovação; nada é bloqueado em definitivo.
- silêncio: todo o resto segue o fluxo normal de permissões.

Falha interna (Auditoria 03, achado 2): NUNCA libera em silêncio uma operação
sensível. Se a análise quebrar, `_reserva` decide com uma checagem mais ampla:
comando/arquivo sensível → "ask" com o erro; comando comum passa com aviso no
stderr. O modo `fim` só avisa e nunca trava.

Só biblioteca padrão (roda no Python 3.9 do macOS).
"""

import fnmatch
import glob
import json
import os
import re
import shlex
import subprocess
import sys

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# Arquivos de produção: mudar exige autorização (REGRAS.md)
PRODUCAO = (
    "backend/app/", "backend/scripts/", "backend/data/", "backend/requirements.txt",
    "frontend/", "deploy/", "Dockerfile", "docker-compose",
)
LIVRES = ("backend/tests/", "AUDITORIA/", ".claude/")

# Arquivos de proteção: hooks, permissões, regras e agentes (achado 4)
PROTEGIDOS = (".claude/hooks/", ".claude/settings", ".claude/auditoria/", ".claude/agents/")

BANCO_PADRAO = "backend/data/database/taldo_manager.db"

# padrão -> motivo (pede aprovação)
CRITICOS = [
    (r"\bgit\s+push\b", "push para o GitHub (exige autorização explícita)"),
    (r"\bgh\s+pr\s+(create|merge)\b", "abrir ou fazer merge de PR (exige autorização explícita)"),
    (r"\bgh\s+(release|repo\s+(delete|edit))\b", "operação no repositório remoto"),
    (r"\bgit\s+merge\b", "merge (merge na main = deploy automático em até 5 min)"),
    (r"\bgit\s+rebase\b", "rebase reescreve histórico"),
    (r"\bgit\s+reset\b[^\n;&|]*--hard\b", "reset --hard descarta trabalho"),
    (r"\bgit\s+clean\s+-[a-zA-Z]*f", "git clean apaga arquivos não versionados"),
    (r"\bgit\s+branch\s+-D\b", "apagar branch à força"),
    (r"\bgit\s+(checkout|restore)\b[^\n;&|]*(\s--(\s|$)|\s-f\b|--force|--source|\s-s\s|"
     r"--worktree|\s\.\.?(\s|$)|\s:/)", "checkout/restore que descarta alterações locais"),
    (r"\bgit\s+stash\b(?!\s+(list|show)\b)", "git stash tira as alterações locais da pasta"),
    (r"\bgit\s+rm\b", "git rm apaga arquivos"),
    (r"\bgit\s+commit\b.*--no-verify", "commit sem verificação"),
    (r"\bgit\s+tag\s+-d\b|\bgit\s+push\s+.*--delete\b", "apagar tag ou ref"),
    (r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f|\brm\s+-[a-zA-Z]*f[a-zA-Z]*r", "rm -rf"),
    (r"\b(ssh|scp|rsync|sftp)\b", "acesso a máquina remota (produção?)"),
    (r"deploy/(atualizar|auto-atualizar|backup)\.sh", "script de deploy/backup da VPS"),
    (r"\bdocker\s+compose\b.*\b(up|down|rm)\b|\bdocker-compose\b", "docker compose (infraestrutura)"),
    (r"\bdocker\s+(volume|system)\s+(rm|prune)\b|\bdocker\s+rmi\b", "apagar volumes/imagens Docker"),
    (r"/dados/", "caminho do volume de produção (/dados)"),
    (r"\b(pip|pip3)\s+install\b", "instalar dependência no ambiente local"),
    (r"\bnpm\s+(install|i|publish)\b", "instalar/publicar pacote npm"),
    (r"\bsqlite3\b[^|]*\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|VACUUM|PRAGMA\s+\w+\s*=)",
     "escrita direta em banco SQLite"),
    (r"--dangerously|bypassPermissions|--permission-mode\s+bypass", "desabilitar permissões"),
]

# Checagem de reserva, usada só quando a análise normal quebra (achado 2):
# mais ampla de propósito.
_SENSIVEL = re.compile(
    r"\b(git|gh|rm|mv|cp|dd|truncate|chmod|chown|ln|sqlite3|docker|ssh|scp|rsync|sftp|"
    r"pip3?|npm|curl|wget|sed|perl|tee|python3?|bash|sh|zsh|eval|sudo|find|xargs)\b"
    r"|>|/dados/|backend/|frontend/|deploy/|Dockerfile|requirements|\.claude|"
    r"--dangerously|bypass", re.IGNORECASE)

# Menção a um arquivo de proteção num comando Bash
_REF_PROTEGIDA = re.compile(
    r"\.claude(?:/(?:hooks|settings[\w.-]*|auditoria|agents)\b|/?(?=[\s'\";|&)*]|$))"
    r"|\b(?:test_)?guarda\.py\b|\bsettings(?:\.local)?\.json\b|\bREGRAS\.md\b|\bAGENTES\.md\b")

# Comandos que só leem (os argumentos podem citar um arquivo de proteção)
_LEITURA = {
    "cat", "head", "tail", "less", "more", "grep", "egrep", "fgrep", "ls", "wc",
    "diff", "cmp", "file", "stat", "sha256sum", "shasum", "md5", "md5sum", "jq",
    "du", "realpath", "readlink", "basename", "dirname", "test", "[", "echo", "printf",
    "pwd", "true",
}
_GIT_LEITURA = {"diff", "log", "show", "status", "blame", "ls-files", "grep", "add",
                "commit", "rev-parse", "cat-file", "shortlog"}
_GIT_OPCOES_COM_VALOR = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env"}
# `git -c chave=valor` que executa comando (pager, editor, alias "!", ssh...)
_GIT_C_PERIGOSO = re.compile(r"(?i)pager|editor|sshcommand|fsmonitor|hookspath|alias\.|"
                             r"cmd|command|textconv|external|askpass|credential|proxy|filter\.|exec")
# comandos que apagam/movem/mudam uma pasta inteira: valem também para a pasta-mãe
_DESTRUTIVOS = {"rm", "rmdir", "unlink", "shred", "mv", "chmod", "chown", "chgrp",
                "rsync", "find", "trash"}
_COMMIT_OPCOES_COM_VALOR = {"-m", "--message", "-F", "--file", "-C", "-c", "--author",
                            "--date", "-t", "--template", "--fixup", "--squash",
                            "--cleanup", "--trailer", "--reuse-message", "--reedit-message"}
_SED_SO_LEITURA = re.compile(r"^(\d+|\$)?(,(\d+|\$))?p$|^/[^/]*/p$")
_RE_COMMIT = re.compile(r"\bgit\s+commit\b")


def _falha_de_teste(etapa):
    """Só para os testes: simula uma falha interna. Leva à reserva, nunca a
    uma decisão mais branda que a normal."""
    if os.environ.get("TALDO_GUARDA_FALHA_TESTE") == etapa:
        raise RuntimeError(f"falha simulada ({etapa})")


def _saida(decisao, motivo, evento="PreToolUse"):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": evento,
        "permissionDecision": decisao,
        "permissionDecisionReason": "[guarda TaldoManager] " + motivo,
    }}, ensure_ascii=False))
    return 0


def _rel(caminho, base=None):
    p = caminho if os.path.isabs(caminho) else os.path.join(base or RAIZ, caminho)
    p = os.path.realpath(os.path.abspath(p))
    raiz = os.path.realpath(RAIZ)
    if p == raiz or p.startswith(raiz + os.sep):
        return os.path.relpath(p, raiz).replace(os.sep, "/")
    return None


def eh_producao(rel):
    if rel is None:
        return False
    rel = rel.replace(os.sep, "/")
    if any(rel.startswith(l) for l in LIVRES):
        return False
    return any(rel == p or rel.startswith(p) for p in PRODUCAO)


def _home_claude():
    return os.path.realpath(os.path.join(os.path.expanduser("~"), ".claude"))


def eh_protegido(caminho, base=None):
    """Caminho (absoluto, ou relativo a `base`/raiz) de um arquivo de proteção."""
    if not caminho:
        return False
    caminho = os.path.expanduser(caminho)
    rel = _rel(caminho, base)
    if rel is not None:
        return rel == ".claude" or any(rel.startswith(p) for p in PROTEGIDOS)
    p = os.path.realpath(os.path.abspath(os.path.join(base or RAIZ, caminho)))
    return os.path.dirname(p) == _home_claude() and os.path.basename(p).startswith("settings")


def _contem_protecao(caminho, base=None):
    """O caminho é uma pasta-mãe de um arquivo de proteção (raiz, `.claude`, `~/.claude`)."""
    rel = _rel(os.path.expanduser(caminho), base)
    if rel is not None:
        return rel == "." or any(p.startswith(rel.rstrip("/") + "/") for p in PROTEGIDOS)
    p = os.path.realpath(os.path.abspath(os.path.join(base or RAIZ, os.path.expanduser(caminho))))
    return p == _home_claude() or _home_claude().startswith(p.rstrip(os.sep) + os.sep)


# ---------------------------------------------------------------------------
# análise do texto do comando
# ---------------------------------------------------------------------------

_HEREDOC = re.compile(r"<<-?[ \t]*(['\"]?)([^\s'\"<>|;&()]+)\1([^\n]*)\n(.*?)\n[ \t]*\2[ \t]*(?=\n|$)",
                      re.DOTALL)
_MENSAGEM = re.compile(r"(\s(?:-[a-zA-Z]*m|--message)(?:[ \t]+|=|(?=[\"'])))"
                       r"(\"(?:\\.|[^\"\\])*\"|'[^']*')")


def sem_mensagens(cmd):
    """Tira só o texto das mensagens de commit (achado 3): `-m "..."` e o
    heredoc de `git commit -F -`. Qualquer outro heredoc continua no texto e
    é analisado. Mensagem com `$(...)` ou crase fica (o shell executa)."""

    def heredoc(m):
        antes = re.split(r"\n|;|&&|\|\|", cmd[:m.start()])[-1]
        do_commit = (re.search(r"\bgit\b.*\bcommit\b", antes)
                     and re.search(r"(?:-F|--file)(?:\s*|=)-(?:\s|$)", antes + " "))
        if do_commit:
            return f"<<{m.group(2)}{m.group(3)}\n"
        return m.group(0)

    h = _HEREDOC.sub(heredoc, cmd)

    def mensagem(m):
        # só a mensagem de um `git commit` (3ª revisão: `bash -cm '...'` é código)
        if not re.search(r"\bgit\b.*\bcommit\b", re.split(r"\n|;|&&|\|\|", h[:m.start()])[-1]):
            return m.group(0)
        texto = m.group(2)
        if texto.startswith('"') and ("$(" in texto or "`" in texto):
            return m.group(0)
        return m.group(1) + "MSG"

    return _MENSAGEM.sub(mensagem, h)


def _substituicoes(cmd):
    """Conteúdo de cada `$(...)` (com parênteses aninhados) e de cada crase."""
    saida, i = [], 0
    while i < len(cmd):
        if cmd.startswith("$(", i):
            nivel, j = 1, i + 2
            while j < len(cmd) and nivel:
                nivel += {"(": 1, ")": -1}.get(cmd[j], 0)
                j += 1
            saida.append(cmd[i + 2:j - 1] if nivel == 0 else cmd[i + 2:])
            i += 2   # continua DENTRO: pega as aninhadas também
            continue
        if cmd[i] == "`":
            fim = cmd.find("`", i + 1)
            saida.append(cmd[i + 1:] if fim < 0 else cmd[i + 1:fim])
            i = len(cmd) if fim < 0 else fim + 1
            continue
        i += 1
    return saida


def _segmentos(cmd, _nivel=0):
    """Comandos simples, em ordem: separa em `; & | ( ) crase` e quebra de
    linha fora de aspas. O conteúdo de `$(...)` e de crases (mesmo dentro de
    aspas duplas, onde o shell executa) também vira segmento."""
    segs, atual, aspas, i = [], [], None, 0
    while i < len(cmd):
        ch = cmd[i]
        if aspas == "'":
            atual.append(ch)
            if ch == "'":
                aspas = None
        elif aspas == '"':
            if ch == "\\" and i + 1 < len(cmd):
                atual.append(cmd[i:i + 2])
                i += 2
                continue
            atual.append(ch)
            if ch == '"':
                aspas = None
        elif ch in "'\"":
            aspas = ch
            atual.append(ch)
        elif ch == "\\" and i + 1 < len(cmd):
            atual.append(cmd[i:i + 2])
            i += 2
            continue
        elif ch in ";&|\n()`":
            segs.append("".join(atual))
            atual = []
        else:
            atual.append(ch)
        i += 1
    segs.append("".join(atual))
    if _nivel < 8:
        for interno in _substituicoes(cmd):
            segs += _segmentos(interno, _nivel + 1)
    return [s.strip() for s in segs if s.strip()]


def _tokens(seg, manter_atribuicoes=False):
    lex = shlex.shlex(seg, posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    toks = list(lex)
    while not manter_atribuicoes and toks and re.match(r"^[A-Za-z_]\w*=", toks[0]):   # VAR=valor cmd
        toks.pop(0)
    return toks


def _eh_redirecao(t):
    return set(t) <= set("<>&|0123456789") and ("<" in t or ">" in t)


def _git_sub(toks, base):
    """(subcomando, argumentos, pasta, valores de -c) de um `git ...`."""
    i, pasta, configs = 1, base, []
    while i < len(toks) and toks[i].startswith("-"):
        t = toks[i]
        if t.startswith("--config-env="):
            configs.append(t.split("=", 1)[1])
            i += 1
        elif t.startswith("--exec-path"):
            configs.append("exec-path")   # troca os executáveis do git
            i += 1
        elif t in _GIT_OPCOES_COM_VALOR:
            valor = toks[i + 1] if i + 1 < len(toks) else ""
            if t == "-C" and pasta is not None:
                pasta = os.path.join(pasta, os.path.expanduser(valor))
            if t in ("-c", "--config-env"):
                configs.append(valor)
            i += 2
        else:
            i += 1
    if i >= len(toks):
        return None, [], pasta, configs
    return toks[i], toks[i + 1:], pasta, configs


def _git_normalizado(limpo):
    """Cada `git ...` reescrito sem as opções globais (`-P`, `-C x`, `-c k=v`,
    `--git-dir x`...), para os padrões de CRITICOS enxergarem o subcomando."""
    linhas = []
    for seg in _segmentos(limpo):
        try:
            toks = _tokens(seg)
        except ValueError:
            continue
        if toks and os.path.basename(toks[0]) == "git":
            sub, args, _, _ = _git_sub(toks, None)
            if sub:
                linhas.append(" ".join(["git", sub] + args))
    return "\n".join(linhas)


def _git_c_perigoso(limpo):
    for seg in _segmentos(limpo):
        try:
            toks = _tokens(seg)
        except ValueError:
            continue
        if toks and os.path.basename(toks[0]) == "git":
            for c in _git_sub(toks, None)[3]:
                if _GIT_C_PERIGOSO.search(c.split("=", 1)[0]):
                    return c
    return None


def _redirecoes_de_escrita(toks):
    alvos = []
    for i, t in enumerate(toks):
        if ">" in t and _eh_redirecao(t):
            alvo = toks[i + 1] if i + 1 < len(toks) else ""
            if alvo == "/dev/null" or (t.endswith("&") and alvo.isdigit()) or re.match(r"^\d?>&\d$", t):
                continue
            alvos.append(alvo)
    return alvos


def _python_do_guarda(args):
    if "-c" in args:
        return False
    if "-m" in args:
        i = args.index("-m")
        if i + 1 >= len(args) or args[i + 1] != "unittest":
            return False
        args = args[:i] + args[i + 2:]
    pos = [a for a in args if not a.startswith("-")]
    if not pos:
        return False
    if os.path.basename(pos[0]) not in ("guarda.py", "test_guarda.py"):
        return False
    return all(re.match(r"^(bash|arquivo|fim|[A-Za-z_][\w.]*)$", a) for a in pos[1:])


def _so_leitura(toks):
    """O comando, pelos argumentos, só lê (redirecionamentos à parte)."""
    if not toks:
        return True
    cmd, args = os.path.basename(toks[0]), [t for t in toks[1:]]
    if cmd in _LEITURA:
        return True
    if cmd == "tree":
        return not any(a == "-o" or a.startswith("-o") for a in args)
    if cmd == "rg":
        return not any(a.startswith("--pre") for a in args)
    if cmd == "sed":
        # só a forma de leitura de linhas: sed [-n|-E|-r] 'N,Mp' | '/re/p' arquivos
        opcoes = [a for a in args if a.startswith("-")]
        resto = [a for a in args if not a.startswith("-")]
        return (set(opcoes) <= {"-n", "-E", "-r"} and bool(resto)
                and bool(_SED_SO_LEITURA.match(resto[0])))
    if cmd == "find":
        return not any(a in ("-delete", "-exec", "-execdir", "-ok", "-okdir", "-fls")
                       or a.startswith("-fprint") for a in args)
    if cmd == "git":
        sub, gargs, _, configs = _git_sub(toks, None)
        if configs and any(_GIT_C_PERIGOSO.search(c.split("=", 1)[0]) for c in configs):
            return False
        if any(a.startswith("--output") or a in ("-O", "--open-files-in-pager") or a.startswith("-O")
               for a in gargs):
            return False
        return sub in _GIT_LEITURA
    if re.match(r"^python3?(\.\d+)?$", cmd):
        return _python_do_guarda(args)
    return False


def _argumentos(toks):
    """Possíveis caminhos: argumentos que não são opção e valores `--opcao=x`."""
    saida, i = [], 1
    while i < len(toks):
        t = toks[i]
        if _eh_redirecao(t):
            i += 2
            continue
        if t.startswith("-"):
            if "=" in t:
                saida.append(t.split("=", 1)[1])
        else:
            saida.append(t)
        i += 1
    return saida


def _nova_pasta(toks, pasta):
    """Pasta depois de `cd`/`pushd` (None = desconhecida)."""
    args = list(toks[1:])
    while args and args[0].startswith("-") and args[0] != "-":   # -P, -L, --
        if args.pop(0) == "--":
            break
    if args and args[0] == "-":
        return None                          # `cd -`: volta para onde?
    alvo = os.path.expanduser(args[0]) if args else os.path.expanduser("~")
    if "$" in alvo or "`" in alvo:
        return None
    if os.path.isabs(alvo):
        return alvo
    return None if pasta is None else os.path.join(pasta, alvo)


def _percorrer(limpo, cwd):
    """(segmento, tokens, tokens com VAR=, pasta) em ordem, acompanhando cd."""
    pasta = cwd
    for seg in _segmentos(limpo):
        try:
            toks, com = _tokens(seg), _tokens(seg, manter_atribuicoes=True)
        except ValueError:
            yield seg, None, None, pasta
            continue
        nome = os.path.basename(toks[0]) if toks else ""
        if nome in ("cd", "pushd"):
            pasta = _nova_pasta(toks, pasta)
            continue
        if nome == "popd":
            pasta = None
            continue
        yield seg, toks, com, pasta


def _mexe_em_protecao(limpo, cwd):
    """Segmentos que podem alterar um arquivo de proteção (achado 4).

    Não basta procurar `.claude/hooks` no texto (2ª revisão): o caminho de
    cada argumento é RESOLVIDO na pasta em que o comando roda — acompanhando
    `cd` (com `-P`, `--`), normalizando `./`, `//` e `..`, expandindo globs —
    e vale também para a pasta-mãe nos comandos destrutivos (`rm -r .claude`,
    `rm -r .`). Argumento com variável ou pasta desconhecida, e `xargs`
    (3ª revisão), contam como suspeitos quando o comando cita uma proteção."""
    menciona = bool(_REF_PROTEGIDA.search(limpo))
    achados, alimentados = [], []
    for seg, toks, _, pasta in _percorrer(limpo, cwd):
        if toks is None:
            if _REF_PROTEGIDA.search(seg):
                achados.append(seg)
            continue
        if not toks:
            continue
        cmd = os.path.basename(toks[0])
        if cmd in ("xargs", "parallel"):
            alimentados.append(seg)
        so_leitura = _so_leitura(toks)
        candidatos = _redirecoes_de_escrita(toks) + ([] if so_leitura else _argumentos(toks))
        if not so_leitura and _REF_PROTEGIDA.search(seg):
            achados.append(seg)
            continue
        for a in candidatos:
            a = os.path.expanduser(a)
            if "$" in a or "`" in a or (pasta is None and not os.path.isabs(a)):
                if menciona:
                    achados.append(seg)
                    break
                continue
            alvos = [a]
            if any(ch in a for ch in "*?["):
                alvos = glob.glob(a if os.path.isabs(a) else os.path.join(pasta, a)) or [a]
            if any(eh_protegido(x, pasta) or _REF_PROTEGIDA.search(x)
                   or (cmd in _DESTRUTIVOS and _contem_protecao(x, pasta)) for x in alvos):
                achados.append(seg)
                break
    if menciona and alimentados:
        achados += alimentados
    return achados


def _banco_padrao(limpo, cwd):
    """(nega_pytest, mexe_no_banco) resolvendo `TALDO_DB=`/`export` e os
    argumentos na pasta de cada comando (3ª revisão: `cd backend && ...`)."""
    alvo = os.path.realpath(os.path.join(RAIZ, BANCO_PADRAO))

    def eh_padrao(v, pasta):
        v = os.path.expanduser(v.strip("'\""))
        if not v or "$" in v or (pasta is None and not os.path.isabs(v)):
            return False
        return os.path.realpath(os.path.join(pasta or RAIZ, v)) == alvo

    exportado = nega = mexe = False
    for _, toks, com, pasta in _percorrer(limpo, cwd):
        if not toks:
            continue
        nome = os.path.basename(toks[0])
        if nome == "export":
            for t in toks[1:]:
                if t.startswith("TALDO_DB="):
                    exportado = eh_padrao(t.split("=", 1)[1], pasta)
            continue
        if nome == "unset" and "TALDO_DB" in toks:
            exportado = False
            continue
        local = None
        for t in com:
            if not re.match(r"^[A-Za-z_]\w*=", t):
                break
            if t.startswith("TALDO_DB="):
                local = eh_padrao(t.split("=", 1)[1], pasta)
        usa_padrao = local if local is not None else exportado
        if usa_padrao and any(os.path.basename(t) == "pytest" for t in toks):
            nega = True
        if nome in ("sqlite3", "rm", "mv", "cp", "truncate", "shred") and any(
                eh_padrao(a, pasta) for a in _argumentos(toks)):
            mexe = True
        if any(eh_padrao(a, pasta) for a in _redirecoes_de_escrita(toks)):
            mexe = True
    return nega, mexe


# ---------------------------------------------------------------------------
# commit: quais arquivos entram (achado 1)
# ---------------------------------------------------------------------------

def _git(*args):
    r = subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True, timeout=20)
    if r.returncode != 0:
        raise RuntimeError(f"git {args[0]} falhou: {r.stderr.strip()[:200]}")
    return r.stdout


def _alterados():
    """[(estado XY, caminho relativo à raiz)] de `git status`, com não versionados."""
    itens = _git("status", "--porcelain=v1", "-uall", "-z").split("\0")
    saida, i = [], 0
    while i < len(itens):
        e = itens[i]
        i += 1
        if len(e) < 4:
            continue
        xy, caminho = e[:2], e[3:]
        if xy[0] in "RC":
            i += 1   # o caminho de origem vem a seguir
        saida.append((xy, caminho))
    return saida


def _expandir(specs, pasta, alterados):
    todos = [c for _, c in alterados]
    arquivos = set()
    for spec in specs:
        if (spec in ("-A", "--all", "-u", "--update") or spec.startswith(":")
                or spec.startswith("--pathspec-from-file")):
            arquivos.update(todos)   # `:/`, `:(top)...`, lista em arquivo: tudo (3ª revisão)
            continue
        if spec.startswith("-"):
            continue
        rel = _rel(os.path.expanduser(spec), pasta)
        if rel is None:
            continue
        if rel == ".":
            arquivos.update(todos)
        elif any(ch in rel for ch in "*?["):
            arquivos.update(c for c in todos if fnmatch.fnmatch(c, rel))
        else:
            dentro = [c for c in todos if c == rel or c.startswith(rel + "/")]
            arquivos.update(dentro or [rel])
    return arquivos


def _arquivos_do_commit(limpo, cwd):
    staged = [l for l in _git("diff", "--cached", "--name-only", "-z").split("\0") if l]
    arquivos = set(staged)
    alterados = None
    for seg in _segmentos(limpo):
        toks = _tokens(seg)
        if not toks or os.path.basename(toks[0]) != "git":
            continue
        sub, args, pasta, _ = _git_sub(toks, cwd)
        if sub not in ("add", "commit"):
            continue
        if alterados is None:
            alterados = _alterados()
        specs, i = [], 0
        while i < len(args):
            a = args[i]
            if set(a) <= set("<>&|0123456789") and ("<" in a or ">" in a):
                i += 2   # redirecionamento e o alvo
                continue
            if sub == "commit":
                if a in ("-a", "--all") or (re.match(r"^-[a-zA-Z]+$", a) and "a" in a):
                    arquivos.update(c for xy, c in alterados if xy != "??")
                if a in _COMMIT_OPCOES_COM_VALOR or re.match(r"^-[a-zA-Z]*[mFCct]$", a):
                    i += 2
                    continue
                if a.startswith("--pathspec-from-file"):
                    specs.append(a)
                    i += 1 if "=" in a else 2
                    continue
                if a.startswith("-"):
                    i += 1
                    continue
            specs.append(a)
            i += 1
        arquivos |= _expandir(specs, pasta, alterados)
    return sorted(arquivos)


def _testes_de_auditoria():
    """Roda tests/auditoria no Docker (~15 s). Devolve (ok, resumo) ou (None, motivo)."""
    try:
        if subprocess.run(["docker", "image", "inspect", "taldo-auditoria:py312"],
                          capture_output=True, timeout=20).returncode != 0:
            return None, "imagem taldo-auditoria:py312 não encontrada (ver REGRAS.md)"
        r = subprocess.run(
            ["docker", "run", "--rm", "-v", f"{RAIZ}:/repo:ro", "-e", "PYTHONDONTWRITEBYTECODE=1",
             "-w", "/repo/backend", "taldo-auditoria:py312", "python", "-m", "pytest",
             "-p", "no:cacheprovider", "tests/auditoria", "-q", "-W", "ignore"],
            capture_output=True, text=True, timeout=240)
    except (OSError, subprocess.SubprocessError) as e:
        return None, f"Docker indisponível ({type(e).__name__}: {e})"
    linhas = [l for l in r.stdout.splitlines() if l.strip()]
    return r.returncode == 0, (linhas[-1] if linhas else r.stderr[-300:])


def _commit(limpo, cwd):
    """None = sem opinião; (decisão, motivo) caso contrário."""
    if not _RE_COMMIT.search(limpo + "\n" + _git_normalizado(limpo)):
        return None
    _falha_de_teste("commit")
    arquivos = _arquivos_do_commit(limpo, cwd)
    prod = [a for a in arquivos if eh_producao(a)]
    partes = []
    if prod:
        partes.append(f"o commit inclui código de produção {prod[:5]}")
    if any(a.startswith("backend/") for a in arquivos):
        ok, resumo = _testes_de_auditoria()
        if ok is False:
            return "deny", f"testes de auditoria falhando, commit recusado: {resumo}"
        if ok is None:
            partes.append(f"não deu para rodar os testes antes do commit: {resumo}")
        elif prod:
            partes.append(f"testes de auditoria: {resumo}")
    if partes:
        return "ask", "; ".join(partes) + ". Autorizado?"
    return None


# ---------------------------------------------------------------------------
# Bash
# ---------------------------------------------------------------------------

def _pytest_no_banco_padrao(cmd):
    if not re.search(r"\bpytest\b", cmd):
        return False
    m = re.search(r"TALDO_DB=(\S+)", cmd)
    return bool(m and m.group(1).strip("'\"").rstrip("/").endswith(BANCO_PADRAO))


def bash(evento):
    _falha_de_teste("analise")
    cmd = evento.get("tool_input", {}).get("command", "") or ""
    cwd = evento.get("cwd") or RAIZ
    if _pytest_no_banco_padrao(cmd):
        return _saida("deny", "pytest com TALDO_DB apontando para o banco padrão do projeto. "
                              "Use o SQLite temporário do conftest.")
    limpo = sem_mensagens(cmd)
    nega_pytest, mexe_no_banco = _banco_padrao(limpo, cwd)
    if nega_pytest:
        return _saida("deny", "pytest com TALDO_DB apontando para o banco padrão do projeto. "
                              "Use o SQLite temporário do conftest.")
    normal = limpo + "\n" + _git_normalizado(limpo)
    motivos = []
    if mexe_no_banco or (BANCO_PADRAO in limpo
                         and re.search(r"\b(sqlite3|rm|mv|cp|truncate)\b|>", limpo)):
        motivos.append("comando mexe no banco padrão do projeto")
    motivos += [m for padrao, m in CRITICOS if re.search(padrao, normal, re.IGNORECASE)]
    perigoso = _git_c_perigoso(limpo)
    if perigoso:
        motivos.append(f"git -c que pode executar comando ({perigoso[:60]!r})")
    protecao = _mexe_em_protecao(limpo, cwd)
    if protecao:
        motivos.append("comando altera arquivo de proteção (hooks, permissões, regras ou "
                       f"agentes): {protecao[0][:80]!r}")
    # os motivos acima ficam garantidos mesmo se a verificação do commit quebrar
    try:
        decisao = _commit(limpo, cwd)
    except Exception as e:   # noqa: BLE001
        decisao = ("ask", f"não deu para verificar o commit ({type(e).__name__}: {e})")
    if decisao and decisao[0] == "deny":
        return _saida(*decisao)
    if decisao:
        motivos.insert(0, decisao[1])
    if motivos:
        return _saida("ask", "operação crítica: " + "; ".join(dict.fromkeys(motivos)))
    return 0


# ---------------------------------------------------------------------------
# Edit / Write
# ---------------------------------------------------------------------------

def arquivo(evento):
    _falha_de_teste("analise")
    ti = evento.get("tool_input", {})
    caminho = ti.get("file_path") or ti.get("notebook_path") or ""
    if eh_protegido(caminho):
        return _saida("ask", f"{_rel(caminho) or caminho} é arquivo de proteção (hooks, "
                             "permissões, regras ou agentes). Alterar exige a sua aprovação.")
    rel = _rel(caminho) if caminho else None
    if eh_producao(rel):
        return _saida("ask", f"{rel} é código de produção. Correções exigem autorização "
                             "explícita (R1, R2 e R10 ainda não autorizados).")
    return 0


# ---------------------------------------------------------------------------
# Stop: alterações inesperadas em produção
# ---------------------------------------------------------------------------

def fim(evento):
    if evento.get("stop_hook_active"):
        return 0
    r = subprocess.run(["git", "status", "--porcelain"], cwd=RAIZ,
                       capture_output=True, text=True, timeout=20)
    prod = [l[3:] for l in r.stdout.splitlines() if eh_producao(l[3:].strip('"'))]
    if prod:
        print(json.dumps({"systemMessage":
            "[guarda TaldoManager] arquivos de produção alterados e não commitados: "
            + ", ".join(prod[:8]) + (" ..." if len(prod) > 8 else "")}, ensure_ascii=False))
    return 0


# ---------------------------------------------------------------------------
# falha interna (achado 2)
# ---------------------------------------------------------------------------

def _reserva(modo, texto, erro):
    """A análise quebrou: sensível → ask; comum → passa com aviso."""
    if modo in ("bash", "arquivo") and (texto is None or _SENSIVEL.search(texto)):
        return _saida("ask", f"erro interno do guarda ({erro}). Por segurança, confirme "
                             "esta operação.")
    print(f"guarda: erro interno ({erro}); operação comum liberada", file=sys.stderr)
    return 0


def main():
    modo = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        bruto = sys.stdin.read()
    except Exception as e:   # noqa: BLE001
        return 0 if modo == "fim" else _reserva(modo, None, f"stdin: {e}")
    try:
        evento = json.loads(bruto)
    except ValueError as e:
        return 0 if modo == "fim" else _reserva(modo, bruto, f"entrada inválida: {e}")
    if not isinstance(evento, dict):
        return 0 if modo == "fim" else _reserva(modo, None, "o evento não é um objeto JSON")
    try:
        return {"bash": bash, "arquivo": arquivo, "fim": fim}[modo](evento)
    except Exception as e:   # noqa: BLE001
        if modo == "fim":
            print(f"guarda: erro interno ignorado no fim: {e}", file=sys.stderr)
            return 0
        ti = evento.get("tool_input") if isinstance(evento.get("tool_input"), dict) else {}
        texto = ti.get("command") if modo == "bash" else (ti.get("file_path") or ti.get("notebook_path"))
        return _reserva(modo, texto if isinstance(texto, str) else None, f"{type(e).__name__}: {e}")


if __name__ == "__main__":
    sys.exit(main())
