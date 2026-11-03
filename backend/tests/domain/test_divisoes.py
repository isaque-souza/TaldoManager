"""Séries A e B (v2.5): quem é de qual divisão e quem sobe e cai."""

import json
from collections import Counter

from app.domain import divisoes
from scripts.data_loader import LIGAS, TODAS_AS_LIGAS


def _tabela(liga, nomes):
    return [{"nome": n, "liga": liga, "posicao_final": i} for i, n in enumerate(nomes, start=1)]


def test_cada_pais_tem_a_serie_a_e_a_b():
    assert divisoes.da_divisao("taldo", 2) == "taldo_b"
    assert divisoes.da_divisao("championship", 1) == "premier"
    assert divisoes.primeiras(TODAS_AS_LIGAS) == ["taldo", "premier"]
    # liga sem B: uma Série A sozinha
    assert divisoes.divisao("liga-nova") == 1
    assert divisoes.da_divisao("liga-nova", 2) is None


def test_ordenar_poe_as_a_antes_das_b():
    assert divisoes.ordenar(["championship", "taldo_b", "premier", "taldo"]) == [
        "taldo", "premier", "taldo_b", "championship",
    ]


def test_save_antigo_ganha_as_series_b():
    assert divisoes.com_as_series_b(["taldo"]) == ["taldo", "taldo_b"]
    assert divisoes.com_as_series_b(["taldo", "premier"]) == list(TODAS_AS_LIGAS)
    assert divisoes.com_as_series_b(list(TODAS_AS_LIGAS)) == list(TODAS_AS_LIGAS)


def test_sobem_os_4_melhores_da_b_e_caem_os_4_piores_da_a():
    a = [f"A{i}" for i in range(1, 21)]
    b = [f"B{i}" for i in range(1, 21)]
    movimentos = divisoes.acesso_e_rebaixamento(_tabela("taldo", a) + _tabela("taldo_b", b))
    assert movimentos == {
        "B1": "taldo", "B2": "taldo", "B3": "taldo", "B4": "taldo",
        "A17": "taldo_b", "A18": "taldo_b", "A19": "taldo_b", "A20": "taldo_b",
    }


def test_sem_a_b_ninguem_troca():
    assert divisoes.acesso_e_rebaixamento(_tabela("taldo", [f"A{i}" for i in range(20)])) == {}


def test_seeds_das_series_b():
    nomes = Counter()
    for liga, (_, pasta) in LIGAS.items():
        for arquivo in ("jogadores.json", "livres.json"):
            if (pasta / arquivo).exists():
                nomes.update(j["nome"] for j in json.loads((pasta / arquivo).read_text(encoding="utf-8")))
    # o jogo identifica o jogador pelo nome: nenhum se repete entre as seeds
    assert not [n for n, q in nomes.items() if q > 1]

    for liga in ("taldo_b", "championship"):
        clubes = json.loads((LIGAS[liga][1] / "clubes.json").read_text(encoding="utf-8"))
        assert len(clubes) == 20
        assert all(len(c["titulares"]) == 11 and len(c["reservas"]) == 12 for c in clubes)
