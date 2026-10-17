import pytest

from app.domain.clube import Clube
from app.domain.diretoria import (
    FAIXAS_META,
    descricao_meta,
    forca_do_elenco,
    meta_da_temporada,
    ranking_de_forca,
    situacao,
)
from app.domain.jogador import Jogador
from scripts.data_loader import carregar_campeonato

XI_433 = ["Goleiro"] + ["Defesa"] * 4 + ["Meio-Campo"] * 3 + ["Atacante"] * 3


def _clube(nome, jogadores):
    """jogadores: [(posicao, overall)]"""
    clube = Clube(nome, "Brasil", 100_000_000, 1_000_000)
    clube.jogadores = [
        Jogador(f"{nome} {i}", 25, pos, ovr) for i, (pos, ovr) in enumerate(jogadores)
    ]
    return clube


def _time(nome, overall):
    return _clube(nome, [(pos, overall) for pos in XI_433])


# --- força ---

def test_forca_e_a_media_do_melhor_xi_por_posicao():
    reservas_fracos = [(pos, 50) for pos in XI_433]
    clube = _clube("A", [(pos, 80) for pos in XI_433] + reservas_fracos)
    assert forca_do_elenco(clube) == 80


def test_forca_respeita_as_posicoes():
    # 11 meias de 90: só 3 entram no 4-3-3
    clube = _clube("A", [("Meio-Campo", 90)] * 11 + [("Goleiro", 60)])
    assert forca_do_elenco(clube) == pytest.approx((3 * 90 + 60) / 4, abs=0.1)


def test_forca_sem_jogadores_e_zero():
    assert forca_do_elenco(_clube("A", [])) == 0


def test_ranking_do_mais_forte_ao_mais_fraco():
    clubes = [_time("Fraco", 60), _time("Forte", 85), _time("Medio", 75)]
    assert ranking_de_forca(clubes) == {"Forte": 1, "Medio": 2, "Fraco": 3}


def test_ranking_empate_desempata_pelo_nome():
    assert ranking_de_forca([_time("B", 70), _time("A", 70)]) == {"A": 1, "B": 2}


def test_ranking_da_seed_cobre_os_20_clubes_sem_repetir():
    clubes = carregar_campeonato().clubes
    ranking = ranking_de_forca(clubes)
    assert sorted(ranking.values()) == list(range(1, len(clubes) + 1))


# --- meta ---

@pytest.mark.parametrize("ranking, meta", [
    (1, 1), (2, 4), (4, 4), (5, 8), (8, 8), (9, 12), (14, 12),
    (15, 16), (18, 16), (19, 18), (20, 18),
])
def test_meta_pela_faixa_do_ranking(ranking, meta):
    assert meta_da_temporada(ranking) == meta


def test_meta_de_liga_maior_cai_na_faixa_mais_baixa():
    assert meta_da_temporada(25) == FAIXAS_META[-1][1]


def test_quanto_mais_forte_mais_exigente_a_meta():
    metas = [meta_da_temporada(r) for r in range(1, 21)]
    assert metas == sorted(metas)


def test_descricao_da_meta():
    assert descricao_meta(1) == "Ser campeão"
    assert descricao_meta(4) == "Terminar no G-4"
    assert descricao_meta(7) == "Terminar até o 7º lugar"


# --- situação ---

@pytest.mark.parametrize("posicao, meta, esperado", [
    (1, 1, "batida"), (3, 4, "batida"), (4, 4, "batida"),
    (5, 4, "perto"), (7, 4, "perto"),
    (8, 4, "longe"), (20, 16, "longe"), (19, 16, "perto"),
])
def test_situacao(posicao, meta, esperado):
    assert situacao(posicao, meta) == esperado
