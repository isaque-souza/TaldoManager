"""Calendário (v2.0, passo 2): as datas da temporada, no modelo europeu.

A temporada 1 é a 2026/27. Ela começa com a pré-temporada
(`SEMANAS_PRE_TEMPORADA` semanas sem jogo, com a janela aberta); a rodada 1
é no primeiro sábado a partir de 8 de agosto, e a liga joga um fim de semana
por rodada. Antes da rodada `RODADA_DA_PAUSA` vem a pausa do meio da
temporada (`SEMANAS_PAUSA` semanas a mais sem jogo, a janela do meio). A
fase da copa é na quarta depois da rodada dela (`app.domain.copa.DATAS`).

O motor e as finanças continuam contando rodadas: o calendário só dá uma
data a cada uma e deixa os dias passarem entre elas. Quando o clube do
técnico está na fase da copa, ela espera a quarta (`na_copa`): o próximo
jogo é o dela, não o da rodada `rodada`. Fora dela, a fase é jogada junto
com a rodada do fim de semana e só leva a data da quarta.

Tudo aqui é determinístico (só `datetime.date`): nada de `random`.
"""

from datetime import date, timedelta

ANO_DA_TEMPORADA_1 = 2026
DIA_DA_RODADA_1 = (8, 8)          # (mês, dia): o primeiro sábado a partir dele
SABADO = 5                        # date.weekday()
SEMANAS_PRE_TEMPORADA = 4
SEMANAS_PAUSA = 2
RODADA_DA_PAUSA = 20              # a primeira rodada depois da pausa
DIAS_ATE_A_COPA = 4               # sábado → quarta

_MESES = ("jan", "fev", "mar", "abr", "mai", "jun",
          "jul", "ago", "set", "out", "nov", "dez")
_SEMANA = ("seg", "ter", "qua", "qui", "sex", "sáb", "dom")


def ano_inicial(temporada):
    """O ano em que a temporada começa (a 1 é a 2026/27)."""
    return ANO_DA_TEMPORADA_1 + (temporada or 1) - 1


def nome_da_temporada(temporada):
    ano = ano_inicial(temporada)
    return f"{ano}/{str(ano + 1)[-2:]}"


def _rodada_1(temporada):
    mes, dia = DIA_DA_RODADA_1
    inicio = date(ano_inicial(temporada), mes, dia)
    return inicio + timedelta(days=(SABADO - inicio.weekday()) % 7)


def data_da_rodada(temporada, rodada):
    """O sábado da rodada (1 em diante)."""
    semanas = rodada - 1
    if rodada >= RODADA_DA_PAUSA:
        semanas += SEMANAS_PAUSA
    return _rodada_1(temporada) + timedelta(weeks=semanas)


def inicio(temporada):
    """O primeiro dia da pré-temporada."""
    return _rodada_1(temporada) - timedelta(weeks=SEMANAS_PRE_TEMPORADA)


def data_da_copa(temporada, rodada):
    """A quarta depois da rodada (a fase da copa jogada com ela)."""
    return data_da_rodada(temporada, rodada) + timedelta(days=DIAS_ATE_A_COPA)


def data_do_jogo(temporada, rodada, na_copa=False):
    """O dia do próximo jogo do técnico: o sábado da rodada `rodada` ou,
    com a copa esperando (`na_copa`), a quarta depois da rodada anterior."""
    if na_copa:
        return data_da_copa(temporada, rodada - 1)
    return data_da_rodada(temporada, rodada)


def data_atual(temporada, rodada_atual, salva=None):
    """O dia em que o save está. `salva` é a data gravada (ISO); saves de
    antes do calendário não têm e ficam no dia da próxima rodada."""
    if salva:
        return date.fromisoformat(salva)
    return data_da_rodada(temporada, rodada_atual or 1)


def dias_ate_o_jogo(hoje, temporada, rodada, na_copa=False):
    return (data_do_jogo(temporada, rodada, na_copa) - hoje).days


def avancar_um_dia(hoje, temporada, rodada, na_copa=False):
    """O dia seguinte — mas não passa do dia do jogo: ele precisa ser
    jogado antes."""
    return min(hoje + timedelta(days=1), data_do_jogo(temporada, rodada, na_copa))


def periodo(hoje, temporada, rodada, na_copa=False):
    """Em que parte da temporada o dia está: "pre_temporada", "pausa"
    (a do meio), "dia_de_jogo" ou "temporada"."""
    if hoje >= data_do_jogo(temporada, rodada, na_copa):
        return "dia_de_jogo"
    if na_copa:
        return "temporada"
    if rodada == 1:
        return "pre_temporada"
    if rodada == RODADA_DA_PAUSA and hoje > data_da_rodada(temporada, rodada - 1) + timedelta(
        weeks=1
    ):
        return "pausa"
    return "temporada"


def formatar(dia, com_semana=True):
    """"sáb, 8 ago 2026" (ou "8 ago 2026")."""
    texto = f"{dia.day} {_MESES[dia.month - 1]} {dia.year}"
    return f"{_SEMANA[dia.weekday()]}, {texto}" if com_semana else texto
