"""Finanças dos clubes (v0.7): TV, bilheteria, salários e premiação."""

import random

from app.domain import financas
from app.domain.clube import Clube
from app.domain.jogador import Jogador
from scripts.data_loader import carregar_campeonato


def _clube(nome="Teste FC", dinheiro=1_000_000, torcedores=100_000):
    clube = Clube(nome, "Brasil", dinheiro, torcedores)
    clube.contratar_jogador(Jogador("Fulano", 25, "Atacante", 80))
    return clube


def test_lancar_receita_soma_no_caixa_e_na_categoria():
    clube = _clube()
    clube.lancar("receita_tv", 50_000)
    assert clube.dinheiro == 1_050_000
    assert clube.receita_tv == 50_000


def test_lancar_despesa_tira_do_caixa_e_pode_endividar():
    clube = _clube(dinheiro=10_000)
    clube.lancar("despesa_salarios", 30_000)
    assert clube.dinheiro == -20_000
    assert clube.despesa_salarios == 30_000


def test_dinheiro_inicial_fica_registrado():
    clube = _clube(dinheiro=5_000_000)
    clube.lancar("receita_tv", 1)
    assert clube.dinheiro_inicial == 5_000_000


def test_bilheteria_proporcional_aos_torcedores():
    assert financas.bilheteria(_clube(torcedores=2_000_000)) == 2 * financas.bilheteria(
        _clube(torcedores=1_000_000)
    )


def test_premiacao_cai_por_posicao_e_tem_piso():
    assert financas.premiacao(1) == financas.PREMIO_CAMPEAO
    assert financas.premiacao(1) > financas.premiacao(2) > financas.premiacao(10)
    assert financas.premiacao(20) == financas.PREMIO_DEGRAU
    assert financas.premiacao(50) == financas.PREMIO_DEGRAU


def test_folha_acompanha_o_elenco():
    clube = _clube()
    antes = financas.folha_salarial(clube)
    clube.contratar_jogador(Jogador("Ciclano", 25, "Defesa", 85))
    assert financas.folha_salarial(clube) > antes


def test_rodada_so_o_mandante_recebe_bilheteria():
    casa, fora = _clube("Casa"), _clube("Fora")
    financas.processar_rodada([(casa, fora)], total_rodadas=38)
    assert casa.receita_bilheteria > 0
    assert fora.receita_bilheteria == 0
    assert casa.receita_tv == fora.receita_tv > 0
    assert casa.despesa_salarios > 0 and fora.despesa_salarios > 0


def test_temporada_completa_fecha_as_contas():
    random.seed(3)
    campeonato = carregar_campeonato()
    while campeonato.rodada <= len(campeonato.calendario):
        campeonato.jogar_rodada()

    for clube in campeonato.clubes:
        receitas = (clube.receita_tv + clube.receita_bilheteria
                    + clube.receita_premiacao)
        # o caixa final é exatamente inicial + receitas - despesas
        assert clube.dinheiro == clube.dinheiro_inicial + receitas - clube.despesa_salarios
        # ~1,5 mi de TV (arredondamento por rodada) e folha anual inteira
        assert abs(clube.receita_tv - financas.COTA_TV_TEMPORADA) < 100
        assert abs(clube.despesa_salarios - financas.folha_salarial(clube)) < 100

    campeao = campeonato.classificacao()[0]
    lanterna = campeonato.classificacao()[-1]
    assert campeao.receita_premiacao == financas.PREMIO_CAMPEAO
    assert lanterna.receita_premiacao == financas.PREMIO_DEGRAU


def test_premiacao_so_sai_no_fim_da_temporada():
    random.seed(3)
    campeonato = carregar_campeonato()
    campeonato.jogar_rodada()
    assert all(c.receita_premiacao == 0 for c in campeonato.clubes)
