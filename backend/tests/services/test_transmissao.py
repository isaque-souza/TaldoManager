"""Simulação interativa (v1.2): a partida do técnico transmitida, com
mudanças de tática e substituições durante o jogo."""

import pytest

from app.services import (
    escalacao_service, simulacao_service, temporada_service, transmissao_service,
)
from app.services.temporada_service import PartidaEmAndamento
from app.services.transmissao_service import TransmissaoInvalida


def _clube():
    return simulacao_service.listar_clubes()[0]["nome"]


def _meu_time(t):
    return t["mandante"] if t["mandante"]["clube"] == t["clube_usuario"] else t["visitante"]


def _minha_partida(res):
    meu = res["clube_usuario"]
    return next(r for r in res["resultados"] if meu in (r["mandante"], r["visitante"]))


def _iniciada(seed=5):
    sid = temporada_service.iniciar(seed=seed, clube_usuario=_clube())
    return sid, transmissao_service.iniciar(sid)


def _troca_valida(t):
    """Um titular de linha e um reserva da mesma posição."""
    meu = _meu_time(t)
    for entra in meu["banco"]:
        sai = next(
            (j for j in meu["titulares"]
             if j["posicao"] == entra["posicao"] and j["posicao"] != "Goleiro"),
            None,
        )
        if sai:
            return sai["nome"], entra["nome"]
    raise AssertionError("elenco sem troca possível")


def test_sem_decisoes_a_transmissao_e_exatamente_a_partida_que_vale():
    sid, t = _iniciada()
    res = temporada_service.avancar(sid)
    minha = _minha_partida(res)

    assert t["minutos"][-1]["placar"] == [minha["gols_mandante"], minha["gols_visitante"]]
    assert len(t["minutos"]) == 90 + t["acrescimos"]

    det = simulacao_service.detalhe_partida(sid, minha["partida_id"])
    assert det["partida"]["acrescimos"] == t["acrescimos"]
    assert [(e["minuto"], e["tipo"], e["jogador"]) for e in det["eventos"]] == [
        (e["minuto"], e["tipo"], e["jogador"]) for e in t["eventos"]
    ]


def test_outros_jogos_da_transmissao_batem_com_a_rodada_gravada():
    sid, t = _iniciada()
    res = temporada_service.avancar(sid)
    gravados = {
        p["mandante"]: [(g["minuto"], g["clube"]) for g in p["gols"]]
        for p in simulacao_service.ao_vivo(sid, 1)["partidas"]
    }
    assert len(t["outros"]) == len(res["resultados"]) - 1
    for jogo in t["outros"]:
        assert sorted((g["minuto"], g["clube"]) for g in jogo["gols"]) == sorted(gravados[jogo["mandante"]])


def test_decisao_nao_muda_o_passado_nem_os_outros_jogos():
    sid, t = _iniciada()
    sai, entra = _troca_valida(t)
    depois = transmissao_service.decidir(sid, 46, sai=sai, entra=entra)

    assert depois["minutos"][:45] == t["minutos"][:45]
    assert [e for e in depois["eventos"] if e["minuto"] < 46] == [
        e for e in t["eventos"] if e["minuto"] < 46
    ]
    assert depois["outros"] == t["outros"]
    assert depois["decisoes"] == [
        {"minuto": 46, "clube": t["clube_usuario"], "sai": sai, "entra": entra}
    ]


def test_substituicao_do_tecnico_vale_na_rodada_gravada():
    sid, t = _iniciada()
    sai, entra = _troca_valida(t)
    final = transmissao_service.decidir(sid, 30, sai=sai, entra=entra)

    troca = next(e for e in final["eventos"] if e["tipo"] == "substituicao" and e["minuto"] == 30)
    assert (troca["jogador"], troca["detalhe"]) == (entra, f"sai {sai}")

    res = temporada_service.avancar(sid)
    minha = _minha_partida(res)
    assert final["minutos"][-1]["placar"] == [minha["gols_mandante"], minha["gols_visitante"]]
    det = simulacao_service.detalhe_partida(sid, minha["partida_id"])
    assert any(e["tipo"] == "substituicao" and e["minuto"] == 30 and e["jogador"] == entra
               for e in det["eventos"])


def test_tatica_mudada_no_jogo_nao_fica_para_a_proxima_rodada():
    sid, t = _iniciada()
    original = _meu_time(t)["tatica"]
    nova = "ofensivo" if original != "ofensivo" else "defensivo"

    transmissao_service.decidir(sid, 10, tatica=nova)
    assert transmissao_service.estado(sid, 10)["clubes"][
        0 if t["mandante"]["clube"] == t["clube_usuario"] else 1
    ]["tatica"] == nova

    temporada_service.avancar(sid)
    assert temporada_service.proxima_rodada(sid)["tatica"] == original


def test_estado_mostra_quem_esta_em_campo_e_o_banco():
    sid, t = _iniciada()
    lado = 0 if t["mandante"]["clube"] == t["clube_usuario"] else 1
    inicio = transmissao_service.estado(sid, 0)["clubes"][lado]
    assert len(inicio["em_campo"]) == 11
    assert inicio["substituicoes_restantes"] == 5
    assert all(j["disponivel"] for j in inicio["banco"])

    sai, entra = _troca_valida(t)
    transmissao_service.decidir(sid, 20, sai=sai, entra=entra)
    agora = transmissao_service.estado(sid, 20)["clubes"][lado]
    nomes = {j["nome"] for j in agora["em_campo"]}
    assert entra in nomes and sai not in nomes
    assert agora["substituicoes_restantes"] == 4
    assert next(j for j in agora["banco"] if j["nome"] == sai)["disponivel"] is False


def test_decisoes_invalidas_sao_recusadas():
    sid, t = _iniciada()
    sai, entra = _troca_valida(t)

    with pytest.raises(TransmissaoInvalida):   # quem entra precisa estar no banco
        transmissao_service.decidir(sid, 10, sai=sai, entra=sai)
    with pytest.raises(TransmissaoInvalida):   # nem tática nem troca
        transmissao_service.decidir(sid, 10)
    with pytest.raises(TransmissaoInvalida):
        transmissao_service.decidir(sid, 10, tatica="retranca")

    transmissao_service.decidir(sid, 40, sai=sai, entra=entra)
    with pytest.raises(TransmissaoInvalida):   # não volta no tempo
        transmissao_service.decidir(sid, 39, tatica="ofensivo")
    with pytest.raises(TransmissaoInvalida):   # quem saiu não volta
        transmissao_service.decidir(sid, 41, sai=entra, entra=sai)
    with pytest.raises(TransmissaoInvalida):   # depois do apito
        transmissao_service.decidir(sid, 200, tatica="ofensivo")


def test_elenco_fica_travado_durante_a_partida():
    sid, _ = _iniciada()
    assert temporada_service.proxima_rodada(sid)["transmissao_ativa"] is True
    with pytest.raises(PartidaEmAndamento):
        escalacao_service.salvar_decisao(sid, tatica="ofensivo")

    temporada_service.avancar(sid)
    assert temporada_service.proxima_rodada(sid)["transmissao_ativa"] is False
    assert escalacao_service.salvar_decisao(sid, tatica="ofensivo")["tatica"] == "ofensivo"


def test_iniciar_de_novo_retoma_a_mesma_partida():
    sid, t = _iniciada()
    sai, entra = _troca_valida(t)
    feita = transmissao_service.decidir(sid, 50, sai=sai, entra=entra)

    # o corpo é ignorado: o time já entrou em campo
    retomada = transmissao_service.iniciar(sid, tatica="defensivo")
    assert retomada == feita
    assert transmissao_service.atual(sid) == feita


def test_iniciar_grava_a_escalacao_do_apito():
    sid = temporada_service.iniciar(seed=5, clube_usuario=_clube())
    t = transmissao_service.iniciar(sid, tatica="defensivo")
    assert _meu_time(t)["tatica"] == "defensivo"
    assert temporada_service.proxima_rodada(sid)["tatica"] == "defensivo"


def test_sem_transmissao_atual_e_none_e_estado_recusa():
    sid = temporada_service.iniciar(seed=5, clube_usuario=_clube())
    assert transmissao_service.atual(sid) is None
    with pytest.raises(TransmissaoInvalida):
        transmissao_service.estado(sid, 10)
    assert transmissao_service.iniciar(999_999) is None
