from app.domain.historico import (
    hall_da_fama,
    lideres,
    pontos_de_lenda,
    resumo_temporada,
    titulos_por_clube,
    totais_por_jogador,
)


def _clube(nome, posicao):
    return {"nome": nome, "posicao_final": posicao}


def _jogador(nome, clube, gols=0, assistencias=0, partidas=30, overall=80,
             melhor_em_campo=0, nota_media=6.5, posicao="Atacante"):
    return {
        "nome": nome, "clube": clube, "posicao": posicao, "overall": overall,
        "gols": gols, "assistencias": assistencias, "partidas": partidas,
        "melhor_em_campo": melhor_em_campo, "nota_media": nota_media,
        "hat_tricks": 0,
    }


CLUBES = [_clube("B", 2), _clube("A", 1), _clube("C", 3)]


def test_resumo_da_temporada():
    jogadores = [
        _jogador("Goleador", "B", gols=20),
        _jogador("Craque", "A", gols=12, melhor_em_campo=9),
        _jogador("Reserva", "C"),
    ]
    r = resumo_temporada(CLUBES, jogadores, clube_usuario="C")

    assert (r["campeao"], r["vice"], r["posicao_usuario"]) == ("A", "B", 3)
    assert r["artilheiro"] == {"nome": "Goleador", "clube": "B", "valor": 20}
    assert r["mvp"] == {"nome": "Craque", "clube": "A", "valor": 9}


def test_temporada_sem_gols_nao_tem_artilheiro_nem_mvp():
    r = resumo_temporada(CLUBES, [_jogador("X", "A")])
    assert r["artilheiro"] is None and r["mvp"] is None
    assert r["posicao_usuario"] is None


def _carreira():
    """Duas temporadas: "Lenda" troca de clube (A → B) e é campeão nas duas; na
    temporada 2 o Coadjuvante é artilheiro e MVP."""
    t1 = [
        _jogador("Lenda", "A", gols=30, assistencias=5, overall=91,
                 melhor_em_campo=10),
        _jogador("Coadjuvante", "C", gols=3, assistencias=12),
    ]
    t2 = [
        _jogador("Lenda", "B", gols=22, partidas=28, overall=88,
                 melhor_em_campo=4),
        _jogador("Coadjuvante", "C", gols=25, assistencias=1,
                 melhor_em_campo=8),
    ]
    clubes2 = [_clube("B", 1), _clube("A", 2), _clube("C", 3)]
    return [
        {"temporada": 1, "jogadores": t1, "resumo": resumo_temporada(CLUBES, t1)},
        {"temporada": 2, "jogadores": t2, "resumo": resumo_temporada(clubes2, t2)},
    ]


def test_totais_somam_as_temporadas_mesmo_trocando_de_clube():
    lenda = totais_por_jogador(_carreira())["Lenda"]

    assert lenda["clube"] == "B"                 # o da última temporada
    assert (lenda["temporadas"], lenda["partidas"]) == (2, 58)
    assert (lenda["gols"], lenda["assistencias"]) == (52, 5)
    assert lenda["titulos"] == 2                 # campeão pelo A e pelo B
    assert (lenda["artilharias"], lenda["mvps"]) == (1, 1)
    assert lenda["pico_overall"] == 91


def test_reserva_que_nao_jogou_nao_conta_o_titulo():
    jogadores = [_jogador("Titular", "A", partidas=10),
                 _jogador("Reserva", "A", partidas=9)]
    totais = totais_por_jogador(
        [{"jogadores": jogadores, "resumo": resumo_temporada(CLUBES, jogadores)}]
    )
    assert (totais["Titular"]["titulos"], totais["Reserva"]["titulos"]) == (1, 0)


def test_titulos_por_clube():
    temporadas = _carreira()
    temporadas.append({"temporada": 3, "resumo": {"campeao": "B"}})
    titulos = titulos_por_clube([(t["temporada"], t["resumo"]) for t in temporadas])
    assert titulos == [
        {"clube": "B", "titulos": 2, "temporadas": [2, 3]},
        {"clube": "A", "titulos": 1, "temporadas": [1]},
    ]


def test_lideres_historicos():
    l = lideres(totais_por_jogador(_carreira()))
    assert [j["nome"] for j in l["gols"]] == ["Lenda", "Coadjuvante"]
    assert [j["nome"] for j in l["assistencias"]] == ["Coadjuvante", "Lenda"]
    assert [j["nome"] for j in l["premios"]] == ["Lenda", "Coadjuvante"]


def test_pontos_de_lenda_calculados_a_mao():
    total = {"titulos": 2, "artilharias": 2, "mvps": 1, "gols": 52,
             "pico_overall": 91}
    # 2×2 títulos + 3×3 prêmios + 52//25 gols + 2 do pico 90+
    assert pontos_de_lenda(total) == 4 + 9 + 2 + 2
    assert pontos_de_lenda({**total, "pico_overall": 89}) == 15


def _aposentou(nome, clube="B", idade=36, overall=85, ultima=2):
    return {"jogador": nome, "clube": clube, "idade": idade,
            "overall": overall, "ultima_temporada": ultima}


def test_hall_da_fama_so_tem_aposentados_com_pontos():
    totais = totais_por_jogador(_carreira())
    # Coadjuvante: 1 artilharia + 1 MVP = 6 pontos, mas não se aposentou
    assert hall_da_fama(totais, []) == []

    hall = hall_da_fama(totais, [_aposentou("Lenda")])
    assert [l["nome"] for l in hall] == ["Lenda"]
    # 2×2 títulos + 3×2 prêmios + 52//25 gols + 2 do pico 91
    assert hall[0]["pontos"] == 14
    assert hall[0]["motivo"] == "2× campeão · artilheiro 1× · MVP 1× · 52 gols · pico 91"
    assert (hall[0]["idade"], hall[0]["ultima_temporada"]) == (36, 2)


def test_aposentado_sem_feitos_fica_de_fora():
    totais = totais_por_jogador(_carreira())
    totais["Comum"] = {**totais["Lenda"], "nome": "Comum", "titulos": 0,
                       "artilharias": 0, "mvps": 0, "gols": 40,
                       "pico_overall": 84}
    # 40 gols = 1 ponto
    assert hall_da_fama(totais, [_aposentou("Comum")]) == []


def test_hall_ordenado_pelos_pontos():
    totais = totais_por_jogador(_carreira())
    hall = hall_da_fama(totais, [_aposentou("Coadjuvante", clube="C"),
                                 _aposentou("Lenda")])
    assert [(l["nome"], l["pontos"]) for l in hall] == [
        ("Lenda", 14), ("Coadjuvante", 7),   # 6 de prêmios + 28 gols
    ]


def test_motivo_no_singular():
    from app.domain.historico import motivo
    total = {"titulos": 1, "artilharias": 0, "mvps": 0, "gols": 1,
             "pico_overall": 90}
    assert motivo(total) == "1× campeão · 1 gol · pico 90"


# --- copa entre as ligas (v1.6) ---------------------------------------------

def test_copa_conta_titulo_de_jogador_e_ponto_de_lenda():
    from app.domain import historico as h

    resumo = {"campeao": "A", "campeoes": ["A", "P"], "campeao_copa": "P",
              "artilheiro": None, "mvp": None}
    jogadores = [
        {"nome": "titular", "posicao": "Ataque", "clube": "P", "partidas": 30,
         "gols": 0, "assistencias": 0, "overall": 80},
        {"nome": "reserva", "posicao": "Ataque", "clube": "P", "partidas": 3,
         "gols": 0, "assistencias": 0, "overall": 70},
    ]
    totais = h.totais_por_jogador([{"jogadores": jogadores, "resumo": resumo}])
    # campeão da outra liga também é campeão; e da copa
    assert totais["titular"]["titulos"] == 1 and totais["titular"]["copas"] == 1
    assert totais["reserva"]["titulos"] == 0 and totais["reserva"]["copas"] == 0
    assert h.pontos_de_lenda(totais["titular"]) == h.PONTOS_TITULO + h.PONTOS_COPA
    assert "copa 1×" in h.motivo(totais["titular"])
    assert h.titulos_por_clube([(1, resumo), (2, resumo)], "campeao_copa") == [
        {"clube": "P", "titulos": 2, "temporadas": [1, 2]}
    ]
