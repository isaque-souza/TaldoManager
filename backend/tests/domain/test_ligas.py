"""Várias ligas no mesmo campeonato (v1.6)."""

import collections
import contextlib
import io
import random

import pytest

from app.domain import financas
from scripts.data_loader import carregar_campeonato

DUAS = ("taldo", "premier")


@pytest.fixture(scope="module")
def temporada_inteira():
    random.seed(11)
    camp = carregar_campeonato(DUAS)
    with contextlib.redirect_stdout(io.StringIO()):
        while camp.rodada <= len(camp.calendario):
            camp.jogar_rodada()
    return camp


def test_sem_dizer_a_liga_e_so_a_taldo():
    camp = carregar_campeonato()
    assert camp.ligas == ["taldo"]
    assert len(camp.clubes) == 20 and len(camp.livres) == 50


def test_duas_ligas_carregam_40_clubes_e_os_livres_das_duas():
    camp = carregar_campeonato(DUAS)
    assert camp.ligas == ["taldo", "premier"]
    assert len(camp.clubes_da_liga("taldo")) == len(camp.clubes_da_liga("premier")) == 20
    assert len(camp.livres) == 100
    assert {c.liga for c in camp.clubes if c.nome == "Arsenal"} == {"premier"}


def test_a_camisa_de_verdade_vem_junto():
    camp = carregar_campeonato(DUAS)
    city = next(c for c in camp.clubes if c.nome == "Manchester City")
    assert next(j for j in city.jogadores if j.nome == "Erling Håland").numero == 9


def test_cada_liga_tem_o_seu_turno_e_returno():
    camp = carregar_campeonato(DUAS)
    assert len(camp.calendario) == 38
    liga = {c.nome: c.liga for c in camp.clubes}
    jogos = collections.Counter()
    for rodada in camp.calendario:
        em_campo = [c.nome for jogo in rodada for c in jogo]
        assert len(em_campo) == len(set(em_campo)) == 40   # todos, uma vez
        for casa, fora in rodada:
            assert casa.liga == fora.liga                   # nunca entre ligas
            jogos[frozenset((casa.nome, fora.nome))] += 1
    assert set(jogos.values()) == {2}                       # ida e volta
    assert len(jogos) == 2 * (20 * 19 // 2)
    assert all(liga[a] == liga[b] for a, b in jogos)


def test_tabela_e_premiacao_por_liga(temporada_inteira):
    camp = temporada_inteira
    for liga in DUAS:
        tabela = camp.classificacao(liga)
        assert len(tabela) == 20 and {c.liga for c in tabela} == {liga}
        assert all(c.vitorias + c.empates + c.derrotas == 38 for c in tabela)
        # cada liga tem o seu campeão premiado
        assert tabela[0].receita_premiacao == financas.premiacao(1)
        assert tabela[-1].receita_premiacao == financas.premiacao(20)
