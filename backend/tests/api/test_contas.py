"""Contas (v2.1): login por cookie e cada técnico só nos próprios saves."""

import pytest
from fastapi.testclient import TestClient

from app.api.contas import exigir_dono
from app.db.conexao import conectar
from app.main import app
from app.repositories import usuario_repository as usuario_repo
from app.services import conta_service


@pytest.fixture(autouse=True)
def com_login():
    """Liga de volta a checagem que o conftest desliga nos outros testes."""
    app.dependency_overrides.pop(exigir_dono, None)
    conta_service._tentativas.clear()
    yield
    conta_service._tentativas.clear()


def _tecnico(nome, senha="segredo1"):
    """Um cliente (navegador) com a própria conta, já logado."""
    c = TestClient(app)
    resp = c.post("/conta/registrar", json={"nome": nome, "senha": senha})
    assert resp.status_code == 201, resp.text
    return c


def _novo_jogo(c, seed=8):
    clube = c.get("/clubes").json()[0]["nome"]
    resp = c.post("/simulacoes", json={"seed": seed, "clube": clube,
                                       "modo": "rodada_a_rodada"})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_sem_login_o_jogo_pede_conta_mas_o_catalogo_e_publico():
    c = TestClient(app)
    assert c.get("/simulacoes").status_code == 401
    assert c.post("/simulacoes", json={}).status_code == 401
    assert c.get("/simulacoes/1").status_code == 401
    assert c.get("/conta/eu").json() is None
    assert c.get("/health").status_code == 200
    assert c.get("/clubes").status_code == 200


def test_registrar_ja_entra_e_sair_encerra_a_sessao():
    c = _tecnico("isaque")
    assert c.get("/conta/eu").json()["nome"] == "isaque"
    assert c.get("/simulacoes").json() == []

    assert c.post("/conta/sair").status_code == 204
    assert c.get("/conta/eu").json() is None


def test_entrar_com_a_senha_certa():
    _tecnico("isaque", "segredo1")
    c = TestClient(app)
    assert c.post("/conta/entrar", json={"nome": "isaque", "senha": "errada"}).status_code == 400
    # o nome não diferencia maiúsculas
    resp = c.post("/conta/entrar", json={"nome": "Isaque", "senha": "segredo1"})
    assert resp.status_code == 200
    assert c.get("/conta/eu").json()["nome"] == "isaque"


def test_cadastro_recusa_nome_repetido_curto_e_senha_fraca():
    _tecnico("isaque")
    c = TestClient(app)
    repetido = c.post("/conta/registrar", json={"nome": "ISAQUE", "senha": "segredo1"})
    assert repetido.status_code == 400
    assert "em uso" in repetido.json()["detail"]
    assert c.post("/conta/registrar", json={"nome": "ab", "senha": "segredo1"}).status_code == 400
    assert c.post("/conta/registrar", json={"nome": "a b c", "senha": "segredo1"}).status_code == 400
    assert c.post("/conta/registrar", json={"nome": "pedro", "senha": "123"}).status_code == 400


def test_senha_e_token_nao_ficam_no_banco():
    c = _tecnico("isaque", "segredo1")
    token = c.cookies.get("taldo_sessao")
    conn = conectar()
    try:
        u = usuario_repo.buscar_por_nome(conn, "isaque")
        assert "segredo1" not in u["senha_hash"]
        sessoes = conn.execute("SELECT token_hash FROM sessao").fetchall()
        assert token not in {s["token_hash"] for s in sessoes}
    finally:
        conn.close()


def test_muitas_senhas_erradas_travam_o_login():
    _tecnico("isaque")
    c = TestClient(app)
    for _ in range(10):
        c.post("/conta/entrar", json={"nome": "isaque", "senha": "errada"})
    travado = c.post("/conta/entrar", json={"nome": "isaque", "senha": "segredo1"})
    assert travado.status_code == 429


def test_cada_tecnico_so_ve_e_mexe_nos_proprios_saves():
    ana = _tecnico("ana")
    beto = _tecnico("beto")
    sid = _novo_jogo(ana)

    assert [s["id"] for s in ana.get("/simulacoes").json()] == [sid]
    assert beto.get("/simulacoes").json() == []

    # o save da Ana não existe para o Beto: nem ler, nem jogar, nem apagar
    assert beto.get(f"/simulacoes/{sid}").status_code == 404
    assert beto.get(f"/simulacoes/{sid}/rodadas/proxima").status_code == 404
    assert beto.get(f"/simulacoes/{sid}/mercado").status_code == 404
    assert beto.post(f"/simulacoes/{sid}/rodadas", json={}).status_code == 404
    assert beto.post(f"/simulacoes/{sid}/calendario/dia").status_code == 404
    assert beto.delete(f"/simulacoes/{sid}").status_code == 404

    # e continua inteiro para a dona
    assert ana.get(f"/simulacoes/{sid}").status_code == 200
    assert ana.get(f"/simulacoes/{sid}/rodadas/proxima").status_code == 200


def test_ids_de_outro_save_nao_atravessam_pelo_proprio_save():
    """Mesmo dentro do próprio save, o jogador/partida de outro save não
    aparece (os serviços conferem o simulacao_id dos ids aninhados)."""
    ana = _tecnico("ana")
    beto = _tecnico("beto")
    sid_ana = _novo_jogo(ana, seed=8)
    sid_beto = _novo_jogo(beto, seed=9)

    conn = conectar()
    try:
        jogador_ana = conn.execute(
            "SELECT id FROM jogador WHERE simulacao_id = ? LIMIT 1", (sid_ana,)
        ).fetchone()["id"]
        clube_ana = conn.execute(
            "SELECT id FROM clube WHERE simulacao_id = ? LIMIT 1", (sid_ana,)
        ).fetchone()["id"]
    finally:
        conn.close()

    assert beto.get(f"/simulacoes/{sid_beto}/jogadores/{jogador_ana}").status_code == 404
    assert beto.get(f"/simulacoes/{sid_beto}/clubes/{clube_ana}").status_code == 404
    assert beto.post(
        f"/simulacoes/{sid_beto}/jogadores/{jogador_ana}/dispensa"
    ).status_code == 404


def test_carreira_de_outro_tecnico_nao_abre(cargo_garantido):
    ana = _tecnico("ana")
    beto = _tecnico("beto")
    clube = ana.get("/clubes").json()[0]["nome"]
    sid = ana.post("/simulacoes", json={"seed": 3, "clube": clube}).json()["id"]

    criada = ana.post(f"/simulacoes/{sid}/proxima-temporada").json()
    # a temporada nova também é da Ana
    assert ana.get(f"/simulacoes/{criada['simulacao_id']}").status_code == 200
    assert beto.get(f"/simulacoes/{criada['simulacao_id']}").status_code == 404
    assert ana.get(f"/carreiras/{criada['carreira_id']}").status_code == 200
    assert beto.get(f"/carreiras/{criada['carreira_id']}").status_code == 404


def test_saves_sem_dono_ficam_fechados_ate_alguem_receber():
    """Os saves de antes das contas não aparecem para ninguém; o script
    `dar_saves` passa todos para uma conta."""
    from app.services import simulacao_service
    sid = simulacao_service.salvar_temporada(seed=1)

    ana = _tecnico("ana")
    assert ana.get("/simulacoes").json() == []
    assert ana.get(f"/simulacoes/{sid}").status_code == 404

    conn = conectar()
    try:
        u = usuario_repo.buscar_por_nome(conn, "ana")
        assert usuario_repo.dar_saves_sem_dono(conn, u["id"]) == 1
        conn.commit()
    finally:
        conn.close()
    assert ana.get(f"/simulacoes/{sid}").status_code == 200


def test_limite_de_jogos_por_conta(monkeypatch):
    monkeypatch.setattr(conta_service, "LIMITE_JOGOS", 1)
    ana = _tecnico("ana")
    _novo_jogo(ana)
    clube = ana.get("/clubes").json()[0]["nome"]
    resp = ana.post("/simulacoes", json={"seed": 2, "clube": clube,
                                         "modo": "rodada_a_rodada"})
    assert resp.status_code == 409
    assert "Limite" in resp.json()["detail"]
