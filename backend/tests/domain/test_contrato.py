"""Regras de renovação de contrato (v0.7)."""

import pytest

from app.domain import contrato, mercado
from app.domain.clube import Clube
from app.domain.contrato import ContratoInvalido
from app.domain.jogador import Jogador

_POSICOES = ["Goleiro"] * 2 + ["Defesa"] * 6 + ["Meio-Campo"] * 5 + ["Atacante"] * 5


def _clube():
    clube = Clube("A", "Brasil", 10_000_000)
    for i, pos in enumerate(_POSICOES):
        clube.contratar_jogador(Jogador(f"A {i}", 25, pos, 75))
    return clube


def _reserva(clube, idade=25, contrato_anos=3):
    j = Jogador("Reserva", idade, "Atacante", 70, contrato_anos=contrato_anos)
    clube.contratar_jogador(j)
    return j


def test_reserva_com_multa_3x_pede_o_salario_de_referencia():
    clube = _clube()
    j = _reserva(clube)
    assert contrato.salario_pedido(j, clube, "3x") == j.salario_referencia()


def test_sem_multa_custa_mais_e_multa_barata_custa_menos():
    clube = _clube()
    j = _reserva(clube)
    base = contrato.salario_pedido(j, clube, "3x")
    assert contrato.salario_pedido(j, clube, "sem") > base
    assert contrato.salario_pedido(j, clube, "5x") > base
    assert contrato.salario_pedido(j, clube, "2x") < base


def test_craque_e_titular_pedem_mais():
    clube = _clube()
    craque = Jogador("Craque", 25, "Atacante", 90)
    clube.contratar_jogador(craque)
    titular = next(j for j in clube.jogadores if j.posicao == "Defesa")
    assert contrato.salario_pedido(craque, clube, "3x") > craque.salario_referencia() * 1.3
    assert contrato.salario_pedido(titular, clube, "3x") > titular.salario_referencia()


def test_ultimo_ano_de_contrato_pede_mais():
    clube = _clube()
    acabando = _reserva(clube, contrato_anos=1)
    assert contrato.salario_pedido(acabando, clube, "3x") > acabando.salario_referencia()


def test_veterano_renova_no_maximo_duas_temporadas():
    clube = _clube()
    veterano = _reserva(clube, idade=33)
    assert contrato.duracao_max(veterano) == contrato.DURACAO_MAX_VETERANO
    contrato.validar(veterano, 2, "3x")
    with pytest.raises(ContratoInvalido, match="1 a 2"):
        contrato.validar(veterano, 3, "3x")


def test_duracao_e_multa_invalidas():
    clube = _clube()
    j = _reserva(clube)
    with pytest.raises(ContratoInvalido):
        contrato.validar(j, 0, "3x")
    with pytest.raises(ContratoInvalido):
        contrato.validar(j, 6, "3x")
    with pytest.raises(ContratoInvalido):
        contrato.validar(j, 3, "10x")


def test_resposta_aceita_contraproposta_ou_recusa():
    clube = _clube()
    j = _reserva(clube)
    pedido = contrato.salario_pedido(j, clube, "3x")
    assert contrato.avaliar_renovacao(j, clube, pedido, 3, "3x").tipo == "aceita"
    contra = contrato.avaliar_renovacao(j, clube, int(pedido * 0.95), 3, "3x")
    assert contra.tipo == "contraproposta" and contra.valor == pedido
    assert contrato.avaliar_renovacao(j, clube, pedido // 2, 3, "3x").tipo == "recusada"


def test_renovar_aplica_o_contrato_novo():
    clube = _clube()
    j = _reserva(clube)
    contrato.renovar(j, anos=5, salario=99_000, opcao_multa="5x")
    assert j.contrato_anos == 5 and j.salario == 99_000
    assert j.multa_rescisoria == contrato.valor_multa(j, "5x")
    contrato.renovar(j, anos=2, salario=99_000, opcao_multa="sem")
    assert j.multa_rescisoria is None


def test_transferencia_assina_contrato_novo_com_o_comprador():
    vendedor, comprador = _clube(), Clube("B", "Brasil", 50_000_000)
    for i, pos in enumerate(_POSICOES):
        comprador.contratar_jogador(Jogador(f"B {i}", 25, pos, 75))
    j = Jogador("Vendido", 25, "Atacante", 80, contrato_anos=1,
                multa_rescisoria=1_000_000, salario=5_000)
    vendedor.contratar_jogador(j)
    mercado.transferir(j, vendedor, comprador, 2_000_000)
    assert j.contrato_anos == mercado.CONTRATO_PADRAO_ANOS
    assert j.salario == j.salario_referencia()
    assert j.multa_rescisoria is None
