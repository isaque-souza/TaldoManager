import pytest

from app.domain.clube import Clube
from app.domain.diretoria import (
    FAIXAS_META,
    avaliar_cargo,
    descricao_meta,
    forca_do_elenco,
    meta_da_temporada,
    ranking_de_forca,
    resumo_carreira,
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
    # o último é sempre longe — senão a meta "até 18º" nunca ficaria longe
    (19, 18, "perto"), (20, 18, "longe"),
])
def test_situacao(posicao, meta, esperado):
    assert situacao(posicao, meta) == esperado


def test_ultimo_lugar_so_nao_e_longe_se_a_meta_for_o_ultimo():
    assert situacao(20, 20) == "batida"
    assert situacao(10, 9, total=10) == "longe"


# --- cargo ---

def test_dentro_ou_perto_da_meta_mantem_o_cargo():
    assert avaliar_cargo((4, 4))["estado"] == "mantido"
    assert avaliar_cargo((7, 4), anterior=(9, 4))["estado"] == "mantido"


def test_uma_temporada_longe_ameaca():
    cargo = avaliar_cargo((9, 4))
    assert cargo["estado"] == "ameacado"
    assert cargo["motivo"]


def test_longe_duas_seguidas_demite():
    cargo = avaliar_cargo((9, 4), anterior=(10, 4))
    assert cargo["estado"] == "demitido"
    assert "duas temporadas" in cargo["motivo"]


def test_longe_depois_de_temporada_boa_so_ameaca():
    assert avaliar_cargo((9, 4), anterior=(2, 4))["estado"] == "ameacado"


def test_muito_abaixo_demite_numa_temporada_so():
    cargo = avaliar_cargo((12, 4))   # 8 abaixo do G-4
    assert cargo["estado"] == "demitido"
    assert "12º" in cargo["motivo"]
    assert avaliar_cargo((11, 4))["estado"] == "ameacado"   # 7 abaixo: ainda não


def test_lanterna_com_meta_18_conta_como_longe():
    assert avaliar_cargo((20, 18), anterior=(20, 18))["estado"] == "demitido"


def test_em_andamento_so_herda_a_ameaca():
    assert avaliar_cargo(None, anterior=(9, 4))["estado"] == "ameacado"
    assert avaliar_cargo(None, anterior=(3, 4))["estado"] == "mantido"
    assert avaliar_cargo(None)["estado"] == "mantido"


def test_temporada_sem_meta_nao_conta_como_longe():
    # save de antes da v1.0 na carreira: não pesa contra o técnico
    assert avaliar_cargo((9, 4), anterior=None)["estado"] == "ameacado"


def test_resumo_da_carreira():
    resumo = resumo_carreira([
        {"posicao": 1, "meta": None, "campeao": True},    # save antigo
        {"posicao": 3, "meta": 4, "campeao": False},
        {"posicao": 9, "meta": 4, "campeao": False},
    ])
    assert resumo == {
        "temporadas": 3, "titulos": 1, "metas_batidas": 1,
        "metas_avaliadas": 2, "melhor_posicao": 1,
    }
