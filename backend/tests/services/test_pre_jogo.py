"""Pré-jogo (v1.1): as escalações que o motor vai usar, antes do apito."""

import pytest

from app.services import escalacao_service, simulacao_service, temporada_service
from app.services.temporada_service import TemporadaConcluida


def _clube_do_ranking(ranking):
    return next(
        c["nome"] for c in simulacao_service.listar_clubes() if c["ranking_forca"] == ranking
    )


def _sim(seed=4, ranking=6):
    return temporada_service.iniciar(seed=seed, clube_usuario=_clube_do_ranking(ranking))


def _xi_jogado(sid, rodada, clube):
    """Titulares que entraram em campo na partida do clube naquela rodada."""
    res = temporada_service.avancar(sid)
    assert res["rodada_jogada"] == rodada
    p = next(r for r in res["resultados"] if clube in (r["mandante"], r["visitante"]))
    det = simulacao_service.detalhe_partida(sid, p["partida_id"])
    lado = "escalacao_mandante" if det["partida"]["mandante"]["nome"] == clube else "escalacao_visitante"
    return {a["jogador"] for a in det[lado] if a["titular"]}


def test_pre_jogo_traz_os_dois_times_com_11_titulares_numerados():
    sid = _sim()
    pj = temporada_service.pre_jogo(sid)

    assert pj["rodada"] == 1 and pj["adversario"]
    for lado in (pj["mandante"], pj["visitante"]):
        assert len(lado["titulares"]) == 11
        assert all(j["numero"] is not None for j in lado["titulares"] + lado["banco"])
        assert [j["linha"] for j in lado["titulares"]][0] == 0   # goleiro primeiro
    assert pj["clube_usuario"] in (pj["mandante"]["clube"], pj["visitante"]["clube"])


def test_linhas_seguem_a_formacao():
    sid = _sim()
    escalacao_service.salvar_decisao(sid, formacao="3-5-2")
    pj = temporada_service.pre_jogo(sid)
    meu = pj["mandante"] if pj["mandante"]["clube"] == pj["clube_usuario"] else pj["visitante"]

    rotulos = sorted(j["rotulo"] for j in meu["titulares"])
    assert meu["formacao"] == "3-5-2"
    # 3 zagueiros, 2 alas, volante, 2 meias centrais e 2 centroavantes, cada
    # um no seu lugar do desenho (v1.3)
    assert rotulos == sorted(["GOL", "ZAG", "ZAG", "ZAG", "ALA", "ALA", "VOL", "MC", "MC", "CA", "CA"])
    assert all(j["x"] is not None and j["y"] is not None for j in meu["titulares"])


def test_pre_jogo_mostra_exatamente_quem_entra_em_campo():
    sid = _sim()
    for rodada in (1, 2, 3):   # com cansaço acumulado o XI muda de rodada a rodada
        pj = temporada_service.pre_jogo(sid)
        for lado in (pj["mandante"], pj["visitante"]):
            if lado["clube"] == pj["clube_usuario"]:
                previsto = {j["nome"] for j in lado["titulares"]}
                clube = lado["clube"]
        assert _xi_jogado(sid, rodada, clube) == previsto


def test_pre_jogo_nao_muda_o_resultado_da_rodada():
    # só leitura: com ou sem espiar o pré-jogo, a rodada sai igual
    a, b = _sim(seed=9), _sim(seed=9)
    temporada_service.pre_jogo(a)
    ra, rb = temporada_service.avancar(a), temporada_service.avancar(b)
    placar = lambda r: [(x["mandante"], x["gols_mandante"], x["gols_visitante"]) for x in r["resultados"]]
    assert placar(ra) == placar(rb)


def test_pre_jogo_de_temporada_concluida_levanta():
    sid = simulacao_service.salvar_temporada(seed=3, clube_usuario=_clube_do_ranking(1))
    with pytest.raises(TemporadaConcluida):
        temporada_service.pre_jogo(sid)


def test_pre_jogo_de_simulacao_inexistente_e_none():
    assert temporada_service.pre_jogo(999_999) is None
