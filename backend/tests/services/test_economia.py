"""Economia v2 (v2.5): dinheiro por liga, patrocínio, salários na escala
nova — e os saves da v1 terminam a temporada nas regras antigas."""

import pytest

from app.db.conexao import conectar
from app.domain import financas
from app.domain.jogador import Jogador
from app.services import carreira_service, simulacao_service, temporada_service


@pytest.fixture(autouse=True)
def _sem_demissao(cargo_garantido):
    """A virada não é sobre a diretoria aqui."""


def _um_clube():
    return simulacao_service.listar_clubes()[0]["nome"]


def _sim(sid):
    conn = conectar()
    try:
        return conn.execute("SELECT * FROM simulacao WHERE id = ?", (sid,)).fetchone()
    finally:
        conn.close()


def _clubes(sid):
    conn = conectar()
    try:
        return {r["nome"]: r for r in conn.execute(
            "SELECT * FROM clube WHERE simulacao_id = ?", (sid,))}
    finally:
        conn.close()


def _rebaixar_para_v1(sid):
    conn = conectar()
    try:
        with conn:
            conn.execute("UPDATE simulacao SET economia = 1 WHERE id = ?", (sid,))
    finally:
        conn.close()


def test_save_novo_nasce_na_economia_atual():
    sid = temporada_service.iniciar(seed=1, clube_usuario=_um_clube())
    assert _sim(sid)["economia"] == financas.ECONOMIA_ATUAL


def test_rodada_da_v2_paga_patrocinio_e_a_tv_nova():
    sid = temporada_service.iniciar(seed=1, clube_usuario=_um_clube())
    temporada_service.avancar(sid)
    clubes = _clubes(sid).values()
    assert all(c["receita_patrocinio"] > 0 for c in clubes)
    assert all(c["receita_tv"] >= financas.cota_tv_rodada(38, c["liga"]) for c in clubes)


def test_save_da_v1_termina_a_temporada_nas_regras_antigas():
    sid = temporada_service.iniciar(seed=1, clube_usuario=_um_clube())
    _rebaixar_para_v1(sid)
    temporada_service.avancar(sid)
    for c in _clubes(sid).values():
        assert c["receita_tv"] == round(financas.COTA_TV_V1 / 38)
        assert c["receita_patrocinio"] == 0


def test_virada_de_um_save_v1_sobe_os_salarios_para_a_escala_nova():
    sid = simulacao_service.salvar_temporada(seed=3, clube_usuario=_um_clube())
    _rebaixar_para_v1(sid)
    # os contratos do save antigo estavam na escala de 0,08
    conn = conectar()
    try:
        with conn:
            conn.execute("UPDATE jogador SET salario = salario / 4 WHERE simulacao_id = ?", (sid,))
    finally:
        conn.close()

    nova = carreira_service.proxima_temporada(sid)["simulacao_id"]
    assert _sim(nova)["economia"] == financas.ECONOMIA_ATUAL
    conn = conectar()
    try:
        linhas = conn.execute(
            "SELECT overall, salario FROM jogador WHERE simulacao_id = ? AND clube_id IS NOT NULL",
            (nova,)).fetchall()
    finally:
        conn.close()
    # o contrato volta para perto da referência da escala nova (a virada
    # também evolui os jogadores, e quem subiu de overall fica abaixo dela)
    razoes = sorted(r["salario"] / Jogador.salario_de_mercado(r["overall"]) for r in linhas)
    mediana = razoes[len(razoes) // 2]
    assert 0.8 <= mediana <= 1.25
    # sem a migração, a mediana ficaria perto de 1/4


def test_detalhe_do_clube_traz_o_premio_da_posicao():
    clube = _um_clube()
    sid = temporada_service.iniciar(seed=1, clube_usuario=clube)
    temporada_service.avancar(sid)
    cid = next(c["id"] for c in _clubes(sid).values() if c["nome"] == clube)
    info = simulacao_service.detalhe_clube(sid, cid)["clube"]
    assert info["premio_posicao"] == financas.premiacao(info["posicao_final"], info["liga"])
