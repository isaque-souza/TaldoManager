"""Torcida (v1.4): cresce e encolhe com a campanha."""

import io
import random
from contextlib import redirect_stdout

import pytest

from app.domain import caixa, torcida
from app.domain.clube import Clube
from app.domain.temporada import restaurar_estado, snapshot_estado
from scripts.data_loader import carregar_campeonato


def _clube(nome="Teste FC", torcedores=1_000_000, forma=()):
    clube = Clube(nome, "Brasil", 0, torcedores)
    clube.forma = list(forma)
    return clube


def test_vitoria_atrai_derrota_afasta_empate_nao_mexe():
    assert torcida.variacao_do_jogo(2, 1) == torcida.VITORIA > 0
    assert torcida.variacao_do_jogo(0, 1) == torcida.DERROTA < 0
    assert torcida.variacao_do_jogo(1, 1) == 0


def test_goleada_pesa_mais_para_os_dois_lados():
    assert torcida.variacao_do_jogo(4, 0) == pytest.approx(torcida.VITORIA + torcida.GOLEADA)
    assert torcida.variacao_do_jogo(0, 3) == pytest.approx(torcida.DERROTA - torcida.GOLEADA)


def test_sequencia_de_vitorias_empolga():
    sem = torcida.variacao_do_jogo(1, 0, sequencia=2)
    com = torcida.variacao_do_jogo(1, 0, sequencia=3)
    assert com == pytest.approx(sem + torcida.BONUS_SEQUENCIA)


def test_classico_vale_o_dobro():
    assert torcida.variacao_do_jogo(1, 0, classico=True) == 2 * torcida.variacao_do_jogo(1, 0)
    assert torcida.variacao_do_jogo(0, 1, classico=True) == 2 * torcida.variacao_do_jogo(0, 1)


def test_processar_jogo_mexe_nos_dois_clubes():
    casa, fora = _clube("Casa", forma=["V"]), _clube("Fora", forma=["D"])
    torcida.processar_jogo(casa, fora, 2, 0)
    assert casa.torcedores == round(1_000_000 * (1 + torcida.VITORIA))
    assert fora.torcedores == round(1_000_000 * (1 + torcida.DERROTA))


def test_processar_jogo_reconhece_o_classico():
    casa, fora = _clube("Casa", forma=["V"]), _clube("Fora", forma=["D"])
    fora.rivais = {"Casa"}   # basta um dos lados marcar a rivalidade
    torcida.processar_jogo(casa, fora, 1, 0)
    assert casa.torcedores == round(1_000_000 * (1 + 2 * torcida.VITORIA))


def test_sequencia_conta_a_forma_ja_com_o_jogo():
    casa = _clube("Casa", forma=["E", "V", "V", "V"])
    torcida.processar_jogo(casa, _clube("Fora", forma=["D"]), 1, 0)
    assert casa.torcedores == round(
        1_000_000 * (1 + torcida.VITORIA + torcida.BONUS_SEQUENCIA)
    )


def test_torcida_nunca_cai_abaixo_do_minimo():
    clube = _clube(torcedores=torcida.MINIMO)
    torcida.processar_jogo(clube, _clube("Outro"), 0, 5)
    assert clube.torcedores == torcida.MINIMO


def test_fim_de_temporada_pela_posicao():
    assert torcida.variacao_da_posicao(1) > torcida.variacao_da_posicao(4) > 0
    assert torcida.variacao_da_posicao(12) == 0
    assert torcida.variacao_da_posicao(20) < 0

    clubes = [_clube(f"C{i}") for i in range(20)]
    torcida.fim_de_temporada(clubes)
    assert clubes[0].torcedores == round(1_000_000 * (1 + torcida.variacao_da_posicao(1)))
    assert clubes[-1].torcedores < 1_000_000


def test_variacao_percentual():
    assert torcida.variacao_percentual(1_100_000, 1_000_000) == pytest.approx(10)
    assert torcida.variacao_percentual(500, 0) is None


def _temporada(seed=7):
    random.seed(seed)
    campeonato = carregar_campeonato()
    with redirect_stdout(io.StringIO()):
        while campeonato.rodada <= len(campeonato.calendario):
            campeonato.jogar_rodada()
    return campeonato


def test_temporada_inteira_premia_o_topo_e_castiga_o_fundo():
    tabela = _temporada().classificacao()
    campeao, lanterna = tabela[0], tabela[-1]
    assert campeao.torcedores > campeao.torcedores_inicial
    assert lanterna.torcedores < lanterna.torcedores_inicial


def test_torcida_nao_mexe_nos_resultados():
    """Nada aqui sorteia: com a torcida ou sem ela, o mesmo seed dá o mesmo
    campeonato."""
    com = [(c.nome, c.pontos) for c in _temporada(11).classificacao()]
    original = torcida.processar_jogo
    torcida.processar_jogo = lambda *a: None
    try:
        sem = [(c.nome, c.pontos) for c in _temporada(11).classificacao()]
    finally:
        torcida.processar_jogo = original
    assert com == sem


def test_snapshot_guarda_a_torcida():
    random.seed(3)
    campeonato = carregar_campeonato()
    with redirect_stdout(io.StringIO()):
        campeonato.jogar_rodada()
    blob = snapshot_estado(campeonato)

    novo = carregar_campeonato()
    restaurar_estado(novo, blob)
    for antes, depois in zip(campeonato.clubes, novo.clubes):
        assert depois.torcedores == antes.torcedores
        assert depois.torcedores_inicial == antes.torcedores_inicial


def test_balanco_da_torcida_na_caixa():
    msg = caixa.balanco_da_torcida(1_000_000, 1_150_000)
    assert msg["setor"] == "Marketing"
    assert "cresceu 15,0%" in msg["corpo"]
    assert "de 1,0 milhão para 1,1 milhão" in msg["corpo"]
    assert "encolheu" in caixa.balanco_da_torcida(2_000_000, 1_900_000)["corpo"]
    assert "mesmo tamanho" in caixa.balanco_da_torcida(800_000, 800_000)["corpo"]
    assert caixa.balanco_da_torcida(0, 100) is None
