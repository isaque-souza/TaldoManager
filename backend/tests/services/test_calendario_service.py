"""Calendário (v2.0) de ponta a ponta: o save anda dia a dia e o jogo leva
o calendário até o dia dele."""

import pytest
from fastapi.testclient import TestClient

from app.db.conexao import conectar
from app.domain import calendario
from app.main import app
from app.repositories import mensagem_repository as mensagem_repo
from app.services import calendario_service, mensagem_service, temporada_service
from app.services.temporada_service import TemporadaConcluida

client = TestClient(app)


def _iniciar():
    return temporada_service.iniciar(seed=11, clube_usuario="Real Taldo")


def test_save_novo_comeca_na_pre_temporada():
    v = calendario_service.ver(_iniciar())
    assert v["data"] == calendario.inicio(1).isoformat()
    assert v["periodo"] == "pre_temporada" and v["janela_aberta"]
    assert v["dias_ate_o_jogo"] == 28 and v["temporada"] == "2026/27"


def test_avancar_um_dia_e_continuar():
    sid = _iniciar()
    assert calendario_service.avancar_dia(sid)["dias_ate_o_jogo"] == 27
    v = calendario_service.continuar(sid)
    assert v["periodo"] == "dia_de_jogo" and v["dias_ate_o_jogo"] == 0
    # no dia do jogo, o calendário não anda sem jogar
    assert calendario_service.avancar_dia(sid)["data"] == v["data"]


def test_jogar_leva_ao_dia_do_jogo_e_as_mensagens_tem_data():
    sid = _iniciar()
    inicio = calendario.inicio(1).isoformat()
    assert all(m["data"] == inicio for m in mensagem_service.listar(sid)["mensagens"])

    temporada_service.avancar(sid)   # sem passar os dias antes: joga igual
    v = calendario_service.ver(sid)
    jogo = calendario.data_da_rodada(1, 1).isoformat()
    assert v["data"] == jogo and v["rodada"] == 2 and v["dias_ate_o_jogo"] == 7


def test_mensagem_nova_leva_o_dia_do_save():
    sid = _iniciar()
    v = calendario_service.avancar_dia(sid)
    conn = conectar()
    with conn:
        mensagem_repo.inserir(conn, sid, None, [{"setor": "Teste", "assunto": "a", "corpo": "b"}])
    conn.close()
    assert mensagem_service.listar(sid)["mensagens"][0]["data"] == v["data"]


def test_api_do_calendario():
    sid = _iniciar()
    assert client.get(f"/simulacoes/{sid}/calendario").json()["periodo"] == "pre_temporada"
    assert client.post(f"/simulacoes/{sid}/calendario/dia").json()["dias_ate_o_jogo"] == 27
    assert client.post(f"/simulacoes/{sid}/calendario/continuar").json()["periodo"] == "dia_de_jogo"
    proxima = client.get(f"/simulacoes/{sid}/rodadas/proxima").json()
    assert proxima["calendario"]["periodo"] == "dia_de_jogo"
    assert client.get("/simulacoes/99999/calendario").status_code == 404


def test_temporada_concluida_nao_anda():
    sid = _iniciar()
    conn = conectar()
    with conn:
        conn.execute("UPDATE simulacao SET estado = 'concluida' WHERE id = ?", (sid,))
    conn.close()
    assert calendario_service.ver(sid)["periodo"] == "concluida"
    with pytest.raises(TemporadaConcluida):
        calendario_service.avancar_dia(sid)
