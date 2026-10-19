"""Copa entre as ligas (v1.6): a visão e as mensagens do técnico."""

from app.domain import caixa
from app.services import copa_service


def _jogo(m, v, gm, gv, vencedor, penaltis=None):
    return {"mandante": m, "visitante": v, "gols_mandante": gm, "gols_visitante": gv,
            "penaltis": penaltis, "vencedor": vencedor, "publico": 0, "gols": []}


DADOS = {
    "classificados": {"taldo": ["A", "B"], "premier": ["X", "Y"]},
    "fases": {
        "oitavas": [_jogo("A", "Y", 2, 0, "A"), _jogo("X", "B", 1, 1, "B", [3, 4])],
        "quartas": [_jogo("A", "B", 0, 1, "B")],
        "semi": [],
    },
}


def test_situacao_de_cada_clube():
    assert copa_service.situacao(DADOS, "Z")["estado"] == "fora"
    y = copa_service.situacao(DADOS, "Y")
    assert (y["estado"], y["fase"], y["jogo"]["adversario"]) == ("eliminado", "oitavas", "A")
    a = copa_service.situacao(DADOS, "A")
    assert (a["estado"], a["fase"], a["jogo"]["mando"]) == ("eliminado", "quartas", "casa")
    assert copa_service.situacao(DADOS, "B") == {"estado": "vivo", "fase": "semi", "jogo": None}

    campeao = {**DADOS, "fases": {**DADOS["fases"], "final": [_jogo("B", "K", 1, 0, "B")],
                                  "semi": [_jogo("B", "Q", 3, 0, "B")]}}
    assert copa_service.situacao(campeao, "B")["estado"] == "campeao"


def test_visao_lista_as_quatro_fases_e_a_proxima():
    v = copa_service.visao(DADOS, "B", {"A": "taldo", "B": "taldo", "X": "premier", "Y": "premier"})
    assert [f["jogada"] for f in v["fases"]] == [True, True, False, False]
    assert v["proxima"]["fase"] == "semi" and v["campeao"] is None
    assert v["fases"][0]["jogos"][0]["liga_visitante"] == "premier"


def test_mensagem_conta_os_penaltis_do_lado_do_tecnico():
    jogo = DADOS["fases"]["oitavas"][1]
    m = caixa.copa_resultado("oitavas", jogo, "B", 500_000, ("quartas", 17, "A", "fora"))
    assert "1 a 1 (4 a 3 nos pênaltis)" in m["corpo"]
    assert "depois da rodada 17" in m["corpo"] and "fora" in m["corpo"]
    perdeu = caixa.copa_resultado("oitavas", jogo, "X", 500_000)
    assert perdeu["assunto"] == "Fora da copa" and "3 a 4 nos pênaltis" in perdeu["corpo"]
