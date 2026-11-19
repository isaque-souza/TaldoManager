"""Cada save joga para sempre no mundo em que nasceu (v2.7): migração dos
saves antigos, jogo novo, virada e mundo que sumiu."""

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.db.conexao import conectar, init_db
from app.main import app, conferir_mundos
from app.services import carreira_service, simulacao_service, temporada_service
from scripts import data_loader, mundos

client = TestClient(app)
DUAS = ("taldo", "premier")


@pytest.fixture(autouse=True)
def _sem_demissao(cargo_garantido):
    """Não é sobre a diretoria."""


def _sim(sid):
    conn = conectar()
    try:
        return conn.execute("SELECT * FROM simulacao WHERE id = ?", (sid,)).fetchone()
    finally:
        conn.close()


def _clubes_do_save(sid):
    sim = _sim(sid)
    return {c.nome for c in data_loader.carregar_campeonato_do_save(sim).clubes}


# ---------------------------------------------------------------------------
# saves de antes
# ---------------------------------------------------------------------------

def test_migracao_poe_os_saves_antigos_no_v1(tmp_path, monkeypatch):
    caminho = tmp_path / "antigo.db"
    monkeypatch.setenv("TALDO_DB", str(caminho))
    velho = sqlite3.connect(caminho)
    velho.execute(
        "CREATE TABLE simulacao (id INTEGER PRIMARY KEY, seed INTEGER, "
        "criada_em TEXT NOT NULL, campeao TEXT NOT NULL, rodadas INTEGER NOT NULL)"
    )
    velho.execute("INSERT INTO simulacao (seed, criada_em, campeao, rodadas) "
                  "VALUES (1, '2026-01-01', 'FC Taldo', 38)")
    velho.commit()
    velho.close()

    init_db()
    init_db()    # idempotente

    sim = _sim(1)
    assert sim["mundo"] == "v1"
    assert data_loader.mundo_do_save(sim) == "v1"


def test_jogo_novo_grava_o_mundo_padrao():
    sid = temporada_service.iniciar(seed=1, clube_usuario="Liverpool", ligas=DUAS)
    assert _sim(sid)["mundo"] == mundos.MUNDO_PADRAO == "v1"
    sid = simulacao_service.salvar_temporada(seed=2, clube_usuario="Liverpool", ligas=DUAS)
    assert _sim(sid)["mundo"] == "v1"


# ---------------------------------------------------------------------------
# dois mundos convivendo
# ---------------------------------------------------------------------------

def test_save_do_v1_nao_ve_o_mundo_novo(mundos_temp, liga_alterada):
    """O marco da v2.7: criar um mundo novo, com clube renomeado, sem mudar
    nada num save do v1 em andamento."""
    antigo = temporada_service.iniciar(seed=1, clube_usuario="Liverpool", ligas=DUAS)
    temporada_service.avancar(antigo)

    obra = liga_alterada("premier", "Chelsea", "Chelsea Novo")
    mundos.criar_mundo("teste", "Teste", base="v1", trocar={"premier": obra})
    novo = temporada_service.iniciar(seed=1, clube_usuario="Liverpool", ligas=DUAS,
                                     mundo="teste")
    assert _sim(novo)["mundo"] == "teste"

    # o save do v1 segue com o Chelsea de sempre e continua andando
    temporada_service.avancar(antigo)
    assert "Chelsea" in _clubes_do_save(antigo)
    assert "Chelsea Novo" not in _clubes_do_save(antigo)
    assert _sim(antigo)["rodada_atual"] == 3

    # o do mundo novo joga com o clube renomeado
    temporada_service.avancar(novo)
    assert "Chelsea Novo" in _clubes_do_save(novo)
    snapshot = json.loads(_sim(novo)["estado_json"])
    assert "Chelsea Novo" in snapshot["clubes"] and "Chelsea" not in snapshot["clubes"]


def test_mesmo_save_mesma_seed_mesmos_jogos_com_outro_mundo_instalado(mundos_temp, liga_alterada):
    """Instalar um mundo novo não muda um jogo do v1: mesma seed, mesmos
    placares de antes e depois."""
    def placares(sid):
        conn = conectar()
        try:
            return [tuple(r) for r in conn.execute(
                "SELECT rodada, mandante_id, visitante_id, gols_mandante, gols_visitante "
                "FROM partida WHERE simulacao_id = ? ORDER BY id", (sid,))]
        finally:
            conn.close()

    antes = temporada_service.iniciar(seed=7, clube_usuario="Arsenal", ligas=DUAS)
    temporada_service.avancar(antes)
    obra = liga_alterada("premier", "Chelsea", "Chelsea Novo")
    mundos.criar_mundo("teste", "Teste", base="v1", trocar={"premier": obra})
    depois = temporada_service.iniciar(seed=7, clube_usuario="Arsenal", ligas=DUAS)
    temporada_service.avancar(depois)

    so_gols = lambda ps: [(r, gm, gv) for r, _, _, gm, gv in ps]   # noqa: E731
    assert so_gols(placares(antes)) == so_gols(placares(depois))
    assert len(placares(antes)) == 20


def test_virada_fica_no_mundo_e_so_ganha_as_ligas_dele(mundos_temp):
    tirar = ("championship", "laliga", "segunda", "brasileirao", "brasileirao_b")
    mundos.criar_mundo("mini", "Mini", base="v1", tirar=tirar)
    sid = simulacao_service.salvar_temporada(seed=4, clube_usuario="Liverpool",
                                             ligas=DUAS, mundo="mini")
    nova = carreira_service.proxima_temporada(sid)["simulacao_id"]

    sim = _sim(nova)
    assert sim["mundo"] == "mini"
    # no v1 ganharia as 8 ligas; no mini, só a Série B que ele tem
    assert json.loads(sim["ligas"]) == ["taldo", "premier", "taldo_b"]
    temporada_service.avancar(nova)
    assert _sim(nova)["rodada_atual"] == 2


# ---------------------------------------------------------------------------
# mundo que sumiu ou foi alterado
# ---------------------------------------------------------------------------

def test_save_com_mundo_ausente_da_erro_claro():
    sid = temporada_service.iniciar(seed=1, clube_usuario="Liverpool", ligas=DUAS)
    conn = conectar()
    with conn:
        conn.execute("UPDATE simulacao SET mundo = 'v99' WHERE id = ?", (sid,))
    conn.close()

    r = client.get(f"/simulacoes/{sid}/rodadas/proxima")
    assert r.status_code == 503
    assert "v99" in r.json()["detail"]
    # a lista de saves continua abrindo
    assert client.get("/simulacoes").status_code == 200
    # e a subida do app avisa
    assert set(conferir_mundos()) == {"v99"}


def test_save_com_mundo_alterado_nao_carrega_outra_coisa(mundos_temp):
    mundos.criar_mundo("teste", "Teste", base="v1")
    sid = temporada_service.iniciar(seed=1, clube_usuario="Liverpool", ligas=DUAS,
                                    mundo="teste")
    clubes = mundos_temp / "teste" / "ligas" / "premier" / "clubes.json"
    clubes.write_text(clubes.read_text(encoding="utf-8") + " ", encoding="utf-8")
    mundos.limpar_cache()

    r = client.post(f"/simulacoes/{sid}/rodadas", json={})
    assert r.status_code == 503
    assert "alterado" in r.json()["detail"]
    assert _sim(sid)["rodada_atual"] == 1     # nada andou


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

def test_api_lista_os_mundos():
    r = client.get("/mundos")
    assert r.status_code == 200
    v1 = next(m for m in r.json() if m["id"] == "v1")
    assert v1["padrao"] is True and v1["base"] is None
    assert [l["id"] for l in v1["ligas"]] == list(data_loader.TODAS_AS_LIGAS)
    assert v1["totais"]["clubes"] == 160


def test_api_jogo_novo_no_mundo_pedido(mundos_temp, liga_alterada):
    obra = liga_alterada("premier", "Chelsea", "Chelsea Novo")
    mundos.criar_mundo("teste", "Teste", base="v1", trocar={"premier": obra})

    r = client.post("/simulacoes", json={
        "clube": "Chelsea Novo", "modo": "rodada_a_rodada", "mundo": "teste",
        "ligas": ["taldo", "premier"],
    })
    assert r.status_code == 201, r.text
    assert _sim(r.json()["id"])["mundo"] == "teste"

    nomes = {c["nome"] for c in client.get("/clubes", params={"mundo": "teste"}).json()}
    assert "Chelsea Novo" in nomes
    assert client.get("/clubes/Chelsea Novo", params={"mundo": "teste"}).status_code == 200
    # o padrão segue sendo o v1
    assert "Chelsea" in {c["nome"] for c in client.get("/clubes").json()}


def test_api_mundo_inexistente():
    r = client.post("/simulacoes", json={"clube": "Liverpool", "mundo": "v99"})
    assert r.status_code == 400 and "v99" in r.json()["detail"]
    assert client.get("/clubes", params={"mundo": "v99"}).status_code == 400
