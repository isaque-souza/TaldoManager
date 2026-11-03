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


def test_premiacao_linear_por_posicao_e_pelo_tamanho_da_liga():
    # v2.5: cada posição vale um degrau; o último leva um
    degrau = financas.premiacao(20, "premier")
    assert degrau == financas.MERITO_DEGRAU
    assert financas.premiacao(1, "premier") == 20 * degrau
    assert financas.premiacao(1, "premier") - financas.premiacao(2, "premier") == degrau
    # a mesma posição paga menos numa liga menor
    assert financas.premiacao(1, "taldo") == round(20 * degrau * financas.PESO_LIGA["taldo"])
    assert financas.premiacao(1, "liga-nova") < financas.premiacao(1, "taldo")
    assert financas.premiacao(50, "premier") == degrau   # piso


def test_premiacao_da_economia_v1_segue_a_antiga():
    assert financas.premiacao(1, economia=1) == financas.PREMIO_CAMPEAO_V1
    assert financas.premiacao(20, economia=1) == financas.PREMIO_DEGRAU_V1


def test_audiencia_pela_torcida_perto_da_maior():
    maior = financas.audiencia_temporada(1_000_000, 1_000_000, "premier")
    assert maior == financas.AUDIENCIA_MAX
    # um quarto da torcida rende metade (raiz)
    assert financas.audiencia_temporada(250_000, 1_000_000, "premier") == maior // 2
    assert financas.audiencia_temporada(0, 1_000_000, "premier") == 0


def test_patrocinio_paga_mais_ao_mais_forte_e_a_maior_torcida():
    topo = financas.patrocinio_temporada(1, 20, 1_000_000, 1_000_000, "premier")
    assert topo == financas.PATROCINIO_FORCA + financas.PATROCINIO_TORCIDA
    meio = financas.patrocinio_temporada(10, 20, 1_000_000, 1_000_000, "premier")
    ultimo = financas.patrocinio_temporada(20, 20, 1_000_000, 1_000_000, "premier")
    assert topo > meio > ultimo == financas.PATROCINIO_TORCIDA
    # ao quadrado: o meio da tabela de força leva bem menos que a metade
    assert meio - ultimo < (topo - ultimo) / 3
    assert financas.patrocinio_temporada(1, 20, 1, 1, "taldo") < topo


def test_rodada_da_economia_v1_nao_tem_patrocinio():
    casa, fora = _clube("Casa"), _clube("Fora")
    financas.processar_rodada([(casa, fora)], total_rodadas=38, economia=1)
    assert casa.receita_tv == round(financas.COTA_TV_V1 / 38)
    assert casa.receita_patrocinio == 0


def test_migrar_salarios_v1_so_sobe_os_da_escala_antiga():
    antigo = Jogador("Antigo", 27, "Atacante", 85, salario=Jogador.salario_de_mercado_v1(85))
    novo = Jogador("Novo", 27, "Atacante", 85)   # já na escala nova
    financas.migrar_salarios_v1([antigo, novo])
    assert abs(antigo.salario - Jogador.salario_de_mercado(85)) <= 2_000
    assert novo.salario == Jogador.salario_de_mercado(85)


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
                    + clube.receita_premiacao + clube.receita_patrocinio)
        # o caixa final é exatamente inicial + receitas - despesas
        assert clube.dinheiro == clube.dinheiro_inicial + receitas - clube.despesa_salarios
        # a parte igual da TV mais a audiência (arredondamento por rodada) e a
        # folha anual inteira
        assert clube.receita_tv >= financas.cota_tv_temporada(clube.liga) - 100
        assert clube.receita_tv <= financas.cota_tv_temporada(clube.liga) + financas.AUDIENCIA_MAX
        assert abs(clube.despesa_salarios - financas.folha_salarial(clube)) < 100

        # um ponto por rodada; o último é o caixa final (já com a premiação)
        assert len(clube.historico_caixa) == len(campeonato.calendario)
        assert clube.historico_caixa[-1] == clube.dinheiro

    campeao = campeonato.classificacao()[0]
    lanterna = campeonato.classificacao()[-1]
    assert campeao.receita_premiacao == financas.premiacao(1, campeao.liga)
    assert lanterna.receita_premiacao == financas.premiacao(20, lanterna.liga)
    assert campeao.receita_patrocinio > 0


def test_premiacao_so_sai_no_fim_da_temporada():
    random.seed(3)
    campeonato = carregar_campeonato()
    campeonato.jogar_rodada()
    assert all(c.receita_premiacao == 0 for c in campeonato.clubes)


def test_olheiro_e_base_custam_pelo_peso_da_liga_com_piso():
    """v2.6: o nível 5 da base custa 4 mi na Premier e 1,6 mi no
    Brasileirão; a Série B paga o piso (25% do preço cheio)."""
    from app.domain import base, olheiro, olheiro_base
    assert base.custo_temporada(5, "premier") == base.custo_temporada(5) == 4_000_000
    assert base.custo_temporada(5, "brasileirao") == 1_600_000
    assert olheiro.custo_temporada(5, "brasileirao_b") == 1_000_000
    assert base.custo_da_troca(1, 5, 19, 38, "brasileirao") == 800_000
    regiao = next(iter(olheiro_base.REGIOES))
    cheio = olheiro_base.custo(regiao, 3)
    assert olheiro_base.custo(regiao, 3, "laliga") == round(cheio / 3 * 0.7 / 10_000) * 10_000 * 3
