"""Testes dos hooks de proteção.  Rodar:  python3 .claude/hooks/test_guarda.py -v

Chamam o guarda.py como o Claude Code chama (JSON no stdin) e conferem a
decisão. Nenhum comando testado é executado de verdade.

Herméticos (Auditoria 03): cada teste usa uma CÓPIA do guarda.py dentro de
um repositório git temporário, com um `docker` falso no PATH — o resultado
não depende do que estiver preparado no seu repositório nem do Docker real.
"""

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
GUARDA = os.path.join(AQUI, "guarda.py")
GIT = shutil.which("git")

DOCKER_FALSO = {
    # `docker image inspect` responde; `docker run` imprime o resumo do pytest
    "ok": "#!/bin/sh\n[ \"$1\" = image ] && exit 0\necho '32 passed, 7 xfailed in 15.0s'\nexit 0\n",
    "falha": "#!/bin/sh\n[ \"$1\" = image ] && exit 0\necho '1 failed, 31 passed in 15.0s'\nexit 1\n",
}


class Repo:
    """Repositório temporário com uma cópia do guarda.py."""

    def __init__(self):
        self.raiz = os.path.realpath(tempfile.mkdtemp(prefix="guarda_"))
        self.guarda = os.path.join(self.raiz, ".claude", "hooks", "guarda.py")
        os.makedirs(os.path.dirname(self.guarda))
        shutil.copy(GUARDA, self.guarda)
        for rel in ("backend/app/x.py", "backend/tests/test_x.py", "AUDITORIA/a.md", "README.md"):
            self.escrever(rel, "base\n")
        self.git("init", "-q")
        self.git("config", "user.email", "teste@exemplo.invalid")
        self.git("config", "user.name", "teste")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "base")
        self.bin = os.path.join(self.raiz, ".bin_teste")
        os.makedirs(self.bin)
        os.symlink(GIT, os.path.join(self.bin, "git"))

    def escrever(self, rel, texto):
        p = os.path.join(self.raiz, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(texto)

    def git(self, *args):
        subprocess.run([GIT, *args], cwd=self.raiz, check=True, capture_output=True)

    def docker(self, modo):
        """modo: None (sem docker), 'ok', 'falha' ou 'quebrado' (não executável)."""
        p = os.path.join(self.bin, "docker")
        if os.path.lexists(p):
            os.remove(p)
        if modo is None:
            return
        with open(p, "w") as f:
            f.write(DOCKER_FALSO.get(modo, "#!/bin/sh\nexit 0\n"))
        os.chmod(p, 0o644 if modo == "quebrado" else 0o755)

    def limpar(self):
        shutil.rmtree(self.raiz, ignore_errors=True)

    def rodar(self, modo, entrada, falha=None):
        env = {"PATH": self.bin, "HOME": os.path.expanduser("~")}
        if falha:
            env["TALDO_GUARDA_FALHA_TESTE"] = falha
        r = subprocess.run([sys.executable, self.guarda, modo], input=entrada,
                           capture_output=True, text=True, timeout=60, env=env)
        assert r.returncode == 0, r.stderr
        if not r.stdout.strip():
            return None, "", r.stderr
        hs = json.loads(r.stdout).get("hookSpecificOutput", {})
        return hs.get("permissionDecision"), hs.get("permissionDecisionReason", ""), r.stderr

    def bash(self, cmd, cwd=None, falha=None):
        ev = {"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": cwd or self.raiz}
        return self.rodar("bash", json.dumps(ev), falha)[:2]

    def editar(self, caminho, falha=None):
        if not os.path.isabs(caminho) and not caminho.startswith("~"):
            caminho = os.path.join(self.raiz, caminho)
        ev = {"tool_name": "Edit", "tool_input": {"file_path": os.path.expanduser(caminho)}}
        return self.rodar("arquivo", json.dumps(ev), falha)[:2]


class Base(unittest.TestCase):
    def setUp(self):
        self.r = Repo()
        self.r.docker(None)

    def tearDown(self):
        self.r.limpar()

    def passa(self, *cmds):
        for cmd in cmds:
            self.assertEqual(self.r.bash(cmd), (None, ""), cmd)

    def pede(self, *cmds, contem=None):
        for cmd in cmds:
            d, m = self.r.bash(cmd)
            self.assertEqual(d, "ask", f"{cmd!r} → {d} {m}")
            if contem:
                self.assertIn(contem, m, cmd)


# ---------------------------------------------------------------------------
# comandos comuns e críticos (o que já existia)
# ---------------------------------------------------------------------------

class Comandos(Base):
    def test_comandos_comuns_passam(self):
        self.passa(
            "ls", "git status --short", "git log --oneline -3", "git diff --stat",
            "grep -rn random backend/app", "git checkout -b auditoria/03-baseline",
            "docker run --rm -v \"$PWD\":/repo:ro -w /repo/backend taldo-auditoria:py312 "
            "python -m pytest tests/auditoria -q",
            "python3 -I AUDITORIA/scripts/diagnostico_integridade.py ~/copia.db",
            "echo ok > /tmp/saida.txt",
            "cat > AUDITORIA/notas.md <<'EOF'\ntexto comum de documentação\nEOF",
            "python3 - <<'EOF'\nprint(sum(range(10)))\nEOF",
        )

    def test_pytest_no_banco_padrao_e_negado(self):
        d, _ = self.r.bash("TALDO_DB=backend/data/database/taldo_manager.db python -m pytest tests")
        self.assertEqual(d, "deny")
        self.passa("TALDO_DB=/tmp/x.db python -m pytest tests")

    def test_operacoes_criticas_pedem_aprovacao(self):
        self.pede(
            "git push origin auditoria/01", "git push --force",
            "gh pr create --title x", "gh pr merge 131",
            "git checkout main && git merge auditoria/01",
            "git reset --hard HEAD~1", "git clean -fd", "git branch -D velha",
            "rm -rf backend/tests", "ssh root@vps", "scp a vps:/tmp",
            "bash deploy/atualizar.sh", "docker compose -f deploy/docker-compose.yml up -d",
            "cp copia.db /dados/taldo_manager.db",
            "sqlite3 copia.db 'DELETE FROM partida'",
            "sqlite3 backend/data/database/taldo_manager.db .tables",
            "pip3 install pytest", "git commit --no-verify -m x",
            "claude --dangerously-skip-permissions",
        )

    def test_opcoes_globais_do_git_nao_escondem_o_comando(self):
        self.pede("git -C /outro/repo push", "git -c core.x=y push origin main",
                  "git --no-pager merge main", "git -P push origin main", "git -p merge main",
                  "git --git-dir .git merge x", "git --git-dir=.git push",
                  contem="operação crítica")

    def test_git_c_que_executa_comando_pede_aprovacao(self):
        self.pede("git -c core.pager='sh -c \"rm -r /tmp/x\"' log",
                  "git -c alias.x='!rm -r /tmp' x", "git -c core.sshCommand=evil fetch",
                  "git --config-env=core.pager=X log", "git --exec-path=/tmp/evil status",
                  contem="git -c")

    def test_comandos_de_escrita_fora_da_protecao_passam(self):
        self.passa("cp -r . /tmp/copia", "rm -f /tmp/x", "rm -r AUDITORIA/tmp",
                   "mkdir -p AUDITORIA/novo", "cd backend && python3 -m pytest -q",
                   "mv AUDITORIA/a.md AUDITORIA/b.md", "D=/tmp/x; rm -r $D")

    def test_git_que_descarta_alteracoes_pede_aprovacao(self):
        # 3ª revisão: desfazer as alterações locais (inclusive do guarda.py)
        self.pede("git stash", "git stash -u", "git checkout HEAD~3 -- .", "git checkout HEAD~3 .",
                  "git restore --source=HEAD~3 .", "git restore -s HEAD .", "git checkout -f",
                  "git reset HEAD~1 --hard", "git checkout -- :/", "cd backend && git checkout -- ..",
                  "git restore --staged --worktree .", "git rm -r .", "git rm -rq -- .",
                  "git -P stash", contem="operação crítica")
        self.passa("git stash list", "git checkout -b x", "git restore --staged AUDITORIA/a.md",
                   "git checkout main")

    def test_banco_padrao_com_cd_e_export(self):
        b = "data/database/" + "taldo_manager.db"
        for cmd in [f"cd backend && TALDO_DB={b} pytest",
                    f"export TALDO_DB=backend/{b}; pytest",
                    f"cd backend; export TALDO_DB={b} && python -m pytest tests"]:
            self.assertEqual(self.r.bash(cmd)[0], "deny", cmd)
        self.pede(f"cd backend && rm {b}", "cd backend/data && cp /tmp/x database/taldo_manager.db",
                  contem="banco padrão")
        self.passa("cd backend && TALDO_DB=/tmp/x.db pytest", "export TALDO_DB=/tmp/x.db; pytest")

    def test_sqlite_so_leitura_passa(self):
        self.passa("sqlite3 /tmp/copia.db 'SELECT COUNT(*) FROM partida'")


# ---------------------------------------------------------------------------
# achado 3: heredoc e conteúdo multilinha
# ---------------------------------------------------------------------------

class Heredoc(Base):
    def test_comando_perigoso_em_heredoc_e_pego(self):
        self.pede("sqlite3 copia.db <<'SQL'\nDELETE FROM partida;\nSQL", contem="SQLite")
        self.pede("bash <<'EOF'\nrm -rf backend\ngit push\nEOF", contem="push")
        self.pede("sh <<EOF\nssh root@vps\nEOF", contem="remota")
        self.pede("python3 - <<'EOF'\nimport os\nos.system('git push origin main')\nEOF",
                  contem="push")

    def test_mensagem_de_commit_em_heredoc_nao_dispara_falso_alarme(self):
        self.passa("git commit -q -F - <<'EOF'\nnão faz git push nem rm -rf\nEOF",
                   'git commit -m "documenta o git push e o ssh"')

    def test_heredoc_de_commit_seguido_de_comando_perigoso_e_pego(self):
        self.pede("git commit -q -F - <<'EOF'\nmensagem\nEOF\ngit push", contem="push")

    def test_opcao_terminada_em_m_fora_do_commit_nao_esconde_codigo(self):
        # 3ª revisão: `bash -cm '...'` não é mensagem de commit
        self.pede("bash -cm 'rm -r .claude/hooks'", contem="proteção")
        self.pede("sh -cm \"git push --force\"", contem="push")

    def test_heredoc_com_delimitador_diferente_ou_sem_fim(self):
        self.pede("git commit -F - <<END-MSG\nmsg\nEND-MSG\nrm -r .claude/hooks", contem="proteção")
        self.pede("git commit -F - <<EOF\nmensagem sem fim\ngit push", contem="push")

    def test_push_encadeado_depois_do_commit_e_pego(self):
        self.pede('git commit -m "x" && git push', contem="push")

    def test_mensagem_com_substituicao_de_comando_nao_e_ignorada(self):
        # "$(...)" dentro de aspas duplas EXECUTA: não é só texto
        self.pede('git commit -m "$(git push origin main)"', contem="push")
        self.pede('git commit -m "`rm -rf backend`"', contem="rm -rf")


# ---------------------------------------------------------------------------
# achado 4: as próprias proteções
# ---------------------------------------------------------------------------

class Protecoes(Base):
    def test_editar_arquivos_de_protecao_pede_aprovacao(self):
        for c in [".claude/hooks/guarda.py", ".claude/hooks/test_guarda.py",
                  ".claude/hooks/README.md", ".claude/settings.json",
                  ".claude/settings.local.json", ".claude/auditoria/REGRAS.md",
                  ".claude/agents/qa-engineer.md", "~/.claude/settings.json"]:
            d, m = self.r.editar(c)
            self.assertEqual(d, "ask", c)
            self.assertIn("proteção", m, c)

    def test_editar_skills_auditoria_e_testes_passa(self):
        for c in [".claude/skills/x/SKILL.md", "AUDITORIA/03_X.md", "AUDITORIA/scripts/novo.py",
                  "backend/tests/auditoria/test_auditoria_x.py", "/tmp/qualquer.txt"]:
            self.assertEqual(self.r.editar(c), (None, ""), c)

    def test_comando_que_altera_protecao_pede_aprovacao(self):
        self.pede(
            "sed -i '' 's/ask/allow/' .claude/hooks/guarda.py",
            "sed -i.bak 1d .claude/hooks/guarda.py",
            "echo 'x' > .claude/hooks/guarda.py",
            "echo 'x' >> .claude/hooks/guarda.py",
            "cat /tmp/novo.py | tee .claude/hooks/guarda.py",
            "cp /tmp/g.py .claude/hooks/guarda.py",
            "rm .claude/hooks/guarda.py",
            "mv .claude /tmp/fora",
            "git checkout -- .claude/hooks/guarda.py",
            "git restore .claude/settings.json",
            "python3 -c \"open('.claude/hooks/guarda.py','w')\"",
            "cd .claude/hooks && sed -i '' 1d guarda.py",
            "echo '{\"disableAllHooks\": true}' > .claude/settings.local.json",
            "echo '{}' >> ~/.claude/settings.json",
            "perl -pi -e 's/x/y/' .claude/agents/qa-engineer.md",
            "find .claude -name '*.py' -delete",
            "python3 - <<'EOF'\nopen('.claude/hooks/guarda.py', 'w').write('')\nEOF",
            "chmod -x .claude/hooks/guarda.py",
            "ln -sf /dev/null .claude/hooks/guarda.py",
            # 2ª revisão: caminhos indiretos
            "cd .claude && rm -r hooks",
            "D=.claude; rm -r $D/hooks",
            "rm -r .claude/./hooks", "rm -r .claude//hooks", "rm -r x/../.claude/hooks",
            "rm -r .claude", "rm -r .",
            "sed -n 'w .claude/settings.json' /tmp/x",
            "sed --expression='w .claude/settings.json' /tmp/x",
            "sed -n 's/a/b/e' .claude/hooks/README.md",
            "git diff --output=.claude/settings.json",
            "tree -o .claude/settings.json",
            "find .claude -fls .claude/x",
            "rg --pre 'rm -r' x .claude/hooks",
            "echo \"$(rm -r .claude/hooks $(true))\"",
            "echo \"`rm -r .claude/hooks`\"",
            # 3ª revisão: pipe para xargs, opções do cd, glob
            "find .claude/hooks -type f | xargs rm",
            "find .claude/hooks -type f -print0 | xargs -0 rm",
            "grep -l x .claude/hooks/* | xargs rm",
            "cd -- .claude && rm -r hooks", "cd -P .claude && rm -r hooks",
            "cd -L .claude && rm -r hooks", "rm -r .[a-z]*",
            contem="proteção",
        )

    def test_comando_dentro_da_pasta_de_protecao(self):
        pasta = os.path.join(self.r.raiz, ".claude")
        for cmd in ["rm -r hooks", "echo x > hooks/guarda.py", "mv hooks /tmp/h"]:
            d, m = self.r.bash(cmd, cwd=pasta)
            self.assertEqual(d, "ask", cmd)
            self.assertIn("proteção", m, cmd)
        self.assertEqual(self.r.bash("ls hooks", cwd=pasta), (None, ""))

    def test_ler_e_rodar_as_protecoes_passa(self):
        self.passa(
            "cat .claude/hooks/guarda.py",
            "sed -n 1,40p .claude/hooks/guarda.py",
            "grep -n hooks .claude/settings.json",
            "ls .claude .claude/hooks",
            "git diff .claude/",
            "git log --oneline -- .claude/hooks/guarda.py",
            "git add .claude/hooks/guarda.py",
            "python3 .claude/hooks/test_guarda.py -v",
            "python3 -m unittest .claude/hooks/test_guarda.py",
            "printf '{}' | python3 .claude/hooks/guarda.py bash",
            "diff .claude/hooks/guarda.py /tmp/outro.py",
            "ls .claude/skills",
        )


# ---------------------------------------------------------------------------
# achado 1: arquivos que vão para o commit
# ---------------------------------------------------------------------------

class Commit(Base):
    def test_add_e_commit_no_mesmo_comando_ve_a_producao(self):
        self.r.escrever("backend/app/x.py", "mudou\n")
        d, m = self.r.bash("git add backend/app/x.py && git commit -m x")
        self.assertEqual(d, "ask")
        self.assertIn("backend/app/x.py", m)

    def test_add_e_commit_com_testes_falhando_e_negado(self):
        self.r.docker("falha")
        self.r.escrever("backend/app/x.py", "mudou\n")
        d, m = self.r.bash("git add backend/app/x.py && git commit -m x")
        self.assertEqual(d, "deny")
        self.assertIn("1 failed", m)

    def test_add_e_commit_com_testes_passando_ainda_pede_aprovacao_da_producao(self):
        self.r.docker("ok")
        self.r.escrever("backend/app/x.py", "mudou\n")
        d, m = self.r.bash("git add backend/app/x.py && git commit -m x")
        self.assertEqual(d, "ask")
        self.assertIn("32 passed", m)

    def test_formas_de_incluir_arquivos(self):
        self.r.escrever("backend/app/x.py", "mudou\n")
        for cmd, cwd in [
            ("git add -A && git commit -m x", None),
            ("git add . && git commit -m x", None),
            ("git add . && git commit -m x", os.path.join(self.r.raiz, "backend")),
            ("git add app && git commit -m x", os.path.join(self.r.raiz, "backend")),
            ("git add 'backend/app/*.py' && git commit -m x", None),
            ("git commit -am x", None),
            ("git commit -a -m x", None),
            ("git commit backend/app/x.py -m x", None),
            ("git -C backend add app/x.py && git commit -m x", None),
        ]:
            d, m = self.r.bash(cmd, cwd=cwd)
            self.assertEqual(d, "ask", f"{cmd} (cwd={cwd}) → {d} {m}")
            self.assertIn("backend/app/x.py", m, cmd)

    def test_opcao_curta_do_git_nao_esconde_o_commit(self):
        self.r.escrever("backend/app/x.py", "mudou\n")
        for cmd in ["git -P commit -m x backend/app/x.py",
                    "git --git-dir .git commit -am x"]:
            d, m = self.r.bash(cmd)
            self.assertEqual(d, "ask", cmd)
            self.assertIn("backend/app/x.py", m, cmd)

    def test_pathspec_especial_do_git(self):
        # 3ª revisão: `:/`, `:(top)` e --pathspec-from-file
        self.r.escrever("backend/app/x.py", "mudou\n")
        for cmd in ["git add :/ && git commit -m x", "git add ':(top)backend' && git commit -m x",
                    "git commit -m x --pathspec-from-file=lista.txt"]:
            d, m = self.r.bash(cmd)
            self.assertEqual(d, "ask", cmd)
            self.assertIn("backend/app/x.py", m, cmd)

    def test_arquivo_ja_preparado_continua_visto(self):
        self.r.escrever("backend/app/x.py", "mudou\n")
        self.r.git("add", "backend/app/x.py")
        d, m = self.r.bash("git commit -m x")
        self.assertEqual(d, "ask")
        self.assertIn("backend/app/x.py", m)

    def test_commit_so_de_documentos_passa(self):
        self.r.docker("falha")   # nem chega a rodar os testes
        self.r.escrever("AUDITORIA/a.md", "mudou\n")
        self.passa("git add AUDITORIA/a.md && git commit -m docs")

    def test_commit_de_testes_roda_os_testes(self):
        self.r.escrever("backend/tests/test_x.py", "mudou\n")
        self.r.docker("falha")
        self.assertEqual(self.r.bash("git add backend/tests && git commit -m t")[0], "deny")
        self.r.docker("ok")
        self.passa("git add backend/tests && git commit -m t")


# ---------------------------------------------------------------------------
# achado 2: falha interna nunca libera operação sensível em silêncio
# ---------------------------------------------------------------------------

class FalhaInterna(Base):
    def test_sem_docker_o_commit_de_backend_pede_aprovacao(self):
        self.r.escrever("backend/tests/test_x.py", "mudou\n")
        d, m = self.r.bash("git add backend/tests && git commit -m t")
        self.assertEqual(d, "ask")
        self.assertIn("não deu para rodar os testes", m)

    def test_docker_quebrado_nao_derruba_o_hook(self):
        self.r.docker("quebrado")
        self.r.escrever("backend/app/x.py", "mudou\n")
        d, m = self.r.bash("git add backend/app/x.py && git commit -m x && git push")
        self.assertEqual(d, "ask")
        self.assertIn("push", m)
        self.assertIn("não deu para rodar os testes", m)

    def test_erro_na_verificacao_do_commit_preserva_os_outros_motivos(self):
        d, m = self.r.bash("git add backend/app/x.py && git commit -m x && git push",
                           falha="commit")
        self.assertEqual(d, "ask")
        self.assertIn("push", m)
        self.assertIn("não deu para verificar o commit", m)

    def test_erro_na_analise_pede_aprovacao_do_que_e_sensivel(self):
        for cmd in ["git push", "rm -rf x", "sqlite3 a.db", "sed -i '' 1d .claude/hooks/guarda.py",
                    "python3 -c 'x'", "echo x > arquivo"]:
            d, m = self.r.bash(cmd, falha="analise")
            self.assertEqual(d, "ask", cmd)
            self.assertIn("erro interno", m, cmd)

    def test_erro_na_analise_deixa_passar_o_comum(self):
        for cmd in ["ls", "pwd", "cat README.md", "grep -rn x AUDITORIA"]:
            self.assertEqual(self.r.bash(cmd, falha="analise"), (None, ""), cmd)

    def test_erro_na_analise_de_arquivo(self):
        self.assertEqual(self.r.editar("backend/app/x.py", falha="analise")[0], "ask")
        self.assertEqual(self.r.editar(".claude/hooks/guarda.py", falha="analise")[0], "ask")
        self.assertEqual(self.r.editar("/tmp/qualquer.txt", falha="analise"), (None, ""))

    def test_entrada_invalida(self):
        self.assertEqual(self.r.rodar("bash", "não é json")[:2], (None, ""))
        self.assertEqual(self.r.rodar("bash", "{git push origin main")[0], "ask")
        self.assertEqual(self.r.rodar("bash", "[1, 2]")[0], "ask")   # JSON que não é objeto

    def test_fim_nunca_trava(self):
        self.assertEqual(self.r.rodar("fim", "{}")[:2], (None, ""))
        self.assertEqual(self.r.rodar("fim", "lixo")[:2], (None, ""))


# ---------------------------------------------------------------------------
# arquivos de produção (o que já existia)
# ---------------------------------------------------------------------------

class Producao(Base):
    def test_producao_pede_aprovacao(self):
        for c in ["backend/app/domain/partida.py", "backend/app/db/schema.sql",
                  "frontend/js/app.js", "deploy/backup.sh", "Dockerfile",
                  "backend/requirements.txt", "backend/scripts/simular.py"]:
            self.assertEqual(self.r.editar(c)[0], "ask", c)

    def test_fim_avisa_producao_alterada(self):
        self.r.escrever("backend/app/x.py", "mudou\n")
        ev = json.dumps({"stop_hook_active": False})
        env = {"PATH": self.r.bin, "HOME": os.path.expanduser("~")}
        r = subprocess.run([sys.executable, self.r.guarda, "fim"], input=ev,
                           capture_output=True, text=True, timeout=60, env=env)
        self.assertIn("backend/app/x.py", r.stdout)


class CopiaFiel(unittest.TestCase):
    def test_o_teste_usa_o_guarda_do_projeto(self):
        r = Repo()
        try:
            with open(GUARDA, "rb") as a, open(r.guarda, "rb") as b:
                self.assertEqual(a.read(), b.read())
            self.assertFalse(os.stat(r.guarda).st_mode & stat.S_IWOTH)
        finally:
            r.limpar()


if __name__ == "__main__":
    unittest.main()
