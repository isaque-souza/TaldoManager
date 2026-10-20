"""Clubes da CPU negociam entre si (v1.7): regras puras."""

import random

from app.domain import mercado_cpu, vontade
from app.domain.clube import Clube
from app.domain.jogador import Jogador

_POSICOES = ["Goleiro"] * 2 + ["Defesa"] * 6 + ["Meio-Campo"] * 5 + ["Atacante"] * 5


def _clube(nome, overall=75, dinheiro=500_000_000):
    clube = Clube(nome, "Brasil", dinheiro)
    for i, pos in enumerate(_POSICOES):
        # overalls variados: com todos iguais, todos seriam o craque
        clube.contratar_jogador(Jogador(f"{nome} {i}", 25, pos, overall + i % 3))
    return clube


def _sempre_compra(monkeypatch):
    monkeypatch.setattr(mercado_cpu, "CHANCE_COMPRA", 1.0)
    # a vontade do jogador (v1.9) tem testes próprios, no fim do arquivo
    monkeypatch.setattr(mercado_cpu, "CHANCE_RECUSA", 0.0)


def test_o_fraco_compra_o_reforco_do_forte(monkeypatch):
    _sempre_compra(monkeypatch)
    fraco, forte = _clube("Fraco", 60), _clube("Forte", 80)
    negocios = mercado_cpu.negociar([fraco, forte], "Técnico", random.Random(1))
    assert negocios and all(n.comprador is fraco and n.vendedor is forte for n in negocios)
    n = negocios[0]
    assert n.jogador in fraco.jogadores and n.jogador not in forte.jogadores
    assert n.jogador.overall >= mercado_cpu.pior_titular(fraco, n.jogador.posicao)


def test_o_clube_do_tecnico_fica_de_fora(monkeypatch):
    _sempre_compra(monkeypatch)
    fraco, tecnico = _clube("Fraco", 60), _clube("Técnico", 80)
    assert mercado_cpu.negociar([fraco, tecnico], "Técnico", random.Random(1)) == []


def test_nao_vende_craque_nem_para_o_rival_nem_sem_caixa(monkeypatch):
    _sempre_compra(monkeypatch)
    fraco, forte = _clube("Fraco", 60), _clube("Forte", 75)
    craque = Jogador("Craque", 25, "Atacante", 95)
    forte.contratar_jogador(craque)
    negocios = mercado_cpu.negociar([fraco, forte], "Técnico", random.Random(1))
    assert craque in forte.jogadores
    assert all(n.jogador is not craque for n in negocios)

    pobre, rico = _clube("Pobre", 60, dinheiro=0), _clube("Rico", 80)
    assert mercado_cpu.negociar([pobre, rico], "Técnico", random.Random(1)) == []

    a, b = _clube("A", 60), _clube("B", 80)
    a.rivais = {"B"}
    assert mercado_cpu.negociar([a, b], "Técnico", random.Random(1)) == []


def test_mesma_semente_mesmos_negocios(monkeypatch):
    _sempre_compra(monkeypatch)

    def rodada():
        clubes = [_clube("A", 60), _clube("B", 80), _clube("C", 70)]
        return [(n.jogador.nome, n.comprador.nome, n.valor)
                for n in mercado_cpu.negociar(clubes, "T", mercado_cpu.semente(7, 1, 1))]

    assert rodada() == rodada()


# --- a vontade do jogador (v1.9) ---------------------------------------------

def test_resistente_pode_recusar_o_comprador(monkeypatch):
    monkeypatch.setattr(mercado_cpu, "CHANCE_COMPRA", 1.0)
    monkeypatch.setattr(mercado_cpu, "CHANCE_RECUSA", 1.0)
    fraco, forte = _clube("Fraco", 60), _clube("Forte", 80)
    # do forte para o fraco ele é resistente: sempre recusa
    assert mercado_cpu.negociar([fraco, forte], "Técnico", random.Random(1)) == []


def test_recusado_o_comprador_tenta_o_proximo(monkeypatch):
    monkeypatch.setattr(mercado_cpu, "CHANCE_COMPRA", 1.0)
    monkeypatch.setattr(mercado_cpu, "CHANCE_RECUSA", 1.0)
    fraco, forte = _clube("Fraco", 60), _clube("Forte", 80)
    # metade topa ir; a outra metade é resistente e sempre recusa
    topam = {j.nome for j in forte.jogadores[::2]}
    real = vontade.interesse

    def interesse(jogador, *args):
        i = real(jogador, *args)
        i.nivel = vontade.ABERTO if jogador.nome in topam else vontade.RESISTENTE
        return i

    monkeypatch.setattr(vontade, "interesse", interesse)
    negocios = mercado_cpu.negociar([fraco, forte], "Técnico", random.Random(1))
    assert negocios and all(n.jogador.nome in topam for n in negocios)


def test_ninguem_compra_quem_nao_vem(monkeypatch):
    _sempre_compra(monkeypatch)
    fraco, forte, rival = _clube("Fraco", 60), _clube("Forte", 80), _clube("Rival", 60)
    fraco.rivais = {"Rival"}
    # sem a história, o fraco compra do forte (o primeiro teste); com todos
    # os do forte tendo feito história no rival do fraco, ninguém vem
    for j in forte.jogadores:
        j.clube_historia = "Rival"
    negocios = mercado_cpu.negociar([fraco, forte, rival], "Técnico", random.Random(1))
    assert not any(n.comprador is fraco and n.vendedor is forte for n in negocios)
