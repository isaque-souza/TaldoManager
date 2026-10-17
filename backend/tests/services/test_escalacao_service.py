import pytest

from app.services import escalacao_service, simulacao_service, temporada_service
from app.services.temporada_service import TemporadaConcluida


def _um_clube():
    return simulacao_service.listar_clubes()[0]["nome"]


def _decisao(sid):
    """Uma escalação diferente da padrão: outra formação, tática ofensiva e
    um XI escolhido a dedo."""
    info = temporada_service.proxima_rodada(sid)
    formacao = next(f for f in info["formacoes"] if f != info["formacao"])
    xi = sorted(j["nome"] for j in info["elenco"])[:11]
    return {"tatica": "ofensivo", "formacao": formacao, "xi_preferido": xi}


def test_salvar_decisao_grava_sem_jogar_a_rodada():
    sid = temporada_service.iniciar(seed=3, clube_usuario=_um_clube())
    decisao = _decisao(sid)

    salva = escalacao_service.salvar_decisao(sid, **decisao)

    assert salva["tatica"] == "ofensivo"
    assert salva["formacao"] == decisao["formacao"]
    assert salva["xi_preferido"] == decisao["xi_preferido"]

    # a próxima rodada (o que o front mostra ao reabrir) já vem com ela,
    # e nenhuma rodada foi jogada
    info = temporada_service.proxima_rodada(sid)
    assert info["rodada"] == 1
    assert info["tatica"] == "ofensivo"
    assert info["formacao"] == decisao["formacao"]
    assert info["xi_preferido"] == decisao["xi_preferido"]


def test_o_que_nao_vem_fica_como_esta():
    sid = temporada_service.iniciar(seed=3, clube_usuario=_um_clube())
    decisao = _decisao(sid)
    escalacao_service.salvar_decisao(sid, **decisao)

    salva = escalacao_service.salvar_decisao(sid, tatica="defensivo")

    assert salva["tatica"] == "defensivo"
    assert salva["formacao"] == decisao["formacao"]
    assert salva["xi_preferido"] == decisao["xi_preferido"]


def test_salvar_e_jogar_da_a_mesma_rodada_que_jogar_mandando_a_decisao():
    clube = _um_clube()
    salvou = temporada_service.iniciar(seed=8, clube_usuario=clube)
    mandou = temporada_service.iniciar(seed=8, clube_usuario=clube)
    decisao = _decisao(salvou)

    escalacao_service.salvar_decisao(salvou, **decisao)
    a = temporada_service.avancar(salvou)
    b = temporada_service.avancar(mandou, **decisao)

    placar = lambda r: [  # noqa: E731
        (p["mandante"], p["gols_mandante"], p["gols_visitante"])
        for p in r["resultados"]
    ]
    assert placar(a) == placar(b)


def test_salvar_decisao_avanca_atualizada_em():
    sid = temporada_service.iniciar(seed=3, clube_usuario=_um_clube())
    antes = simulacao_service.listar_simulacoes()[0]["atualizada_em"]

    salva = escalacao_service.salvar_decisao(sid, tatica="defensivo")

    assert salva["atualizada_em"] > antes


def test_xi_fora_do_elenco_e_recusado_e_nada_muda():
    sid = temporada_service.iniciar(seed=3, clube_usuario=_um_clube())
    antes = temporada_service.proxima_rodada(sid)

    with pytest.raises(ValueError):
        escalacao_service.salvar_decisao(sid, xi_preferido=["Fulano de Tal"])
    with pytest.raises(ValueError):
        escalacao_service.salvar_decisao(sid, formacao="1-1-8")

    depois = temporada_service.proxima_rodada(sid)
    assert depois["xi_preferido"] == antes["xi_preferido"]
    assert depois["formacao"] == antes["formacao"]


def test_simulacao_inexistente_devolve_none():
    assert escalacao_service.salvar_decisao(9999, tatica="ofensivo") is None


def test_temporada_concluida_nao_aceita_decisao():
    sid = simulacao_service.salvar_temporada(seed=1)

    with pytest.raises(TemporadaConcluida):
        escalacao_service.salvar_decisao(sid, tatica="ofensivo")


def test_xi_vazio_poe_todos_no_automatico():
    sid = temporada_service.iniciar(seed=3, clube_usuario=_um_clube())
    escalacao_service.salvar_decisao(sid, **_decisao(sid))

    salva = escalacao_service.salvar_decisao(sid, xi_preferido=[])

    assert salva["xi_preferido"] is None
    assert temporada_service.proxima_rodada(sid)["xi_preferido"] is None


def test_jogar_com_xi_vazio_tambem_limpa():
    sid = temporada_service.iniciar(seed=3, clube_usuario=_um_clube())
    escalacao_service.salvar_decisao(sid, **_decisao(sid))

    temporada_service.avancar(sid, xi_preferido=[])

    assert temporada_service.proxima_rodada(sid)["xi_preferido"] is None
