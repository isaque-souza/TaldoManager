#!/usr/bin/env python3
"""Hooks de proteção da auditoria do TaldoManager.

Uso (chamado pelo Claude Code, JSON do evento no stdin):
    python3 .claude/hooks/guarda.py bash      # PreToolUse  Bash
    python3 .claude/hooks/guarda.py arquivo   # PreToolUse  Edit|Write|NotebookEdit
    python3 .claude/hooks/guarda.py fim       # Stop

Decisões (ver .claude/hooks/README.md):
- "deny": só para o que nunca é legítimo na auditoria (pytest contra o banco
  padrão; commit com testes de auditoria falhando).
- "ask": operação crítica ou destrutiva. O Claude Code pede a sua aprovação;
  nada é bloqueado em definitivo.
- silêncio: todo o resto segue o fluxo normal de permissões.

Só biblioteca padrão (roda no Python 3.9 do macOS). Qualquer erro interno
deixa passar (exit 0): o hook nunca trava o trabalho por defeito próprio.
"""

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

BANCO_PADRAO = "backend/data/database/taldo_manager.db"

# padrão -> motivo (pede aprovação)
CRITICOS = [
    (r"\bgit\s+push\b", "push para o GitHub (exige autorização explícita)"),
    (r"\bgh\s+pr\s+(create|merge)\b", "abrir ou fazer merge de PR (exige autorização explícita)"),
    (r"\bgh\s+(release|repo\s+(delete|edit))\b", "operação no repositório remoto"),
    (r"\bgit\s+merge\b", "merge (merge na main = deploy automático em até 5 min)"),
    (r"\bgit\s+rebase\b", "rebase reescreve histórico"),
    (r"\bgit\s+reset\s+--hard\b", "reset --hard descarta trabalho"),
    (r"\bgit\s+clean\s+-[a-zA-Z]*f", "git clean apaga arquivos não versionados"),
    (r"\bgit\s+branch\s+-D\b", "apagar branch à força"),
    (r"\bgit\s+(checkout|restore)\s+(--\s+)?\.(\s|$)", "descartar alterações locais"),
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


def _saida(decisao, motivo, evento="PreToolUse"):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": evento,
        "permissionDecision": decisao,
        "permissionDecisionReason": "[guarda TaldoManager] " + motivo,
    }}, ensure_ascii=False))
    return 0


def _rel(caminho):
    p = os.path.abspath(os.path.join(RAIZ, caminho)) if not os.path.isabs(caminho) else caminho
    p = os.path.realpath(p)
    raiz = os.path.realpath(RAIZ)
    if p == raiz or p.startswith(raiz + os.sep):
        return os.path.relpath(p, raiz)
    return None


def eh_producao(rel):
    if rel is None:
        return False
    rel = rel.replace(os.sep, "/")
    if any(rel.startswith(l) for l in LIVRES):
        return False
    return any(rel == p or rel.startswith(p) for p in PRODUCAO)


# ---------------------------------------------------------------------------
# Bash
# ---------------------------------------------------------------------------

def _pytest_no_banco_padrao(cmd):
    if not re.search(r"\bpytest\b", cmd):
        return False
    m = re.search(r"TALDO_DB=(\S+)", cmd)
    return bool(m and m.group(1).strip("'\"").rstrip("/").endswith(BANCO_PADRAO))


def _commit_staged():
    r = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=RAIZ,
                       capture_output=True, text=True, timeout=20)
    return [l for l in r.stdout.splitlines() if l]


def _testes_de_auditoria():
    """Roda tests/auditoria no Docker (~15 s). Devolve (ok, resumo) ou (None, motivo)."""
    if subprocess.run(["docker", "image", "inspect", "taldo-auditoria:py312"],
                      capture_output=True, timeout=20).returncode != 0:
        return None, "imagem taldo-auditoria:py312 não encontrada (ver REGRAS.md)"
    r = subprocess.run(
        ["docker", "run", "--rm", "-v", f"{RAIZ}:/repo:ro", "-e", "PYTHONDONTWRITEBYTECODE=1",
         "-w", "/repo/backend", "taldo-auditoria:py312", "python", "-m", "pytest",
         "-p", "no:cacheprovider", "tests/auditoria", "-q", "-W", "ignore"],
        capture_output=True, text=True, timeout=240)
    linhas = [l for l in r.stdout.splitlines() if l.strip()]
    return r.returncode == 0, (linhas[-1] if linhas else r.stderr[-300:])


def _commit(cmd):
    """None = sem opinião; (decisão, motivo) caso contrário."""
    if not re.search(r"\bgit\s+commit\b", cmd):
        return None
    arquivos = _commit_staged()
    # `git commit -a`/`-am` também leva os modificados não preparados
    if re.search(r"\bgit\s+commit\b[^&|;]*\s-[a-zA-Z]*a", cmd):
        r = subprocess.run(["git", "diff", "--name-only"], cwd=RAIZ,
                           capture_output=True, text=True, timeout=20)
        arquivos += [l for l in r.stdout.splitlines() if l]
    prod = [a for a in arquivos if eh_producao(a)]
    if any(a.startswith("backend/") for a in arquivos):
        ok, resumo = _testes_de_auditoria()
        if ok is False:
            return "deny", f"testes de auditoria falhando, commit recusado: {resumo}"
        if ok is None:
            return "ask", f"não deu para rodar os testes antes do commit: {resumo}"
        if prod:
            return "ask", f"o commit inclui código de produção {prod[:5]}. Testes de auditoria: {resumo}. Autorizado?"
    elif prod:
        return "ask", f"o commit inclui arquivos de produção {prod[:5]}. Autorizado?"
    return None


def sem_mensagens(cmd):
    """Tira corpos de heredoc e mensagens -m/-F: o texto de um commit não é comando."""
    cmd = re.sub(r"<<-?\s*['\"]?(\w+)['\"]?[^\n]*\n.*?\n\s*\1\b", " ", cmd, flags=re.DOTALL)
    cmd = re.sub(r"\s-(m|F)\s*(\"(\\.|[^\"])*\"|'[^']*')", " ", cmd)
    return cmd


def bash(evento):
    cmd = evento.get("tool_input", {}).get("command", "") or ""
    if _pytest_no_banco_padrao(cmd):
        return _saida("deny", "pytest com TALDO_DB apontando para o banco padrão do projeto. "
                              "Use o SQLite temporário do conftest.")
    limpo = sem_mensagens(cmd)
    motivos = []
    if BANCO_PADRAO in limpo and re.search(r"\b(sqlite3|rm|mv|cp|truncate)\b|>", limpo):
        motivos.append("comando mexe no banco padrão do projeto")
    motivos += [m for padrao, m in CRITICOS if re.search(padrao, limpo, re.IGNORECASE)]
    decisao = _commit(limpo)
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
    ti = evento.get("tool_input", {})
    caminho = ti.get("file_path") or ti.get("notebook_path") or ""
    rel = _rel(caminho) if caminho else None
    if eh_producao(rel):
        return _saida("ask", f"{rel} é código de produção. Correções exigem autorização "
                             "explícita (R1, R2 e R10 ainda não autorizados).")
    if rel and rel.replace(os.sep, "/").startswith(".claude/settings"):
        return _saida("ask", f"{rel} muda permissões ou hooks.")
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


def main():
    modo = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        evento = json.load(sys.stdin)
    except ValueError:
        return 0
    try:
        return {"bash": bash, "arquivo": arquivo, "fim": fim}[modo](evento)
    except Exception as e:  # o hook nunca trava o trabalho por defeito próprio
        print(f"guarda: erro interno ignorado: {e}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
