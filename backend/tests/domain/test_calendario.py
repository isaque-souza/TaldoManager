"""Calendário (v2.0): as datas da temporada."""

from datetime import date, timedelta

from app.domain import calendario


def test_temporada_1_e_2026_27():
    assert calendario.nome_da_temporada(1) == "2026/27"
    assert calendario.nome_da_temporada(3) == "2028/29"


def test_rodadas_no_sabado_uma_por_semana():
    r1 = calendario.data_da_rodada(1, 1)
    assert r1.weekday() == calendario.SABADO
    assert date(2026, 8, 8) <= r1 < date(2026, 8, 15)
    assert calendario.data_da_rodada(1, 2) - r1 == timedelta(weeks=1)
    for rodada in range(1, 39):
        assert calendario.data_da_rodada(1, rodada).weekday() == calendario.SABADO


def test_pausa_do_meio_antes_da_rodada_20():
    r19 = calendario.data_da_rodada(1, 19)
    r20 = calendario.data_da_rodada(1, 20)
    assert r20 - r19 == timedelta(weeks=1 + calendario.SEMANAS_PAUSA)
    # a pausa cai na virada do ano e a temporada acaba em maio
    assert r19.month == 12 and r20.year == 2027
    assert calendario.data_da_rodada(1, 38).month == 5


def test_pre_temporada_de_4_semanas():
    assert calendario.data_da_rodada(1, 1) - calendario.inicio(1) == timedelta(weeks=4)
    assert calendario.inicio(2).year == 2027


def test_copa_na_quarta():
    assert calendario.data_da_copa(1, 8).weekday() == 2


def test_avancar_um_dia_nao_passa_do_jogo():
    jogo = calendario.data_da_rodada(1, 1)
    assert calendario.avancar_um_dia(jogo - timedelta(days=2), 1, 1) == jogo - timedelta(days=1)
    assert calendario.avancar_um_dia(jogo, 1, 1) == jogo


def test_data_atual_de_save_antigo_e_o_dia_do_jogo():
    assert calendario.data_atual(1, 5) == calendario.data_da_rodada(1, 5)
    assert calendario.data_atual(1, 5, "2026-09-01") == date(2026, 9, 1)


def test_periodos():
    inicio = calendario.inicio(1)
    assert calendario.periodo(inicio, 1, 1) == "pre_temporada"
    assert calendario.periodo(calendario.data_da_rodada(1, 1), 1, 1) == "dia_de_jogo"
    depois_r1 = calendario.data_da_rodada(1, 1) + timedelta(days=1)
    assert calendario.periodo(depois_r1, 1, 2) == "temporada"
    r19 = calendario.data_da_rodada(1, 19)
    assert calendario.periodo(r19 + timedelta(days=3), 1, 20) == "temporada"
    assert calendario.periodo(r19 + timedelta(days=10), 1, 20) == "pausa"


def test_formatar():
    assert calendario.formatar(date(2026, 8, 8)) == "sáb, 8 ago 2026"
    assert calendario.formatar(date(2027, 1, 2), com_semana=False) == "2 jan 2027"
