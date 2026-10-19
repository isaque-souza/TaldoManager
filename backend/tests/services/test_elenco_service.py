"""Central do Elenco (v1.7): lista de transferências e dispensa, com banco
e snapshot."""

import json

import pytest

from app.db.conexao import conectar
from app.domain import mercado
from app.domain.mercado import TransferenciaInvalida
from app.repositories import clube_repository as clube_repo
from app.repositories import jogador_repository as jogador_repo
from app.repositories import mensagem_repository as mensagem_repo
from app.repositories import simulacao_repository as simulacao_repo
from app.services import carreira_service, mercado_service, temporada_service


def _iniciar(seed=11, clube="Real Taldo"):
    return temporada_service.iniciar(seed=seed, clube_usuario=clube)


def _reserva(m):
    """Um jogador do elenco que dá para dispensar: o reserva mais fraco que
    não é goleiro (jovem e com contrato, para seguir no clube na virada)."""
    return min(
        (
            f for f in m["elenco"]
            if f["posicao"] != "Goleiro" and f["idade"] < 30 and f["contrato_anos"] >= 2
        ),
        key=lambda f: f["overall"],
    )


def _rng(sid):
    conn = conectar()
    try:
        return json.loads(simulacao_repo.buscar(conn, sid)["estado_json"])["rng"]
    finally:
        conn.close()


def _jogar_ate_o_fim(sid):
    while temporada_service.avancar(sid)["concluida"] is False:
        pass


def test_lista_de_transferencias_fica_gravada_e_segue_nas_rodadas():
    sid = _iniciar()
    alvo = mercado_service.ver_mercado(sid)["elenco"][-1]
    assert alvo["a_venda"] is False

    r = mercado_service.marcar_a_venda(sid, alvo["jogador_id"], True)
    assert r == {"jogador_id": alvo["jogador_id"], "jogador": alvo["nome"], "a_venda": True}

    temporada_service.avancar(sid)
    elenco = {f["nome"]: f for f in mercado_service.ver_mercado(sid)["elenco"]}
    assert elenco[alvo["nome"]]["a_venda"] is True

    mercado_service.marcar_a_venda(sid, alvo["jogador_id"], False)
    elenco = {f["nome"]: f for f in mercado_service.ver_mercado(sid)["elenco"]}
    assert elenco[alvo["nome"]]["a_venda"] is False


def test_lista_de_transferencias_segue_para_a_temporada_seguinte():
    sid = _iniciar(seed=5)
    alvo = _reserva(mercado_service.ver_mercado(sid))
    mercado_service.marcar_a_venda(sid, alvo["jogador_id"], True)
    _jogar_ate_o_fim(sid)

    nova = carreira_service.proxima_temporada(sid)["simulacao_id"]
    elenco = {f["nome"]: f for f in mercado_service.ver_mercado(nova)["elenco"]}
    assert elenco[alvo["nome"]]["a_venda"] is True


def test_so_marca_jogador_do_proprio_elenco():
    sid = _iniciar()
    outro = mercado_service.ver_mercado(sid)["disponiveis"][0]
    with pytest.raises(TransferenciaInvalida):
        mercado_service.marcar_a_venda(sid, outro["jogador_id"], True)
    assert mercado_service.marcar_a_venda(sid, 999_999, True) is None


def test_elenco_mostra_o_custo_da_dispensa():
    sid = _iniciar()
    for f in mercado_service.ver_mercado(sid)["elenco"]:
        assert f["rescisao"] == round(f["salario"] * f["contrato_anos"] * 0.5 / 10_000) * 10_000
    # Real Taldo tem 3 goleiros e 23 jogadores: dá para dispensar qualquer um
    assert all(f["dispensa_bloqueada"] is None for f in mercado_service.ver_mercado(sid)["elenco"])


def test_dispensar_paga_a_rescisao_e_o_jogador_fica_livre():
    sid = _iniciar()
    m = mercado_service.ver_mercado(sid)
    alvo = _reserva(m)

    r = mercado_service.dispensar(sid, alvo["jogador_id"])

    assert r["jogador"] == alvo["nome"] and r["rescisao"] == alvo["rescisao"]
    assert r["caixa"] == m["caixa"] - alvo["rescisao"]
    depois = mercado_service.ver_mercado(sid)
    assert alvo["nome"] not in {f["nome"] for f in depois["elenco"]}
    livre = next(f for f in depois["livres"] if f["nome"] == alvo["nome"])
    assert livre["contrato_anos"] == 0
    assert len(depois["livres"]) == len(m["livres"]) + 1

    conn = conectar()
    try:
        assuntos = [m["assunto"] for m in mensagem_repo.listar(conn, sid)]
    finally:
        conn.close()
    assert f"Dispensado: {alvo['nome']}" in assuntos


def test_dispensa_vale_com_a_janela_fechada_e_nao_mexe_na_sorte():
    sid = _iniciar()
    temporada_service.avancar(sid)
    assert not mercado.janela_aberta(2)
    alvo = _reserva(mercado_service.ver_mercado(sid))
    antes = _rng(sid)
    mercado_service.dispensar(sid, alvo["jogador_id"])
    assert _rng(sid) == antes


def test_dispensado_some_do_elenco_do_clube_mas_guarda_o_que_jogou():
    sid = _iniciar()
    temporada_service.avancar(sid)
    alvo = _reserva(mercado_service.ver_mercado(sid))
    mercado_service.dispensar(sid, alvo["jogador_id"])
    temporada_service.avancar(sid)   # regrava a tabela depois de mais uma rodada

    conn = conectar()
    try:
        linha = jogador_repo.buscar(conn, alvo["jogador_id"])
        clube_id = linha["clube_id"]
        elenco = {r["nome"] for r in jogador_repo.listar_por_clube(conn, clube_id)}
        todos = {r["nome"] for r in jogador_repo.listar_por_simulacao(conn, sid)}
    finally:
        conn.close()
    # a linha fica (lances e atuações apontam para ela), marcada como livre
    assert linha["livre"] == 1 and linha["clube"] == "Real Taldo"
    assert alvo["nome"] not in elenco
    assert alvo["nome"] in todos


def test_dispensado_nao_volta_para_o_clube_na_virada():
    sid = _iniciar(seed=5)
    alvo = _reserva(mercado_service.ver_mercado(sid))
    mercado_service.dispensar(sid, alvo["jogador_id"])
    _jogar_ate_o_fim(sid)

    nova = carreira_service.proxima_temporada(sid)["simulacao_id"]
    conn = conectar()
    try:
        meu = next(
            c["id"] for c in clube_repo.listar_por_simulacao(conn, nova)
            if c["nome"] == "Real Taldo"
        )
        elenco = {r["nome"] for r in jogador_repo.listar_por_clube(conn, meu)}
    finally:
        conn.close()
    assert alvo["nome"] not in elenco


def test_dispensado_pode_ser_contratado_de_volta_com_a_mesma_linha():
    sid = _iniciar()
    alvo = _reserva(mercado_service.ver_mercado(sid))
    mercado_service.dispensar(sid, alvo["jogador_id"])

    mercado_service.contratar_livre(sid, alvo["nome"])

    volta = next(
        f for f in mercado_service.ver_mercado(sid)["elenco"] if f["nome"] == alvo["nome"]
    )
    assert volta["jogador_id"] == alvo["jogador_id"]
    conn = conectar()
    try:
        assert jogador_repo.buscar(conn, alvo["jogador_id"])["livre"] == 0
    finally:
        conn.close()


def test_so_dispensa_jogador_do_proprio_elenco():
    sid = _iniciar()
    outro = mercado_service.ver_mercado(sid)["disponiveis"][0]
    with pytest.raises(TransferenciaInvalida):
        mercado_service.dispensar(sid, outro["jogador_id"])
    assert mercado_service.dispensar(sid, 999_999) is None
