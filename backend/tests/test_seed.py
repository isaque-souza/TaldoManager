"""Garante que a seed em disco tem uma hierarquia de forças entre os clubes
(tiers), e não 20 elencos praticamente iguais."""

import statistics

from scripts.data_loader import carregar_jogadores, carregar_clubes


def _forca_xi(clube):
    titulares = sorted(clube.jogadores, key=lambda j: j.overall, reverse=True)[:11]
    return statistics.mean(j.overall for j in titulares)


def test_seed_tem_20_clubes_e_360_jogadores():
    jogadores = carregar_jogadores()
    clubes = carregar_clubes(jogadores)

    assert len(clubes) == 20
    assert len(jogadores) == 360
    assert all(len(c.jogadores) == 18 for c in clubes)


def test_clubes_de_elite_sao_mais_fortes_que_os_fracos():
    jogadores = carregar_jogadores()
    clubes = {c.nome: c for c in carregar_clubes(jogadores)}

    elite = statistics.mean(
        _forca_xi(clubes[n]) for n in ("Real Taldo", "Taldo City")
    )
    fracos = statistics.mean(
        _forca_xi(clubes[n]) for n in ("Taldo Dragons", "Taldo FC")
    )

    assert elite - fracos >= 8


def test_seed_tem_um_espalhamento_de_forca_realista():
    jogadores = carregar_jogadores()
    clubes = carregar_clubes(jogadores)

    forcas = sorted(_forca_xi(c) for c in clubes)

    # do pior ao melhor elenco deve haver uma diferença clara
    assert forcas[-1] - forcas[0] >= 9


def test_seed_tem_dados_de_mercado_coerentes():
    jogadores = carregar_jogadores().values()

    assert all(j.overall <= j.potencial <= 99 for j in jogadores)
    assert all(1 <= j.contrato_anos <= 5 for j in jogadores)
    # veteranos não têm margem de crescimento
    assert all(j.potencial == j.overall for j in jogadores if j.idade >= 30)
    # e pelo menos alguns jovens são promessas
    assert any(j.potencial - j.overall >= 8 for j in jogadores if j.idade <= 20)
