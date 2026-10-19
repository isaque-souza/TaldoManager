import contextlib
import io
import random

from app.domain.jogador import Jogador
from app.domain.partida import Partida
from scripts.data_loader import carregar_campeonato
from tests.domain.test_partida import _clube_completo


def _silencioso(fn):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn()


def test_jogador_novo_nao_esta_suspenso():
    j = Jogador("X", 25, "Defesa", 80)
    assert j.jogos_suspensao == 0
    assert j.amarelos_ciclo == 0
    assert j.suspenso is False


def test_registrar_amarelo_suspende_a_cada_5():
    j = Jogador("Z", 25, "Defesa", 80)

    for _ in range(4):
        assert j.registrar_amarelo() is False
    assert j.suspenso is False

    assert j.registrar_amarelo() is True     # o 5º fecha o ciclo
    assert j.jogos_suspensao == 1
    assert j.amarelos_ciclo == 0

    for _ in range(4):
        j.registrar_amarelo()
    assert j.jogos_suspensao == 1
    assert j.registrar_amarelo() is True     # o 10º
    assert j.jogos_suspensao == 2


def test_suspenso_fica_de_fora_e_cumpre_um_jogo_por_partida():
    random.seed(1)
    casa = _clube_completo("Casa")
    fora = _clube_completo("Fora")
    _silencioso(Partida(casa, fora).simular_partida)

    titular = next(j for j in casa.titulares if j.posicao == "Defesa")
    titular.jogos_suspensao = 2

    _silencioso(Partida(casa, fora).simular_partida)
    assert titular not in casa.titulares
    assert titular.jogos_suspensao == 1

    _silencioso(Partida(casa, fora).simular_partida)
    assert titular.jogos_suspensao == 0

    partidas_antes = titular.partidas
    _silencioso(Partida(casa, fora).simular_partida)
    assert titular.partidas > partidas_antes     # voltou a jogar


def test_expulsao_deixa_o_jogador_de_fora_da_proxima():
    random.seed(4)
    casa = _clube_completo("Casa")
    fora = _clube_completo("Fora")

    suspenso = None
    for _ in range(60):
        _silencioso(Partida(casa, fora).simular_partida)
        cand = [
            j for j in casa.jogadores + fora.jogadores if j.jogos_suspensao > 0
        ]
        if cand:
            suspenso = cand[0]
            break

    assert suspenso is not None, "seed 4 não gerou expulsão em 60 jogos"

    dono = casa if suspenso in casa.jogadores else fora
    outro = fora if dono is casa else casa
    _silencioso(Partida(dono, outro).simular_partida)
    assert suspenso not in dono.titulares


def test_temporada_inteira_respeita_as_suspensoes():
    random.seed(7)
    camp = carregar_campeonato()
    with contextlib.redirect_stdout(io.StringIO()):
        while camp.rodada <= len(camp.calendario):
            camp.jogar_rodada()

    jogadores = [j for c in camp.clubes for j in c.jogadores]
    assert sum(j.vermelhos for j in jogadores) > 0          # houve expulsões
    assert all(j.jogos_suspensao >= 0 for j in jogadores)
    assert all(
        j.amarelos_ciclo < Jogador.AMARELOS_PARA_SUSPENSAO for j in jogadores
    )


def test_cartoes_saem_de_faltas_e_goleiro_quase_nao_leva():
    random.seed(3)
    camp = carregar_campeonato()
    with contextlib.redirect_stdout(io.StringIO()):
        while camp.rodada <= len(camp.calendario):
            camp.jogar_rodada()

    jogadores = [j for c in camp.clubes for j in c.jogadores]

    # todo cartão veio de uma falta -> ninguém tem mais cartões que faltas
    # (o 2º amarelo dá amarelo e vermelho na mesma falta, por isso separados)
    for j in jogadores:
        assert j.amarelos <= j.faltas and j.vermelhos <= j.faltas

    # goleiro praticamente não leva cartão (não comete as faltas do jogo)
    gols = [j for j in jogadores if j.posicao == "Goleiro"]
    assert sum(j.amarelos + j.vermelhos for j in gols) == 0

    # números de campeonato plausíveis
    amarelos = sum(j.amarelos for j in jogadores)
    assert 700 < amarelos < 1800          # ~2-4 por jogo em 380 jogos
