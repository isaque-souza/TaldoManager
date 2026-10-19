"""O contrato de quem chega (v1.7): a etapa 2 da negociação."""

import pytest

from app.domain import contrato, papeis
from app.domain.clube import Clube
from app.domain.jogador import Jogador

_POSICOES = ["Goleiro"] * 3 + ["Defesa"] * 7 + ["Meio-Campo"] * 7 + ["Atacante"] * 6


def _clube(nome, overall):
    clube = Clube(nome, "Brasil", 50_000_000)
    for i, pos in enumerate(_POSICOES):
        clube.contratar_jogador(Jogador(f"{nome} {i}", 25, pos, overall))
    return clube


def _reforco(salario=None):
    return Jogador("Reforço", 25, "Atacante", 80, salario=salario)


def test_mudar_de_clube_custa_10_por_cento_e_livre_nao():
    forte, outro = _clube("A", 85), _clube("B", 85)
    j = _reforco(salario=1)
    livre = contrato.salario_pedido_chegada(j, forte, None, "3x")
    mudanca = contrato.salario_pedido_chegada(j, forte, outro, "3x")
    assert mudanca == round(livre * contrato.FATOR_MUDANCA / 1_000) * 1_000


def test_descer_para_clube_mais_fraco_custa_mais():
    forte, fraco = _clube("A", 85), _clube("B", 70)
    j = _reforco(salario=1)
    subir = contrato.salario_pedido_chegada(j, forte, fraco, "3x")
    descer = contrato.salario_pedido_chegada(j, fraco, forte, "3x")
    assert contrato.clube_mais_fraco(fraco, forte)
    assert not contrato.clube_mais_fraco(forte, fraco)
    # no fraco ele ainda seria craque (pede mais por isso também)
    assert descer > subir * contrato.FATOR_PRESTIGIO


def test_nunca_aceita_ganhar_menos_do_que_ja_ganha():
    a, b = _clube("A", 85), _clube("B", 85)
    j = _reforco(salario=50_000_000)
    assert contrato.salario_pedido_chegada(j, a, b, "3x") == 50_000_000


def test_papel_esperado_no_clube_novo():
    fraco, forte = _clube("A", 70), _clube("B", 90)
    j = _reforco()
    assert contrato.papel_esperado(fraco, j) == papeis.TITULAR
    assert contrato.papel_esperado(forte, j) == papeis.RESERVA
    jovem = Jogador("Jovem", 19, "Atacante", 75, potencial=90)
    assert contrato.papel_esperado(forte, jovem) == papeis.PROMESSA


def test_prometer_mais_que_o_esperado_baixa_o_pedido():
    forte, outro = _clube("A", 90), _clube("B", 90)
    j = _reforco(salario=1)
    esperado = contrato.salario_pedido_chegada(j, forte, outro, "3x")   # reserva
    titular = contrato.salario_pedido_chegada(j, forte, outro, "3x", papeis.TITULAR)
    assert titular < esperado


def test_avaliar_chegada_aceita_contrapropoe_ou_recusa():
    a, b = _clube("A", 85), _clube("B", 85)
    j = _reforco(salario=1)
    pedido = contrato.salario_pedido_chegada(j, a, b, "3x", papeis.ROTACAO)
    sim = contrato.avaliar_chegada(j, a, b, pedido, 2, "3x", papeis.ROTACAO)
    quase = contrato.avaliar_chegada(j, a, b, int(pedido * 0.95), 2, "3x", papeis.ROTACAO)
    nao = contrato.avaliar_chegada(j, a, b, pedido // 2, 2, "3x", papeis.ROTACAO)
    assert (sim.tipo, quase.tipo, nao.tipo) == ("aceita", "contraproposta", "recusada")
    assert quase.valor == pedido
    with pytest.raises(contrato.ContratoInvalido):
        contrato.avaliar_chegada(j, a, b, pedido, 9, "3x", papeis.ROTACAO)
