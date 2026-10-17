import pytest

from app.db.conexao import conectar
from app.repositories import clube_repository as clube_repo
from app.services import simulacao_service, temporada_service
from app.services.temporada_service import TemporadaConcluida


def _um_clube():
    return simulacao_service.listar_clubes()[0]["nome"]


def _jogar_ate_o_fim(sid):
    rodadas = 0
    while not temporada_service.proxima_rodada(sid)["concluida"]:
        r = temporada_service.avancar(sid)
        rodadas += 1
    return rodadas, r


def test_iniciar_exige_clube():
    with pytest.raises(ValueError):
        temporada_service.iniciar(seed=1)


def test_iniciar_cria_save_em_andamento_na_rodada_1():
    sid = temporada_service.iniciar(seed=1, clube_usuario=_um_clube())

    visao = simulacao_service.carregar_temporada(sid)
    assert visao["estado"] == "em_andamento"
    assert visao["rodada_atual"] == 1
    assert visao["campeao"] is None
    # nada jogado ainda
    assert all(c["jogos"] == 0 for c in visao["classificacao"])


def test_avancar_joga_uma_rodada_e_incrementa():
    clube = _um_clube()
    sid = temporada_service.iniciar(seed=1, clube_usuario=clube)

    r = temporada_service.avancar(sid)
    assert r["rodada_jogada"] == 1
    assert r["concluida"] is False
    assert len(r["resultados"]) == 10
    assert r["rodada_atual"] == 2

    # 20 clubes jogaram exatamente uma vez
    jogos = [c["jogos"] for c in r["classificacao"]]
    assert set(jogos) == {1}


def test_proxima_rodada_traz_confronto_e_elenco_do_clube():
    clube = _um_clube()
    sid = temporada_service.iniciar(seed=2, clube_usuario=clube)

    pr = temporada_service.proxima_rodada(sid)
    assert pr["concluida"] is False
    assert pr["rodada"] == 1
    assert pr["clube_usuario"] == clube
    assert pr["adversario"] is not None
    assert pr["mando"] in ("casa", "fora")
    assert len(pr["confrontos"]) == 10
    assert len(pr["elenco"]) >= 11
    assert {"nome", "posicao", "overall", "energia", "condicao"} <= set(
        pr["elenco"][0]
    )


def test_temporada_completa_termina_com_campeao():
    sid = temporada_service.iniciar(seed=3, clube_usuario=_um_clube())
    rodadas, ultimo = _jogar_ate_o_fim(sid)

    assert rodadas == 38
    assert ultimo["concluida"] is True

    visao = simulacao_service.carregar_temporada(sid)
    assert visao["estado"] == "concluida"
    assert visao["campeao"] == visao["classificacao"][0]["clube"]
    assert visao["rodada_atual"] is None
    assert len(visao["historico"]) == 380
    assert all(c["jogos"] == 38 for c in visao["classificacao"])


def test_nao_da_pra_avancar_temporada_concluida():
    sid = temporada_service.iniciar(seed=4, clube_usuario=_um_clube())
    _jogar_ate_o_fim(sid)

    with pytest.raises(TemporadaConcluida):
        temporada_service.avancar(sid)


def test_avancar_com_decisao_invalida_levanta_valueerror():
    sid = temporada_service.iniciar(seed=5, clube_usuario=_um_clube())
    with pytest.raises(ValueError):
        temporada_service.avancar(sid, formacao="9-0-1")


def test_rodada_a_rodada_reproduz_a_temporada_continua():
    clube = simulacao_service.listar_clubes()[3]["nome"]

    continua = simulacao_service.simular_temporada(
        seed=123, clube_usuario=clube, tatica="defensivo"
    )
    sid = temporada_service.iniciar(
        seed=123, clube_usuario=clube, tatica="defensivo"
    )
    _jogar_ate_o_fim(sid)
    passo_a_passo = simulacao_service.carregar_temporada(sid)

    tab_a = [(c["clube"], c["pontos"], c["saldo_gols"]) for c in continua["classificacao"]]
    tab_b = [(c["clube"], c["pontos"], c["saldo_gols"]) for c in passo_a_passo["classificacao"]]
    assert tab_a == tab_b
    assert continua["campeao"] == passo_a_passo["campeao"]


def test_financas_rodada_a_rodada_batem_com_a_temporada_continua():
    # o caixa e os totais passam pelo snapshot entre as rodadas; se algum
    # campo ficasse de fora, o save rodada a rodada divergiria
    clube = _um_clube()
    continua = simulacao_service.salvar_temporada(seed=77, clube_usuario=clube)
    sid = temporada_service.iniciar(seed=77, clube_usuario=clube)
    _jogar_ate_o_fim(sid)

    campos = ("nome", "dinheiro_inicial", "dinheiro", "receita_tv",
              "receita_bilheteria", "receita_premiacao", "despesa_salarios",
              "historico_caixa")
    conn = conectar()
    try:
        a = [tuple(r[c] for c in campos) for r in clube_repo.listar_por_simulacao(conn, continua)]
        b = [tuple(r[c] for c in campos) for r in clube_repo.listar_por_simulacao(conn, sid)]
    finally:
        conn.close()

    assert a == b
    assert all(r[2] != r[1] for r in a)   # o caixa de fato se moveu


def test_avancar_persiste_partidas_para_as_paginas_de_navegacao():
    sid = temporada_service.iniciar(seed=6, clube_usuario=_um_clube())
    temporada_service.avancar(sid)
    temporada_service.avancar(sid)

    visao = simulacao_service.carregar_temporada(sid)
    algum_clube_id = visao["classificacao"][0]["id"]
    detalhe = simulacao_service.detalhe_clube(sid, algum_clube_id)
    assert detalhe is not None
    jogados = [j for j in detalhe["jogos"] if j["gols_pro"] is not None]
    assert len(jogados) == 2

    # a página da partida também
    pid = detalhe["jogos"][0]["partida_id"]
    assert simulacao_service.detalhe_partida(sid, pid) is not None


def test_proxima_rodada_expoe_situacao_de_suspensao_e_lesao():
    sid = temporada_service.iniciar(seed=2, clube_usuario=_um_clube())
    pr = temporada_service.proxima_rodada(sid)
    assert {
        "suspenso", "jogos_suspensao", "amarelos_ciclo",
        "lesionado", "rodadas_lesao",
    } <= set(pr["elenco"][0])
    assert all(j["suspenso"] is False for j in pr["elenco"])     # rodada 1
    assert all(j["lesionado"] is False for j in pr["elenco"])


def test_suspensao_sobrevive_ao_snapshot():
    import json

    from app.db.conexao import conectar
    from app.repositories import simulacao_repository as simulacao_repo

    sid = temporada_service.iniciar(seed=7, clube_usuario=_um_clube())
    for _ in range(6):
        temporada_service.avancar(sid)

    conn = conectar()
    try:
        blob = json.loads(simulacao_repo.buscar(conn, sid)["estado_json"])
    finally:
        conn.close()

    jogadores = [
        j
        for clube in blob["clubes"].values()
        for j in clube["jogadores"].values()
    ]
    assert any("jogos_suspensao" in j for j in jogadores)
    # avançar de novo não explode (restaura os contadores)
    temporada_service.avancar(sid)


def test_proxima_rodada_none_quando_simulacao_nao_existe():
    assert temporada_service.proxima_rodada(9999) is None


def test_avancar_none_quando_simulacao_nao_existe():
    assert temporada_service.avancar(9999) is None
