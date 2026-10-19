"""Papel no elenco (v1.7)."""

import pytest

from app.domain import contrato, papeis
from app.domain.clube import Clube
from app.domain.jogador import Jogador
from app.domain.papeis import CONTENTE, INCOMODADO, QUER_SAIR

_POSICOES = (["Goleiro"] * 3 + ["Defesa"] * 7 + ["Meio-Campo"] * 7 + ["Atacante"] * 6)


def _clube():
    clube = Clube("A", "Brasil", 50_000_000)
    for i, pos in enumerate(_POSICOES):
        clube.contratar_jogador(Jogador(f"A {i}", 25, pos, 90 - i))
    return clube


def test_distribuicao_inicial_segue_a_escalacao_do_motor():
    clube = _clube()
    papeis.completar(clube)

    titulares = [j for j in clube.jogadores if j.papel == papeis.TITULAR]
    assert len(titulares) == 11
    assert sum(1 for j in titulares if j.posicao == "Goleiro") == 1
    clube.escalar_time()
    assert set(titulares) == set(clube.titulares)

    rotacao = [j for j in clube.jogadores if j.papel == papeis.ROTACAO]
    assert len(rotacao) == papeis.VAGAS_ROTACAO
    assert all(j.posicao != "Goleiro" for j in rotacao)
    assert all(j.papel for j in clube.jogadores)


def test_jovem_de_potencial_vira_promessa_e_completar_nao_mexe_em_quem_tem_papel():
    clube = _clube()
    papeis.completar(clube)
    papeis.definir(clube.jogadores[0], papeis.RESERVA)

    jovem = Jogador("Jovem", 19, "Atacante", 70, potencial=85)
    clube.contratar_jogador(jovem)
    papeis.completar(clube)

    assert jovem.papel == papeis.PROMESSA
    assert clube.jogadores[0].papel == papeis.RESERVA


def test_promessa_so_ate_21_anos():
    veterano = Jogador("V", 30, "Atacante", 80)
    with pytest.raises(papeis.PapelInvalido):
        papeis.definir(veterano, papeis.PROMESSA)
    with pytest.raises(papeis.PapelInvalido):
        papeis.definir(veterano, "craque")


def test_rebaixar_incomoda_e_promover_deixa_contente():
    j = Jogador("J", 25, "Atacante", 80)
    j.papel = papeis.TITULAR
    papeis.definir(j, papeis.ROTACAO)
    assert j.humor == INCOMODADO
    papeis.definir(j, papeis.RESERVA)       # já incomodado: não piora sozinho
    assert j.humor == INCOMODADO
    papeis.definir(j, papeis.TITULAR)
    assert j.humor == CONTENTE
    papeis.definir(j, papeis.TITULAR)       # mesmo papel: nada muda
    assert j.humor == CONTENTE


def test_disponivel_nao_conta_lesionado_nem_suspenso():
    clube = _clube()
    clube.jogadores[0].rodadas_lesao = 2
    clube.jogadores[1].jogos_suspensao = 1
    papeis.contar_disponiveis(clube)
    assert clube.jogadores[0].jogos_disponivel == 0
    assert clube.jogadores[1].jogos_disponivel == 0
    assert clube.jogadores[2].jogos_disponivel == 1


def test_checagem_a_cada_5_rodadas_a_partir_da_10():
    assert [r for r in range(1, 39) if papeis.eh_checagem(r)] == [10, 15, 20, 25, 30, 35]


def _jogador(papel, disp, titular=0, jogou=0):
    j = Jogador("J", 20, "Atacante", 80)
    j.papel, j.jogos_disponivel, j.titularidades, j.partidas = papel, disp, titular, jogou
    return j


def test_humor_anda_um_passo_por_checagem():
    clube = Clube("A", "Brasil", 0)
    j = _jogador(papeis.TITULAR, 10, titular=4)   # 40% < 50%
    clube.jogadores = [j]

    papeis.checar(clube)
    assert j.humor == INCOMODADO and not j.a_venda
    papeis.checar(clube)
    assert j.humor == QUER_SAIR and j.a_venda
    papeis.checar(clube)                           # não passa de quer sair
    assert j.humor == QUER_SAIR

    j.titularidades = 6                             # voltou a jogar: 60%
    papeis.checar(clube)
    assert j.humor == INCOMODADO
    papeis.checar(clube)
    assert j.humor == CONTENTE


def test_cada_papel_cobra_a_sua_meta():
    clube = Clube("A", "Brasil", 0)
    rotacao_ok = _jogador(papeis.ROTACAO, 10, jogou=3)        # 30%
    rotacao_ruim = _jogador(papeis.ROTACAO, 10, jogou=2)
    promessa_ok = _jogador(papeis.PROMESSA, 10, jogou=2)      # 20%
    reserva = _jogador(papeis.RESERVA, 10)                    # sem meta
    poucos_jogos = _jogador(papeis.TITULAR, papeis.MINIMO_DE_JOGOS - 1)
    clube.jogadores = [rotacao_ok, rotacao_ruim, promessa_ok, reserva, poucos_jogos]

    papeis.checar(clube)

    assert rotacao_ok.humor == CONTENTE
    assert rotacao_ruim.humor == INCOMODADO
    assert promessa_ok.humor == CONTENTE
    assert reserva.humor == CONTENTE
    assert poucos_jogos.humor == CONTENTE


def test_quem_quer_sair_nao_renova():
    clube = _clube()
    j = clube.jogadores[5]
    j.humor = QUER_SAIR
    r = contrato.avaliar_renovacao(j, clube, j.salario * 10, 2, "3x")
    assert r.tipo == "recusada" and "quer sair" in r.motivo
