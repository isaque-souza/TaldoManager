"""Pré-jogo (v1.1): as escalações que o motor vai usar, antes do apito."""

import pytest

from types import SimpleNamespace as N

from app.services import (
    escalacao_service, pos_jogo_service, pre_jogo_service, simulacao_service, temporada_service,
)
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


# ---------------------------------------------------------------------------
# contexto do jogo (v2.3): forma, desfalques, estádio e público
# ---------------------------------------------------------------------------

def _contextos(pj):
    meu = pj["contexto_mandante"] if pj["mando"] == "casa" else pj["contexto_visitante"]
    rival = pj["contexto_visitante"] if meu is pj["contexto_mandante"] else pj["contexto_mandante"]
    return meu, rival


def test_na_primeira_rodada_nao_ha_forma_nem_posicao():
    pj = temporada_service.pre_jogo(_sim())
    meu, rival = _contextos(pj)

    assert meu["clube"] == pj["clube_usuario"] and rival["clube"] == pj["adversario"]
    assert meu["forma"] == [] and rival["forma"] == []
    assert meu["posicao"] is None


def test_forma_e_a_dos_jogos_gravados():
    sid = _sim()
    jogados = []
    for _ in range(7):
        res = temporada_service.avancar(sid)
        jogados.append(res["rodada_jogada"])
    pj = temporada_service.pre_jogo(sid)
    meu, rival = _contextos(pj)

    assert len(meu["forma"]) == 5
    assert [j["rodada"] for j in meu["forma"]] == sorted(j["rodada"] for j in meu["forma"])
    for j in meu["forma"]:
        assert j["resultado"] == (
            "V" if j["gols_pro"] > j["gols_contra"]
            else "D" if j["gols_pro"] < j["gols_contra"] else "E"
        )
    assert meu["posicao"] is not None and 1 <= meu["posicao"] <= meu["total_clubes"]
    assert len(rival["forma"]) == 5


def test_estadio_preve_o_publico_que_o_jogo_tem():
    sid = _sim()
    pj = temporada_service.pre_jogo(sid)
    est = pj["estadio"]
    assert est["clube"] == pj["mandante"]["clube"]
    assert 0 < est["publico_previsto"] <= est["capacidade"]

    temporada_service.avancar(sid)
    rel = pos_jogo_service.ver(sid)
    assert rel["publico"] == est["publico_previsto"]


def test_desfalques_trazem_lesionados_e_suspensos():
    def jog(nome, overall, lesao=0, susp=0):
        return N(nome=nome, numero=9, posicao="ATA", funcao="CA", overall=overall,
                 lesionado=lesao > 0, rodadas_lesao=lesao,
                 suspenso=susp > 0, jogos_suspensao=susp)

    clube = N(jogadores=[jog("A", 70, lesao=3), jog("B", 80, susp=1), jog("C", 90)])
    fora = pre_jogo_service.desfalques(clube)
    assert [(d["nome"], d["motivo"], d["jogos"]) for d in fora] == [
        ("B", "suspensao", 1), ("A", "lesao", 3),
    ]


def test_desfalque_nao_aparece_no_xi():
    sid = _sim()
    for _ in range(12):
        temporada_service.avancar(sid)
        pj = temporada_service.pre_jogo(sid)
        if pj["adversario"] is None:
            continue
        for ctx, esc in ((pj["contexto_mandante"], pj["mandante"]),
                         (pj["contexto_visitante"], pj["visitante"])):
            fora = {d["nome"] for d in ctx["desfalques"]}
            em_campo = {j["nome"] for j in esc["titulares"] + esc["banco"]}
            assert not fora & em_campo


def test_contexto_nao_muda_o_resultado_da_rodada_adiante():
    a, b = _sim(seed=9), _sim(seed=9)
    for _ in range(5):
        temporada_service.avancar(a)
        temporada_service.avancar(b)
    temporada_service.pre_jogo(a)
    ra, rb = temporada_service.avancar(a), temporada_service.avancar(b)
    placar = lambda r: [(x["mandante"], x["gols_mandante"], x["gols_visitante"]) for x in r["resultados"]]
    assert placar(ra) == placar(rb)


def test_jogo_da_copa_tem_contexto_e_entra_na_forma(cargo_garantido):
    from scripts.data_loader import TODAS_AS_LIGAS
    sid = temporada_service.iniciar(seed=6, clube_usuario="Arsenal", ligas=TODAS_AS_LIGAS)
    for _ in range(8):
        temporada_service.avancar(sid)

    pj = temporada_service.pre_jogo(sid)
    assert pj["copa"]["fase"] == "oitavas"
    meu, rival = _contextos(pj)
    # o rival da copa pode ser da outra liga: posição e total são os da liga dele
    assert 1 <= rival["posicao"] <= rival["total_clubes"]
    assert all(j["competicao"] == "liga" for j in meu["forma"])
    previsto = pj["estadio"]["publico_previsto"]

    res = temporada_service.avancar(sid)
    jogo = next(j for j in res["copa"]["jogos"] if "Arsenal" in (j["mandante"], j["visitante"]))
    assert jogo["publico"] == previsto

    depois = temporada_service.pre_jogo(sid)   # rodada 9 da liga
    assert depois["copa"] is None
    ultimo = _contextos(depois)[0]["forma"][-1]
    assert ultimo["competicao"] == "copa" and ultimo["fase"] == pj["copa"]["nome"]
    assert bool(ultimo["penaltis"]) == (jogo["gols_mandante"] == jogo["gols_visitante"])
    if ultimo["penaltis"]:
        assert ultimo["penaltis"]["classificou"] == (jogo["vencedor"] == "Arsenal")
