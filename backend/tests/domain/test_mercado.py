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


def test_melhor_comprador_e_o_mais_rico_que_pode_pagar():
    vendedor = _clube("A")
    pobre, medio, rico = _clube("P", 10), _clube("M", 5_000_000), _clube("R", 9_000_000)
    for c in (rico,):   # rico com elenco lotado não pode
        for i in range(mercado.ELENCO_MAX - len(c.jogadores)):
            c.contratar_jogador(Jogador(f"Extra {i}", 25, "Defesa", 70))
    jogador = _atacante(vendedor)
    escolhido = mercado.melhor_comprador(
        jogador, [vendedor, pobre, medio, rico], 1_000_000, excluir=[vendedor]
    )
    assert escolhido is medio


def test_ninguem_pode_pagar():
    vendedor = _clube("A")
    assert mercado.melhor_comprador(
        _atacante(vendedor), [vendedor, _clube("P", 10)], 1_000, excluir=[vendedor]
    ) is None


def test_escalacao_improvisa_quando_falta_posicao():
    # só 3 defensores para um 4-3-3: o XI tem que fechar 11 mesmo assim
    clube = _clube("A")
    for j in [j for j in clube.jogadores if j.posicao == "Defesa"][:3]:
        clube.jogadores.remove(j)
    clube.formacao = "4-3-3"
    clube.escalar_time()
    assert len(clube.titulares) == 11
    assert sum(1 for j in clube.titulares if j.posicao == "Goleiro") == 1
