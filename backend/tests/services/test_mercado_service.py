"""Mercado de transferências de ponta a ponta: serviço + banco + snapshot."""

import json

import pytest

from app.db.conexao import conectar
from app.repositories import simulacao_repository as simulacao_repo

from app.domain.mercado import TransferenciaInvalida
from app.services import mercado_service, simulacao_service, temporada_service
from app.services.temporada_service import TemporadaConcluida


def _iniciar(seed=11):
    clube = simulacao_service.listar_clubes()[0]["nome"]
    return temporada_service.iniciar(seed=seed, clube_usuario=clube), clube


def _compravel(m):
    return next(f for f in m["disponiveis"] if f["bloqueio"] is None)


def test_mercado_abre_antes_da_rodada_1():
    sid, clube = _iniciar()
    m = mercado_service.ver_mercado(sid)
    assert m["janela_aberta"] and m["rodada"] == 1
    assert m["clube_usuario"] == clube
    assert len(m["elenco"]) == 18
    assert all(f["clube"] != clube for f in m["disponiveis"])


def test_filtros_de_posicao_e_valor():
    sid, _ = _iniciar()
    m = mercado_service.ver_mercado(sid, posicao="Goleiro", valor_max=2_000_000)
    assert m["disponiveis"]
    assert all(f["posicao"] == "Goleiro" for f in m["disponiveis"])
    assert all(f["valor_mercado"] <= 2_000_000 for f in m["disponiveis"])


def test_compra_tira_do_caixa_e_o_jogador_continua_no_clube_novo():
    sid, clube = _iniciar()
    antes = mercado_service.ver_mercado(sid)
    alvo = _compravel(antes)

    feita = mercado_service.transferir(sid, alvo["jogador_id"], "compra")
    assert feita["para_clube"] == clube and feita["de_clube"] == alvo["clube"]
    assert feita["caixa"] == antes["caixa"] - alvo["valor_mercado"]

    # o elenco novo sobrevive ao snapshot, e o jogador entra em campo
    temporada_service.avancar(sid)
    depois = mercado_service.ver_mercado(sid)
    assert alvo["nome"] in [f["nome"] for f in depois["elenco"]]
    assert len(depois["elenco"]) == 19

    detalhe = simulacao_service.game_log_jogador(sid, alvo["jogador_id"])
    assert detalhe["jogador"]["clube"] == clube
    assert depois["transferencias"][0]["jogador"] == alvo["nome"]


def test_venda_vai_para_o_clube_mais_rico_e_entra_no_caixa():
    sid, clube = _iniciar()
    antes = mercado_service.ver_mercado(sid)
    vendido = next(f for f in antes["elenco"] if f["bloqueio"] is None)

    feita = mercado_service.transferir(sid, vendido["jogador_id"], "venda")
    assert feita["de_clube"] == clube and feita["para_clube"] != clube
    assert feita["caixa"] == antes["caixa"] + vendido["valor_mercado"]
    assert len(mercado_service.ver_mercado(sid)["elenco"]) == 17


def test_janela_fecha_depois_da_rodada_1():
    sid, _ = _iniciar()
    temporada_service.avancar(sid)
    m = mercado_service.ver_mercado(sid)
    assert not m["janela_aberta"]
    assert all(f["bloqueio"] for f in m["disponiveis"])
    with pytest.raises(TransferenciaInvalida, match="fechada"):
        mercado_service.transferir(sid, m["disponiveis"][0]["jogador_id"], "compra")


def test_nao_compra_jogador_do_proprio_elenco():
    sid, _ = _iniciar()
    meu = mercado_service.ver_mercado(sid)["elenco"][0]
    with pytest.raises(TransferenciaInvalida):
        mercado_service.transferir(sid, meu["jogador_id"], "compra")


def test_transferencia_nao_mexe_na_sorte_da_temporada():
    # comprar não pode consumir números aleatórios: a corrente de RNG gravada
    # no snapshot tem que ser a mesma de um save idêntico sem transferência
    sem, _ = _iniciar(seed=21)
    com, _ = _iniciar(seed=21)
    mercado_service.transferir(
        com, _compravel(mercado_service.ver_mercado(com))["jogador_id"], "compra"
    )
    assert _rng(sem) == _rng(com)


def _rng(sid):
    conn = conectar()
    try:
        return json.loads(simulacao_repo.buscar(conn, sid)["estado_json"])["rng"]
    finally:
        conn.close()


def test_sem_mercado_em_temporada_concluida():
    sid = simulacao_service.salvar_temporada(seed=3)
    with pytest.raises(TemporadaConcluida):
        mercado_service.ver_mercado(sid)


def test_simulacao_ou_jogador_inexistente():
    assert mercado_service.ver_mercado(999_999) is None
    sid, _ = _iniciar()
    assert mercado_service.transferir(sid, 999_999, "compra") is None
