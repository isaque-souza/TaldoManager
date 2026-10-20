"""O contrato de quem chega (v1.7): a etapa 2 da negociação."""

from types import SimpleNamespace

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


def _Interesse(fator, nivel="aberto", bloqueio=None):
    return SimpleNamespace(fator=fator, nivel=nivel, bloqueio=bloqueio)


def _reforco(salario=None):
    return Jogador("Reforço", 25, "Atacante", 80, salario=salario)


def test_mudar_de_clube_custa_10_por_cento_e_livre_nao():
    forte, outro = _clube("A", 85), _clube("B", 85)
    j = _reforco(salario=1)
    livre = contrato.salario_pedido_chegada(j, forte, None, "3x")
    mudanca = contrato.salario_pedido_chegada(j, forte, outro, "3x")
    assert mudanca == round(livre * contrato.FATOR_MUDANCA / 1_000) * 1_000


def test_o_interesse_mexe_no_salario_pedido():
    a, b = _clube("A", 85), _clube("B", 85)
    j = _reforco(salario=1)
    neutro = contrato.salario_pedido_chegada(j, a, b, "3x")
    animado = contrato.salario_pedido_chegada(j, a, b, "3x", interesse=_Interesse(0.85))
    sem_vontade = contrato.salario_pedido_chegada(j, a, b, "3x", interesse=_Interesse(1.4))
    assert animado < neutro < sem_vontade


def test_nao_vem_nem_avalia_o_contrato():
    a, b = _clube("A", 85), _clube("B", 85)
    with pytest.raises(contrato.ContratoInvalido, match="rival"):
        contrato.avaliar_chegada(
            _reforco(), a, b, 10**9, 2, "3x", papeis.ROTACAO,
            _Interesse(1.0, "nao_vem", "Ídolo do B: não joga no rival"),
        )


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


def test_sugestao_parte_do_mercado_com_a_mudanca_e_nao_revela_o_resto():
    a, b = _clube("A", 70), _clube("B", 85)
    j = _reforco(salario=1)
    sugestao = contrato.salario_sugerido_chegada(j, a, b)
    ref = j.salario_referencia()
    assert sugestao == round(ref * contrato.FATOR_TITULAR * contrato.FATOR_MUDANCA / 1_000) * 1_000
    # o pedido real (craque no clube A) fica acima
    assert contrato.salario_pedido_chegada(j, a, b, "3x") > sugestao
