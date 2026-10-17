"""Garante que a seed em disco tem uma hierarquia de forças entre os clubes
(tiers), e não 20 elencos praticamente iguais."""

import json
import statistics
from pathlib import Path

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


def _clubes_json():
    return json.loads((Path(__file__).parent.parent / "data/seeds/clubes.json").read_text())


def test_todo_clube_tem_identidade_visual_e_siglas_unicas():
    clubes = _clubes_json()
    for c in clubes:
        ident = c["identidade"]
        assert ident["cor_primaria"].startswith("#") and len(ident["cor_primaria"]) == 7
        assert ident["cor_secundaria"].startswith("#") and len(ident["cor_secundaria"]) == 7
        assert len(ident["sigla"]) == 3
    assert len({c["identidade"]["sigla"] for c in clubes}) == len(clubes)


def test_rivais_nao_tem_a_mesma_cor_principal():
    clubes = _clubes_json()
    cor = {c["nome"]: c["identidade"]["cor_primaria"] for c in clubes}
    for c in clubes:
        for rival in c.get("rivais", []):
            assert cor[c["nome"]] != cor[rival], (c["nome"], rival)
