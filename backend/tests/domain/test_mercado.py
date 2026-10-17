"""Regras do mercado de transferências (v0.7)."""

import pytest

from app.domain import mercado
from app.domain.clube import Clube
from app.domain.jogador import Jogador
from app.domain.mercado import TransferenciaInvalida

_POSICOES = ["Goleiro"] * 2 + ["Defesa"] * 6 + ["Meio-Campo"] * 5 + ["Atacante"] * 5


def _clube(nome, dinheiro=50_000_000, n=18):
    clube = Clube(nome, "Brasil", dinheiro)
    for i, pos in enumerate(_POSICOES[:n]):
        clube.contratar_jogador(Jogador(f"{nome} {i}", 25, pos, 75))
    return clube


def _atacante(clube):
    return next(j for j in clube.jogadores if j.posicao == "Atacante")


def test_janela_abre_na_pre_temporada_e_na_virada_do_turno():
    assert mercado.janela_aberta(1)
    assert mercado.janela_aberta(20)
    assert not mercado.janela_aberta(2)
    assert not mercado.janela_aberta(38)


def test_transferir_move_o_jogador_e_o_dinheiro():
    vendedor, comprador = _clube("A"), _clube("B")
    jogador = _atacante(vendedor)

    mercado.transferir(jogador, vendedor, comprador, 2_000_000)

    assert jogador not in vendedor.jogadores
    assert jogador in comprador.jogadores
    assert vendedor.dinheiro == 52_000_000 and vendedor.receita_vendas == 2_000_000
    assert comprador.dinheiro == 48_000_000 and comprador.despesa_compras == 2_000_000


def test_jogador_vendido_sai_do_xi_preferido():
    vendedor, comprador = _clube("A"), _clube("B")
    jogador = _atacante(vendedor)
    vendedor.xi_preferido = {jogador}
    mercado.transferir(jogador, vendedor, comprador, 1)
    assert jogador not in vendedor.xi_preferido


def test_sem_caixa_nao_compra():
    vendedor, comprador = _clube("A"), _clube("B", dinheiro=100)
    with pytest.raises(TransferenciaInvalida, match="caixa"):
        mercado.transferir(_atacante(vendedor), vendedor, comprador, 1_000)


def test_vendedor_nao_fica_abaixo_do_elenco_minimo():
    vendedor, comprador = _clube("A", n=mercado.ELENCO_MIN), _clube("B")
    with pytest.raises(TransferenciaInvalida, match="menos de"):
        mercado.transferir(vendedor.jogadores[-1], vendedor, comprador, 1)


def test_comprador_nao_passa_do_elenco_maximo():
    vendedor, comprador = _clube("A"), _clube("B")
    for i in range(mercado.ELENCO_MAX - len(comprador.jogadores)):
        comprador.contratar_jogador(Jogador(f"Extra {i}", 25, "Defesa", 70))
    with pytest.raises(TransferenciaInvalida, match="já tem"):
        mercado.transferir(_atacante(vendedor), vendedor, comprador, 1)


def test_nao_vende_o_penultimo_goleiro():
    vendedor, comprador = _clube("A"), _clube("B")
    goleiro = vendedor.jogadores[0]
    with pytest.raises(TransferenciaInvalida, match="goleiros"):
        mercado.transferir(goleiro, vendedor, comprador, 1)


def test_jogador_de_outro_clube_nao_pode_ser_vendido():
    a, b = _clube("A"), _clube("B")
    with pytest.raises(TransferenciaInvalida):
        mercado.transferir(_atacante(b), a, b, 1)


def test_escalacao_improvisa_quando_falta_posicao():
    # só 3 defensores para um 4-3-3: o XI tem que fechar 11 mesmo assim
    clube = _clube("A")
    for j in [j for j in clube.jogadores if j.posicao == "Defesa"][:3]:
        clube.jogadores.remove(j)
    clube.formacao = "4-3-3"
    clube.escalar_time()
    assert len(clube.titulares) == 11
    assert sum(1 for j in clube.titulares if j.posicao == "Goleiro") == 1


# --- negociação ------------------------------------------------------------

def _negocio(contrato=3, multa=None, rivais=False):
    """vendedor com um atacante RESERVA (overall abaixo dos titulares)."""
    vendedor, comprador = _clube("A"), _clube("B")
    reserva = Jogador("Reserva", 25, "Atacante", 70,
                      contrato_anos=contrato, multa_rescisoria=multa)
    vendedor.contratar_jogador(reserva)
    if rivais:
        vendedor.rivais = {"B"}
    return reserva, vendedor, comprador


def test_preco_de_reserva_comum_e_o_valor_de_mercado():
    j, v, c = _negocio()
    assert mercado.preco_pedido(j, v, c) == j.valor_mercado()


def test_titular_e_craque_custam_mais():
    v, c = _clube("A"), _clube("B")
    craque = Jogador("Craque", 25, "Atacante", 90)
    v.contratar_jogador(craque)
    titular = next(j for j in v.jogadores if j.posicao == "Atacante" and j is not craque)
    assert mercado.preco_pedido(craque, v, c) == round(craque.valor_mercado() * mercado.FATOR_CRAQUE / 10_000) * 10_000
    assert mercado.preco_pedido(titular, v, c) > titular.valor_mercado()


def test_contrato_acabando_barateia_e_longo_encarece():
    curto, v, c = _negocio(contrato=1)
    assert mercado.preco_pedido(curto, v, c) < curto.valor_mercado()
    longo, v, c = _negocio(contrato=5)
    assert mercado.preco_pedido(longo, v, c) > longo.valor_mercado()


def test_clube_endividado_vende_mais_barato():
    j, v, c = _negocio()
    v.dinheiro = -1
    assert mercado.preco_pedido(j, v, c) < j.valor_mercado()


def test_rival_paga_mais_caro():
    normal, v1, c1 = _negocio()
    rival, v2, c2 = _negocio(rivais=True)
    assert mercado.preco_pedido(rival, v2, c2) > mercado.preco_pedido(normal, v1, c1)


def test_resposta_aceita_contraproposta_ou_recusa():
    j, v, c = _negocio()
    pedido = mercado.preco_pedido(j, v, c)
    assert mercado.avaliar_proposta(j, v, c, pedido).tipo == "aceita"
    contra = mercado.avaliar_proposta(j, v, c, int(pedido * 0.9))
    assert contra.tipo == "contraproposta" and contra.valor == pedido
    assert mercado.avaliar_proposta(j, v, c, int(pedido * 0.5)).tipo == "recusada"


def test_multa_paga_o_clube_nao_pode_recusar_nem_rival():
    j, v, c = _negocio(multa=500_000, rivais=True)
    r = mercado.avaliar_proposta(j, v, c, 600_000)
    assert r.tipo == "multa" and r.fechou
    assert r.valor == 500_000   # paga a multa, não o que ofereceu a mais


def test_preco_pedido_nunca_passa_da_multa():
    j, v, c = _negocio(multa=20_000, rivais=True)
    assert mercado.preco_pedido(j, v, c) == 20_000


def test_seria_titular_compara_com_o_elenco_do_comprador():
    c = _clube("B")   # atacantes de 75 num 4-3-3
    assert mercado.seria_titular(c, Jogador("Bom", 25, "Atacante", 80))
    assert not mercado.seria_titular(c, Jogador("Fraco", 25, "Atacante", 60))


def test_ofertas_pagam_mais_quando_seria_titular_e_marcam_rival():
    vendedor = _clube("A")
    vendedor.rivais = {"Rival"}
    bom = Jogador("Bom", 25, "Atacante", 80)
    vendedor.contratar_jogador(bom)
    fraco_no_ataque = _clube("Fraco")
    for j in fraco_no_ataque.jogadores:
        if j.posicao == "Atacante":
            j.overall = 60
    forte_no_ataque = _clube("Forte")
    for j in forte_no_ataque.jogadores:
        if j.posicao == "Atacante":
            j.overall = 90
    rival = _clube("Rival")
    pobre = _clube("Pobre", dinheiro=10)

    lista = mercado.ofertas(bom, vendedor, [vendedor, fraco_no_ataque, forte_no_ataque, rival, pobre])
    por_clube = {o.clube.nome: o for o in lista}

    assert "Pobre" not in por_clube                   # não pode pagar
    assert por_clube["Fraco"].titular and not por_clube["Forte"].titular
    assert por_clube["Fraco"].valor > por_clube["Forte"].valor
    assert por_clube["Rival"].rival
    assert lista[0].valor >= lista[-1].valor          # maior primeiro
