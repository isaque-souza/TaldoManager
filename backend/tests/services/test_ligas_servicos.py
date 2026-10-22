"""Saves com as duas ligas (v1.6): banco, serviços e carreira."""

import collections
import json

import pytest

from app.db.conexao import conectar
from app.services import (
    carreira_service, mercado_service, simulacao_service, temporada_service,
)
from scripts.data_loader import TODAS_AS_LIGAS

DUAS = TODAS_AS_LIGAS


@pytest.fixture(autouse=True)
def _sem_demissao(cargo_garantido):
    """Não é sobre a diretoria."""


def _linhas(sql, *args):
    conn = conectar()
    try:
        return conn.execute(sql, args).fetchall()
    finally:
        conn.close()


def test_temporada_nova_com_as_duas_ligas():
    sid = temporada_service.iniciar(seed=3, clube_usuario="Arsenal", ligas=DUAS)

    sim = _linhas("SELECT ligas, meta_posicao, ranking_forca FROM simulacao WHERE id = ?", sid)[0]
    assert json.loads(sim["ligas"]) == ["taldo", "premier"]
    # o ranking de força é o da Premier (20 clubes), não o das 40
    assert 1 <= sim["ranking_forca"] <= 3 and sim["meta_posicao"] <= 4
    ligas = collections.Counter(
        r["liga"] for r in _linhas("SELECT liga FROM clube WHERE simulacao_id = ?", sid)
    )
    assert ligas == {"taldo": 20, "premier": 20}

    temporada_service.avancar(sid)
    assert len(_linhas("SELECT id FROM partida WHERE simulacao_id = ?", sid)) == 20


def test_mercado_cruza_as_ligas():
    sid = temporada_service.iniciar(seed=3, clube_usuario="Arsenal", ligas=DUAS)
    m = mercado_service.ver_mercado(sid)
    clubes = {f["clube"] for f in m["disponiveis"]}
    assert "Real Taldo" in clubes and "Liverpool" in clubes
    assert len(m["livres"]) == 100


def test_temporada_inteira_posicao_e_campeao_por_liga():
    sid = simulacao_service.salvar_temporada(seed=4, clube_usuario="Liverpool", ligas=DUAS)

    clubes = _linhas("SELECT nome, liga, posicao_final FROM clube WHERE simulacao_id = ?", sid)
    for liga in DUAS:
        assert sorted(c["posicao_final"] for c in clubes if c["liga"] == liga) == list(range(1, 21))
    campeao = _linhas("SELECT campeao FROM simulacao WHERE id = ?", sid)[0]["campeao"]
    premier = {c["nome"] for c in clubes if c["liga"] == "premier"}
    assert campeao in premier          # o campeão do save é o da liga do técnico


def test_carreira_segue_com_as_duas_ligas():
    sid = simulacao_service.salvar_temporada(seed=4, clube_usuario="Liverpool", ligas=DUAS)
    nova = carreira_service.proxima_temporada(sid)["simulacao_id"]

    sim = _linhas("SELECT ligas FROM simulacao WHERE id = ?", nova)[0]
    assert json.loads(sim["ligas"]) == ["taldo", "premier"]
    m = mercado_service.ver_mercado(nova)
    assert len(m["livres"]) >= 100     # a lista cresce com as ligas
    porliga = collections.Counter(
        r["liga"] for r in _linhas("SELECT liga FROM clube WHERE simulacao_id = ?", nova)
    )
    assert porliga == {"taldo": 20, "premier": 20}


def test_listar_clubes_das_duas_ligas_com_ranking_por_liga():
    clubes = simulacao_service.listar_clubes(DUAS)
    assert len(clubes) == 40
    for liga in DUAS:
        ranking = sorted(c["ranking_forca"] for c in clubes if c["liga"] == liga)
        assert ranking == list(range(1, 21))


def test_save_antigo_continua_so_com_a_taldo():
    sid = temporada_service.iniciar(seed=3, clube_usuario="Real Taldo")
    assert _linhas("SELECT ligas FROM simulacao WHERE id = ?", sid)[0]["ligas"] is None
    assert len(mercado_service.ver_mercado(sid)["livres"]) == 50


def test_outros_jogos_ao_vivo_sao_da_liga_do_tecnico():
    sid = temporada_service.iniciar(seed=3, clube_usuario="Arsenal", ligas=DUAS)
    temporada_service.avancar(sid)

    jogos = simulacao_service.ao_vivo(sid, 1)["partidas"]
    premier = {c["nome"] for c in simulacao_service.listar_clubes(DUAS) if c["liga"] == "premier"}
    assert len(jogos) == 10
    assert all(j["mandante"] in premier for j in jogos)


# --- copa entre as ligas (v1.6) ---------------------------------------------

def _copa_do_estado(sid):
    estado = _linhas("SELECT estado_json FROM simulacao WHERE id = ?", sid)[0]["estado_json"]
    return json.loads(estado)["copa"]


def test_jogo_novo_ja_tem_a_copa_com_os_classificados_de_inicio():
    sid = temporada_service.iniciar(seed=3, clube_usuario="Arsenal", ligas=DUAS)
    copa = _copa_do_estado(sid)
    # a Premier pela tabela real de 23/24
    assert copa["classificados"]["premier"][:3] == ["Manchester City", "Arsenal", "Liverpool"]
    assert len(copa["classificados"]["taldo"]) == 8
    assert all(j["vencedor"] is None for j in copa["fases"]["oitavas"])


def test_so_a_taldo_nao_tem_copa():
    sid = temporada_service.iniciar(seed=3, clube_usuario="Real Taldo")
    assert _copa_do_estado(sid) is None


def test_a_copa_anda_no_save_e_fica_guardada_no_fim():
    sid = temporada_service.iniciar(seed=6, clube_usuario="Arsenal", ligas=DUAS)
    for _ in range(8):
        temporada_service.avancar(sid)
    # o Arsenal está nas oitavas: a fase espera o jogo dele, na quarta
    assert all(j["vencedor"] is None for j in _copa_do_estado(sid)["fases"]["oitavas"])
    res = temporada_service.avancar(sid)
    assert res["copa_jogada"] and res["rodada_jogada"] == 8 and res["rodada_atual"] == 9
    oitavas = _copa_do_estado(sid)["fases"]["oitavas"]
    assert all(j["vencedor"] for j in oitavas)          # jogou depois da 8ª
    assert all(j["vencedor"] is None for j in _copa_do_estado(sid)["fases"]["quartas"])

    while temporada_service.avancar(sid)["concluida"] is False:
        pass
    copa = json.loads(_linhas("SELECT copa_json FROM simulacao WHERE id = ?", sid)[0]["copa_json"])
    assert copa["fases"]["oitavas"] == oitavas          # a mesma de antes
    assert copa["fases"]["final"][0]["vencedor"]


def test_temporada_inteira_de_uma_vez_guarda_a_copa():
    sid = simulacao_service.salvar_temporada(seed=4, clube_usuario="Liverpool", ligas=DUAS)
    copa = json.loads(_linhas("SELECT copa_json FROM simulacao WHERE id = ?", sid)[0]["copa_json"])
    assert copa["fases"]["final"][0]["vencedor"]


def test_na_carreira_os_classificados_vem_da_tabela_anterior():
    sid = simulacao_service.salvar_temporada(seed=4, clube_usuario="Liverpool", ligas=DUAS)
    nova = carreira_service.proxima_temporada(sid)["simulacao_id"]
    tabela = _linhas(
        "SELECT nome, liga FROM clube WHERE simulacao_id = ? ORDER BY posicao_final", sid
    )
    copa = _copa_do_estado(nova)
    for liga in DUAS:
        assert copa["classificados"][liga] == [c["nome"] for c in tabela if c["liga"] == liga][:8]


def test_carreira_com_duas_ligas_campeao_da_liga_do_tecnico_e_copa():
    sid = simulacao_service.salvar_temporada(seed=4, clube_usuario="Liverpool", ligas=DUAS)
    cid = carreira_service.proxima_temporada(sid)["carreira_id"]
    c = carreira_service.detalhe_carreira(cid)
    t1 = c["temporadas"][0]

    liga = {r["nome"]: r["liga"] for r in _linhas("SELECT nome, liga FROM clube WHERE simulacao_id = ?", sid)}
    # campeão e vice da Premier (a liga do técnico), não o 1º da outra liga
    assert liga[t1["campeao"]] == liga[t1["vice"]] == "premier"
    assert t1["campeao_copa"] and c["titulos_copa"][0]["clube"] == t1["campeao_copa"]
    # o Liverpool foi 3º em 23/24: está na copa
    assert t1["copa_usuario"] in ("oitavas", "quartas", "semi", "final", "campeao")
