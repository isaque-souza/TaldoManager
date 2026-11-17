"""Testes dos hooks de proteção.  Rodar:  python3 .claude/hooks/test_guarda.py -v

Chamam o guarda.py como o Claude Code chama (JSON no stdin) e conferem a
decisão. Nenhum comando testado é executado de verdade.
"""

import json
import os
import subprocess
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
GUARDA = os.path.join(AQUI, "guarda.py")


def decidir(modo, evento):
    r = subprocess.run([sys.executable, GUARDA, modo], input=json.dumps(evento),
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    if not r.stdout.strip():
        return None, ""
    saida = json.loads(r.stdout)
    hs = saida.get("hookSpecificOutput", {})
    return hs.get("permissionDecision"), hs.get("permissionDecisionReason", "")


def bash(cmd):
    return decidir("bash", {"tool_name": "Bash", "tool_input": {"command": cmd}})


def editar(caminho):
    return decidir("arquivo", {"tool_name": "Edit", "tool_input": {"file_path": caminho}})


class Bash(unittest.TestCase):
    def test_comandos_comuns_passam(self):
        for cmd in ["ls", "git status --short", "git log --oneline -3", "git diff --stat",
                    "grep -rn random backend/app", "git checkout -b auditoria/03-baseline",
                    "docker run --rm -v \"$PWD\":/repo:ro -w /repo/backend taldo-auditoria:py312 "
                    "python -m pytest tests/auditoria -q",
                    "python3 -I AUDITORIA/scripts/diagnostico_integridade.py ~/copia.db"]:
            self.assertEqual(bash(cmd)[0], None, cmd)

    def test_pytest_no_banco_padrao_e_negado(self):
        d, m = bash("TALDO_DB=backend/data/database/taldo_manager.db python -m pytest tests")
        self.assertEqual(d, "deny")
        d, _ = bash("TALDO_DB=/tmp/x.db python -m pytest tests")
        self.assertIsNone(d)

    def test_operacoes_criticas_pedem_aprovacao(self):
        for cmd in ["git push origin auditoria/01", "git push --force",
                    "gh pr create --title x", "gh pr merge 131",
                    "git checkout main && git merge auditoria/01",
                    "git reset --hard HEAD~1", "git clean -fd", "git branch -D velha",
                    "rm -rf backend/tests", "ssh root@vps", "scp a vps:/tmp",
                    "bash deploy/atualizar.sh", "docker compose -f deploy/docker-compose.yml up -d",
                    "cp copia.db /dados/taldo_manager.db",
                    "sqlite3 copia.db 'DELETE FROM partida'",
                    "sqlite3 backend/data/database/taldo_manager.db .tables",
                    "pip3 install pytest", "git commit --no-verify -m x",
                    "claude --dangerously-skip-permissions"]:
            self.assertEqual(bash(cmd)[0], "ask", cmd)

    def test_mensagem_de_commit_nao_dispara_falso_alarme(self):
        cmd = "git commit -q -F - <<'EOF'\nnão faz git push nem rm -rf\nEOF"
        self.assertIsNone(bash(cmd)[0])
        self.assertIsNone(bash('git commit -m "documenta o git push e o ssh"')[0])

    def test_push_encadeado_depois_do_commit_e_pego(self):
        d, m = bash('git commit -m "x" && git push')
        self.assertEqual(d, "ask")
        self.assertIn("push", m)

    def test_sqlite_so_leitura_passa(self):
        self.assertIsNone(bash("sqlite3 /tmp/copia.db 'SELECT COUNT(*) FROM partida'")[0])


class Arquivos(unittest.TestCase):
    def test_producao_pede_aprovacao(self):
        for c in ["backend/app/domain/partida.py", "backend/app/db/schema.sql",
                  "frontend/js/app.js", "deploy/backup.sh", "Dockerfile",
                  "backend/requirements.txt", "backend/scripts/simular.py"]:
            self.assertEqual(editar(c)[0], "ask", c)

    def test_auditoria_testes_e_docs_passam(self):
        for c in ["AUDITORIA/03_X.md", "AUDITORIA/scripts/novo.py",
                  "backend/tests/auditoria/test_auditoria_x.py", ".claude/skills/x/SKILL.md",
                  "/tmp/qualquer.txt"]:
            self.assertIsNone(editar(c)[0], c)

    def test_settings_pede_aprovacao(self):
        self.assertEqual(editar(".claude/settings.json")[0], "ask")

    def test_caminho_absoluto_de_producao(self):
        raiz = os.path.abspath(os.path.join(AQUI, "..", ".."))
        self.assertEqual(editar(os.path.join(raiz, "backend/app/main.py"))[0], "ask")


class Robustez(unittest.TestCase):
    def test_entrada_invalida_nao_trava(self):
        r = subprocess.run([sys.executable, GUARDA, "bash"], input="não é json",
                           capture_output=True, text=True)
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_fim_nao_trava(self):
        r = subprocess.run([sys.executable, GUARDA, "fim"], input="{}",
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
