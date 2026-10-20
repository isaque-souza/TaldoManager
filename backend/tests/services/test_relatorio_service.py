"""Relatório de contratação (v2.0) de ponta a ponta: pedir, os dias
passarem, a mensagem do olheiro e o que a ficha mostra."""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.domain import relatorio
from app.main import app
from app.services import (
    calendario_service, mensagem_service, mercado_service, observado_service, temporada_service,
)
from app.services.relatorio_service import PedidoInvalido, pedir

client = TestClient(app)


def _iniciar():
    return temporada_service.iniciar(seed=11, clube_usuario="Real Taldo")


def _ficha(sid, nome):
    m = mercado_service.ver_mercado(sid)
    return next(f for f in m["disponiveis"] + m["livres"] if f["nome"] == nome)


def _observado(sid, i=0):
    """Um jogador de outro clube que não é "não vem", já observado."""
    m = mercado_service.ver_mercado(sid)
    f = [f for f in m["disponiveis"] if f["interesse"] is None][i]
    observado_service.observar(sid, f["nome"])
    return f["nome"]


def test_sem_relatorio_a_vontade_fica_escondida_menos_o_nao_vem():
    m = mercado_service.ver_mercado(_iniciar())
    escondidos = [f for f in m["disponiveis"] if f["interesse"] is None]
    visiveis = [f for f in m["disponiveis"] if f["interesse"] is not None]
    assert escondidos and all(f["relatorio"] is None for f in escondidos)
    assert all(f["interesse"]["bloqueio"] for f in visiveis)


def test_pedir_e_receber_quando_os_dias_passam():
    sid = _iniciar()
    nome = _observado(sid)
    r = pedir(sid, nome)
    hoje = date.fromisoformat(calendario_service.ver(sid)["data"])
    assert r["pronto_em"] == (hoje + timedelta(days=relatorio.DIAS[1])).isoformat()
    andamento = _ficha(sid, nome)
    assert andamento["relatorio"] == {"status": "andamento", "pronto_em": r["pronto_em"]}
    assert andamento["interesse"] is None

    # "Continuar" para no dia em que o relatório fica pronto
    v = calendario_service.continuar(sid)
    assert v["data"] == r["pronto_em"] and v["periodo"] == "pre_temporada"
    ultima = mensagem_service.listar(sid)["mensagens"][0]
    assert ultima["setor"] == "Olheiro" and nome in ultima["assunto"]

    f = _ficha(sid, nome)
    assert f["relatorio"]["status"] == "pronto"
    assert f["interesse"] is not None
    minimo, maximo = f["relatorio"]["preco"]
    assert minimo < maximo
    assert f["relatorio"]["dificuldade"] in ("facil", "media", "dificil", "impossivel")


def test_jogar_a_rodada_entrega_os_relatorios_do_caminho():
    sid = _iniciar()
    nome = _observado(sid)
    pedir(sid, nome)
    temporada_service.avancar(sid)
    assert _ficha(sid, nome)["relatorio"]["status"] == "pronto"


def test_pedidos_invalidos():
    sid = _iniciar()
    m = mercado_service.ver_mercado(sid)
    fora = next(f["nome"] for f in m["disponiveis"] if not f["observado"])
    with pytest.raises(PedidoInvalido):
        pedir(sid, fora)                 # não observado
    nome = _observado(sid)
    pedir(sid, nome)
    with pytest.raises(PedidoInvalido):
        pedir(sid, nome)                 # já pedido
    outro = _observado(sid, 1)
    with pytest.raises(PedidoInvalido):
        pedir(sid, outro)                # nível 1: um por vez


def test_api_pedir_relatorio():
    sid = _iniciar()
    nome = _observado(sid)
    r = client.post(f"/simulacoes/{sid}/relatorios", json={"nome": nome})
    assert r.status_code == 201 and r.json()["nome"] == nome
    assert client.post(f"/simulacoes/{sid}/relatorios", json={"nome": nome}).status_code == 400
    olheiro = client.get(f"/simulacoes/{sid}/mercado").json()["olheiro"]
    assert olheiro["relatorios_em_andamento"] == 1 and olheiro["relatorios_limite"] == 1
