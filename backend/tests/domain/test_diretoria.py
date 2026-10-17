from app.domain.clube import Clube
from app.domain.diretoria import forca_do_elenco, ranking_de_forca
from app.domain.jogador import Jogador
from scripts.data_loader import carregar_campeonato


def _clube(nome, overalls):
    clube = Clube(nome, "Brasil", 100_000_000, 1_000_000)
    clube.jogadores = [
        Jogador(f"{nome} {i}", 25, "Meio-Campo", ovr) for i, ovr in enumerate(overalls)
    ]
    return clube


def test_forca_e_a_media_dos_11_melhores():
    clube = _clube("A", [80] * 11 + [50] * 7)   # reservas fracos não pesam
    assert forca_do_elenco(clube) == 80


def test_forca_com_menos_de_11_usa_quem_tem():
    assert forca_do_elenco(_clube("A", [70, 80])) == 75


def test_forca_sem_jogadores_e_zero():
    assert forca_do_elenco(_clube("A", [])) == 0


def test_ranking_do_mais_forte_ao_mais_fraco():
    clubes = [_clube("Fraco", [60] * 11), _clube("Forte", [85] * 11), _clube("Medio", [75] * 11)]
    assert ranking_de_forca(clubes) == {"Forte": 1, "Medio": 2, "Fraco": 3}


def test_ranking_empate_desempata_pelo_nome():
    clubes = [_clube("B", [70] * 11), _clube("A", [70] * 11)]
    assert ranking_de_forca(clubes) == {"A": 1, "B": 2}


def test_ranking_da_seed_cobre_os_20_clubes_sem_repetir():
    clubes = carregar_campeonato().clubes
    ranking = ranking_de_forca(clubes)
    assert sorted(ranking.values()) == list(range(1, len(clubes) + 1))
