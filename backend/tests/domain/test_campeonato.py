from app.domain.campeonato import Campeonato
from app.domain.clube import Clube


def test_criar_campeonato():
    clubes = [
        Clube("FC Taldo", "Brasil", 1000000),
        Clube("Real Taldo", "Brasil", 1000000),
        Clube("Taldo United", "Brasil", 1000000),
        Clube("Taldo City", "Brasil", 1000000),
    ]

    campeonato = Campeonato(
        "Campeonato Taldo",
        clubes
    )

    assert campeonato.nome == "Campeonato Taldo"
    assert campeonato.clubes == clubes
    assert campeonato.rodada == 1
    assert campeonato.historico == []
    assert campeonato.calendario is not None

# --- calendário (mando alternado) ------------------------------------------

import random

import pytest

from app.domain.temporada import restaurar_estado, snapshot_estado
from scripts.data_loader import carregar_campeonato


def _liga(n):
    return Campeonato("Liga", [Clube(f"C{i}", "Brasil", 0) for i in range(n)])


def _maior_sequencia(campeonato, clube):
    lados = [
        next(m is clube for m, v in rodada if clube in (m, v))
        for rodada in campeonato.calendario
        if any(clube in par for par in rodada)
    ]
    maior = atual = 1
    for antes, agora in zip(lados, lados[1:]):
        atual = atual + 1 if antes == agora else 1
        maior = max(maior, atual)
    return maior


@pytest.mark.parametrize("n", [4, 6, 20])
def test_todos_se_enfrentam_uma_vez_em_cada_casa(n):
    camp = _liga(n)
    assert len(camp.calendario) == 2 * (n - 1)
    jogos = [(m.nome, v.nome) for rodada in camp.calendario for m, v in rodada]
    assert len(jogos) == len(set(jogos)) == n * (n - 1)
    for rodada in camp.calendario:
        times = [t for par in rodada for t in par]
        assert len(times) == len(set(times)) == n   # cada um joga uma vez


@pytest.mark.parametrize("n", [6, 20])
def test_mando_alterna(n):
    camp = _liga(n)
    metade = n - 1
    for clube in camp.clubes:
        assert _maior_sequencia(camp, clube) <= 2
        em_casa = [
            sum(1 for m, _ in rodada if m is clube)
            for rodada in camp.calendario
        ]
        assert sum(em_casa) == n - 1
        assert metade // 2 <= sum(em_casa[:metade]) <= metade // 2 + 1


def test_sem_revanche_logo_na_virada_do_turno():
    camp = _liga(20)
    fim_turno = {frozenset((m.nome, v.nome)) for m, v in camp.calendario[18]}
    inicio_returno = {frozenset((m.nome, v.nome)) for m, v in camp.calendario[19]}
    assert not fim_turno & inicio_returno


def test_calendario_antigo_ainda_existe_e_nao_alternava():
    camp = _liga(20)
    antigo = camp.gerar_calendario(versao=1)
    camp.calendario = antigo
    assert max(_maior_sequencia(camp, c) for c in camp.clubes) > 2


def test_save_antigo_segue_com_o_calendario_em_que_comecou():
    estado = random.getstate()
    try:
        camp = carregar_campeonato()
        blob = snapshot_estado(camp)
        assert blob["calendario"] == Campeonato.CALENDARIO_ATUAL

        del blob["calendario"]   # snapshot de antes do mando alternado
        antigo = carregar_campeonato()
        restaurar_estado(antigo, blob)
        assert antigo.versao_calendario == 1
        assert [[(m.nome, v.nome) for m, v in r] for r in antigo.calendario] == [
            [(m.nome, v.nome) for m, v in r] for r in antigo.gerar_calendario(versao=1)
        ]

        novo = carregar_campeonato()
        restaurar_estado(novo, snapshot_estado(camp))
        assert novo.versao_calendario == Campeonato.CALENDARIO_ATUAL
    finally:
        random.setstate(estado)


def test_mando_alterna_em_cada_liga():
    clubes = [Clube(f"A{i}", "Brasil", 0) for i in range(6)]
    clubes += [Clube(f"B{i}", "Brasil", 0) for i in range(6)]
    for c in clubes[6:]:
        c.liga = "Segunda"
    camp = Campeonato("Ligas", clubes)
    assert len(camp.calendario) == 10
    for clube in camp.clubes:
        assert _maior_sequencia(camp, clube) <= 2
        rivais = {v.liga for m, v in (p for r in camp.calendario for p in r)
                  if m is clube} | {m.liga for m, v in (p for r in camp.calendario for p in r)
                                    if v is clube}
        assert rivais == {clube.liga}


# --- calendário sorteado (v3) ----------------------------------------------

from app.domain.campeonato import semente_do_calendario


def _ordem(camp):
    return [[(m.nome, v.nome) for m, v in rodada] for rodada in camp.calendario]


def test_sem_semente_e_a_ordem_da_seed():
    camp = _liga(20)
    assert camp.semente_calendario is None
    assert _ordem(camp) == [[(m.nome, v.nome) for m, v in r] for r in camp.gerar_calendario(versao=2)]


def test_sementes_diferentes_sorteiam_ordens_diferentes():
    a, b = _liga(20), _liga(20)
    a.sortear_calendario(1)
    b.sortear_calendario(2)
    assert _ordem(a) != _ordem(b)
    # e a mesma semente repete a ordem
    c = _liga(20)
    c.sortear_calendario(1)
    assert _ordem(a) == _ordem(c)


@pytest.mark.parametrize("semente", [1, 7, 12345])
def test_calendario_sorteado_segue_valido(semente):
    camp = _liga(20)
    camp.sortear_calendario(semente)
    assert len(camp.calendario) == 38
    jogos = [par for rodada in _ordem(camp) for par in rodada]
    assert len(jogos) == len(set(jogos)) == 20 * 19
    for clube in camp.clubes:
        assert _maior_sequencia(camp, clube) <= 2
    for rodada in camp.calendario:
        times = [t for par in rodada for t in par]
        assert len(times) == len(set(times)) == 20


def test_cada_liga_sorteia_a_sua_ordem():
    clubes = [Clube(f"A{i}", "Brasil", 0) for i in range(6)] + [Clube(f"B{i}", "Inglaterra", 0) for i in range(6)]
    for c in clubes[6:]:
        c.liga = "premier"
    camp = Campeonato("Ligas", clubes)
    camp.sortear_calendario(9)
    for rodada in camp.calendario:
        for m, v in rodada:
            assert m.liga == v.liga   # ninguém joga contra a outra liga


def test_semente_do_calendario_por_temporada_e_sem_mexer_no_rng():
    estado = random.getstate()
    assert semente_do_calendario(10, 1) == semente_do_calendario(10, 1)
    assert semente_do_calendario(10, 1) != semente_do_calendario(10, 2)
    assert random.getstate() == estado   # a sequência das partidas é a mesma


def test_snapshot_guarda_o_sorteio():
    estado = random.getstate()
    try:
        camp = carregar_campeonato()
        camp.sortear_calendario(4242)
        blob = snapshot_estado(camp)
        assert blob["semente_calendario"] == 4242

        de_novo = carregar_campeonato()
        restaurar_estado(de_novo, blob)
        assert de_novo.semente_calendario == 4242
        assert _ordem(de_novo) == _ordem(camp)
    finally:
        random.setstate(estado)
