"""Vontade do jogador (v1.9): prestígio, formador, clube da história e sonho."""

import random
from types import SimpleNamespace

from app.domain import base, mercado, vontade
from app.domain.clube import Clube
from app.domain.jogador import Jogador
from app.domain.temporada import restaurar_estado, snapshot_estado
from scripts.data_loader import TODAS_AS_LIGAS, carregar_campeonato

POSICOES = ["Goleiro"] * 2 + ["Defesa"] * 6 + ["Meio-Campo"] * 6 + ["Atacante"] * 4


def _clube(nome, pais="Itália", overall=75, torcedores=1_000_000):
    clube = Clube(nome, pais, 50_000_000, torcedores)
    for i, posicao in enumerate(POSICOES):
        clube.contratar_jogador(Jogador(f"{nome} {i}", 25, posicao, overall))
    return clube


def _liga():
    """Três italianos (um gigante), um inglês forte e um brasileiro."""
    clubes = [
        _clube("Inter", overall=85, torcedores=5_000_000),
        _clube("Milan", overall=80, torcedores=4_000_000),
        _clube("Empoli", overall=65, torcedores=200_000),
        _clube("City", "Inglaterra", overall=86, torcedores=3_000_000),
        _clube("Bahia", "Brasil", overall=68, torcedores=2_000_000),
    ]
    return SimpleNamespace(clubes=clubes, livres=[])


def _clube_de(liga, nome):
    return next(c for c in liga.clubes if c.nome == nome)


def test_prestigio_vem_da_forca_e_da_torcida():
    liga = _liga()
    prest = vontade.prestigio(liga.clubes)
    assert prest["Inter"] > prest["Milan"] > prest["Empoli"]
    assert prest["Empoli"] == 0   # o mais fraco e com menos torcida
    assert all(0 <= p <= 100 for p in prest.values())


def test_jovem_e_cria_do_clube_onde_esta():
    liga = _liga()
    empoli = _clube_de(liga, "Empoli")
    jovem = Jogador("Garoto", vontade.IDADE_CRIA, "Atacante", 60)
    assert vontade.formador_inicial(jovem, empoli, liga.clubes) == "Empoli"


def test_formador_e_o_mesmo_em_toda_execucao():
    liga = _liga()
    inter = _clube_de(liga, "Inter")
    veterano = Jogador("Fulano de Tal", 30, "Atacante", 80)
    primeiro = vontade.formador_inicial(veterano, inter, liga.clubes)
    assert primeiro in {c.nome for c in liga.clubes}
    assert vontade.formador_inicial(veterano, inter, liga.clubes) == primeiro


def test_livre_tambem_tem_formador():
    liga = _liga()
    livre = Jogador("Sem Clube", 28, "Defesa", 70)
    assert vontade.formador_inicial(livre, None, liga.clubes) in {c.nome for c in liga.clubes}


def test_jovem_sonha_com_um_grande_do_pais_ou_do_mundo():
    liga = _liga()
    prest = vontade.prestigio(liga.clubes)
    grandes = {"Inter", "Milan", "Empoli", "City", "Bahia"}   # liga pequena: todos cabem
    for i in range(40):
        jogador = Jogador(f"Jogador {i}", 24, "Atacante", 70)
        jogador.formador = "Empoli"
        assert vontade.sonho(jogador, liga.clubes, prest) in grandes


def test_sonho_nacional_e_do_pais_onde_foi_formado():
    liga = _liga()
    prest = vontade.prestigio(liga.clubes)
    # formado na Itália: os grandes italianos aparecem entre os sonhos
    sonhos = set()
    for i in range(60):
        jogador = Jogador(f"Italiano {i}", 22, "Meio-Campo", 70)
        jogador.formador = "Empoli"
        sonhos.add(vontade.sonho(jogador, liga.clubes, prest))
    assert {"Inter", "Milan"} <= sonhos


def test_veterano_quer_encerrar_no_formador():
    liga = _liga()
    prest = vontade.prestigio(liga.clubes)
    veterano = Jogador("Velho Lobo", vontade.IDADE_APOSENTADORIA, "Defesa", 75)
    veterano.formador = "Bahia"
    assert vontade.sonho(veterano, liga.clubes, prest) == "Bahia"


def test_veterano_com_historia_escolhe_entre_formador_e_historia():
    liga = _liga()
    prest = vontade.prestigio(liga.clubes)
    escolhas = set()
    for i in range(40):
        veterano = Jogador(f"Veterano {i}", 33, "Defesa", 75)
        veterano.formador = "Bahia"
        veterano.clube_historia = "Milan"
        escolhas.add(vontade.sonho(veterano, liga.clubes, prest))
    assert escolhas == {"Bahia", "Milan"}


def test_idolo_ganha_a_historia_e_leva_ela_ao_sair():
    liga = _liga()
    milan, city = _clube_de(liga, "Milan"), _clube_de(liga, "City")
    idolo = Jogador("Ídolo", 29, "Atacante", 82, fama=80, temporadas_no_clube=5)
    milan.contratar_jogador(idolo)
    comum = milan.jogadores[0]

    vontade.marcar_historia(liga)
    assert idolo.clube_historia == "Milan"
    assert comum.clube_historia is None

    mercado.transferir(idolo, milan, city, 1_000_000)
    vontade.marcar_historia(liga)
    assert idolo.clube_historia == "Milan"   # no City ainda não fez história


def test_completar_nao_mexe_em_quem_ja_tem():
    liga = _liga()
    jogador = _clube_de(liga, "Inter").jogadores[0]
    jogador.formador, jogador.sonho = "Bahia", "Empoli"
    vontade.completar(liga)
    assert (jogador.formador, jogador.sonho) == ("Bahia", "Empoli")


def test_na_virada_o_sonho_muda_com_a_idade():
    liga = _liga()
    jogador = _clube_de(liga, "Inter").jogadores[0]
    vontade.completar(liga)
    jogador.formador = "Bahia"
    jogador.idade = vontade.IDADE_APOSENTADORIA
    vontade.virada(liga)
    assert jogador.sonho == "Bahia"


def test_seed_da_formador_e_sonho_a_todo_mundo():
    campeonato = carregar_campeonato(TODAS_AS_LIGAS)
    nomes = {c.nome for c in campeonato.clubes}
    todos = [j for c in campeonato.clubes for j in c.jogadores] + campeonato.livres
    assert all(j.formador in nomes and j.sonho in nomes for j in todos)
    # ninguém sonha com o mesmo clube que um quarto da liga
    maior = max(sum(j.sonho == n for j in todos) for n in nomes)
    assert maior < len(todos) / 4


def test_jovem_da_base_e_cria_da_casa():
    campeonato = carregar_campeonato()
    clube = campeonato.clubes[0]
    jovem = base.gerar_jovem(clube, set(), random.Random(1))
    assert jovem.formador == clube.nome


def test_snapshot_guarda_a_vontade():
    campeonato = carregar_campeonato()
    jogador = campeonato.clubes[0].jogadores[0]
    jogador.formador, jogador.clube_historia, jogador.sonho = "A", "B", "C"
    blob = snapshot_estado(campeonato)

    novo = carregar_campeonato()
    restaurar_estado(novo, blob)
    copia = next(j for c in novo.clubes for j in c.jogadores if j.nome == jogador.nome)
    assert (copia.formador, copia.clube_historia, copia.sonho) == ("A", "B", "C")
