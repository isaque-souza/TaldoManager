"""Relatório de contratação (v2.0): faixas e dificuldade."""

import pytest

from app.domain import relatorio, vontade
from app.domain.clube import Clube
from app.domain.jogador import Jogador
from app.domain.vontade import Interesse


def _interesse(nivel=vontade.ABERTO, bloqueio=None):
    return Interesse(pontos=1, nivel=nivel, fator=1.0, motivos=[], bloqueio=bloqueio)


@pytest.mark.parametrize("nivel", relatorio.DIAS)
def test_a_faixa_sempre_contem_o_valor(nivel):
    for i in range(200):
        valor = 300_000 + i * 731_377
        minimo, maximo = relatorio.faixa(valor, f"J{i}", nivel, "preco")
        assert minimo <= valor <= maximo


def test_a_faixa_estreita_com_o_nivel():
    larguras = []
    for nivel in relatorio.DIAS:
        minimo, maximo = relatorio.faixa(20_000_000, "Craque", nivel, "preco")
        larguras.append(maximo - minimo)
    assert larguras == sorted(larguras, reverse=True) and larguras[0] > larguras[-1]


def test_a_faixa_tem_dois_algarismos():
    minimo, maximo = relatorio.faixa(18_734_000, "J", 3, "preco")
    assert minimo % 1_000_000 == 0 and maximo % 1_000_000 == 0


def test_dias_e_limite_pelo_nivel():
    assert [relatorio.DIAS[n] for n in range(1, 6)] == [10, 8, 6, 4, 2]
    assert relatorio.limite(3) == 3


def test_dificuldade():
    d = relatorio.dificuldade
    assert d(_interesse(bloqueio="Ídolo do X: não joga no rival"), 1, 100) == relatorio.IMPOSSIVEL
    assert d(_interesse(), 200, 100) == relatorio.IMPOSSIVEL
    assert d(_interesse(), 10, 100, motivo_clube="Não vende") == relatorio.IMPOSSIVEL
    assert d(_interesse(vontade.RESISTENTE), 10, 100) == relatorio.DIFICIL
    assert d(_interesse(), 10, 100, rival=True) == relatorio.DIFICIL
    assert d(_interesse(), 60, 100) == relatorio.DIFICIL
    assert d(_interesse(vontade.QUER_VIR), 20, 100) == relatorio.FACIL
    assert d(_interesse(vontade.QUER_VIR), 40, 100) == relatorio.MEDIA
    assert d(_interesse(), 10, 100) == relatorio.MEDIA


def test_montar_livre():
    comprador = Clube("Casa", "Brasil", 50_000_000)
    j = Jogador("Livre", 27, "Atacante", 85)
    r = relatorio.montar(j, None, comprador, _interesse(vontade.QUER_VIR), 1_000_000, 800_000, 5)
    assert r["dificuldade"] == relatorio.FACIL
    assert r["chance_disputa"] == 50   # craque: 85+
    assert r["preco"][0] <= 1_000_000 <= r["preco"][1]
