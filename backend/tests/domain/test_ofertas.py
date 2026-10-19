"""Ofertas da CPU pelos jogadores do técnico (v1.7)."""

import random

import pytest

from app.domain import ofertas
from app.domain.clube import Clube
from app.domain.jogador import Jogador
from app.domain.mercado import TransferenciaInvalida

_POSICOES = ["Goleiro"] * 2 + ["Defesa"] * 6 + ["Meio-Campo"] * 5 + ["Atacante"] * 5


def _clube(nome, dinheiro=500_000_000, overall=75):
    clube = Clube(nome, "Brasil", dinheiro)
    for i, pos in enumerate(_POSICOES):
        clube.contratar_jogador(Jogador(f"{nome} {i}", 25, pos, overall))
    return clube


def _liga(n=8):
    return [_clube(f"C{i}") for i in range(n)]


def test_a_venda_recebe_ate_tres_ofertas_abaixo_do_valor_e_da_multa():
    meu, *outros = _liga()
    craque = Jogador("Craque", 25, "Atacante", 85, multa_rescisoria=50_000_000)
    meu.contratar_jogador(craque)

    contagens = set()
    for n in range(40):
        lista = ofertas.para_venda(craque, meu, [meu, *outros], random.Random(n))
        contagens.add(len(lista))
        assert len(lista) <= ofertas.MAX_OFERTAS
        assert [o.valor for o in lista] == sorted((o.valor for o in lista), reverse=True)
        for o in lista:
            assert o.clube is not meu and not o.espontanea
            assert o.valor < craque.multa_rescisoria
            # titular lá (1,15) × variação máxima (1,10) × desconto (0,9)
            assert o.valor <= craque.valor_mercado() * 1.15 * 1.10 * 0.9 + 10_000
            assert o.valor <= o.teto
    assert 0 in contagens and max(contagens) == ofertas.MAX_OFERTAS


def test_o_mesmo_sorteio_da_as_mesmas_ofertas():
    meu, *outros = _liga()
    j = meu.jogadores[-1]
    a = ofertas.para_venda(j, meu, [meu, *outros], ofertas.semente(1, 20, j.nome))
    b = ofertas.para_venda(j, meu, [meu, *outros], ofertas.semente(1, 20, j.nome))
    assert [(o.clube.nome, o.valor) for o in a] == [(o.clube.nome, o.valor) for o in b]


def test_quem_nao_pode_pagar_nao_oferece_e_saida_bloqueada_nao_recebe():
    meu = _clube("Meu")
    pobres = [_clube(f"P{i}", dinheiro=10) for i in range(5)]
    j = meu.jogadores[-1]
    for n in range(20):
        assert ofertas.para_venda(j, meu, [meu, *pobres], random.Random(n)) == []

    goleiro = meu.jogadores[0]   # só 2 goleiros: não pode sair
    ricos = _liga()
    assert ofertas.para_venda(goleiro, meu, [meu, *ricos], random.Random(1)) == []


def test_assedio_mira_um_dos_melhores_e_vem_de_clube_mais_forte():
    meu = _clube("Meu", overall=70)
    craques = [Jogador(f"Craque {i}", 25, "Meio-Campo", 88 - i) for i in range(4)]
    for c in craques:
        meu.contratar_jogador(c)
    craques[0].a_venda = True          # quem está à venda não é assédio
    fortes = [_clube(f"F{i}", overall=85) for i in range(3)]
    fracos = [_clube(f"f{i}", overall=60) for i in range(3)]

    vistos = 0
    for n in range(60):
        achado = ofertas.assedio(meu, [meu, *fortes, *fracos], random.Random(n))
        if achado is None:
            continue
        vistos += 1
        jogador, oferta = achado
        assert jogador in craques[1:4]
        assert oferta.clube in fortes and oferta.espontanea
        assert jogador.valor_mercado() * 1.2 - 10_000 <= oferta.valor
        assert oferta.valor <= jogador.valor_mercado() * 1.5 + 10_000
    # ~50% das janelas
    assert 15 < vistos < 45


def test_o_mais_forte_e_assediado_pelos_que_vem_logo_abaixo():
    meu = _clube("Meu", overall=90)
    abaixo = [_clube(f"A{i}", overall=85 - i) for i in range(3)]
    fracos = [_clube(f"f{i}", overall=60) for i in range(3)]
    clubes = {
        achado[1].clube.nome
        for n in range(60)
        if (achado := ofertas.assedio(meu, [meu, *fracos, *abaixo], random.Random(n)))
    }
    assert clubes and clubes <= {c.nome for c in abaixo}


def test_contraproposta_aceita_ate_o_teto():
    assert ofertas.responder_contraproposta(1_000_000, 1_150_000, 1_150_000) == "aceita"
    assert ofertas.responder_contraproposta(1_000_000, 1_150_000, 1_160_000) == "retirada"
    with pytest.raises(TransferenciaInvalida, match="mais do que a oferta"):
        ofertas.responder_contraproposta(1_000_000, 1_150_000, 1_000_000)
