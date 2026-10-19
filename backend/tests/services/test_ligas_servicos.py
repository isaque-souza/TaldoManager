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
