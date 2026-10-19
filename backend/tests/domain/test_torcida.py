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


def test_torcida_nao_sorteia_nada():
    """A torcida muda o mando (e assim os jogos), mas nunca consome a
    sequência aleatória: o mesmo seed segue dando o mesmo campeonato."""
    random.seed(5)
    antes = random.getstate()
    casa, fora = _clube("Casa", forma=["V"] * 3), _clube("Fora", forma=["D"])
    torcida.processar_jogo(casa, fora, 3, 0)
    torcida.fim_de_temporada([casa, fora])
    torcida.mando_de_campo(casa.torcedores)
    assert random.getstate() == antes

    a = [(c.nome, c.pontos, c.torcedores) for c in _temporada(11).classificacao()]
    b = [(c.nome, c.pontos, c.torcedores) for c in _temporada(11).classificacao()]
    assert a == b


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


def test_mando_de_campo_cresce_com_a_torcida():
    pequeno = torcida.mando_de_campo(200_000)
    medio = torcida.mando_de_campo(torcida.MANDO_REFERENCIA)
    grande = torcida.mando_de_campo(12_000_000)
    assert torcida.MANDO_MIN <= pequeno < medio < grande <= torcida.MANDO_MAX
    assert medio == torcida.MANDO_BASE
    # jogar em casa sempre conforta, até com a menor torcida
    assert torcida.mando_de_campo(torcida.MINIMO) == torcida.MANDO_MIN > 0
    # sem torcida registrada, o mando de sempre
    assert torcida.mando_de_campo(0) == torcida.MANDO_BASE


def test_mandante_com_mais_torcida_e_mais_forte():
    from app.domain.jogador import Jogador
    from app.domain.partida import Partida

    casa, fora = _clube("Casa"), _clube("Fora")
    for clube in (casa, fora):
        clube.contratar_jogador(Jogador(f"{clube.nome} 1", 25, "Atacante", 80))

    def vantagem(torcedores):
        casa.torcedores = torcedores
        p = Partida(casa, fora)
        return p.forca_em_campo(casa) - p.forca_em_campo(fora)

    assert vantagem(10_000_000) > vantagem(300_000) > 0


def test_venda_ao_rival_pesa_pela_importancia_do_jogador():
    from app.domain.jogador import Jogador

    casa, rival, neutro = _clube("Casa"), _clube("Rival"), _clube("Neutro")
    casa.rivais = {"Rival"}
    craque = Jogador("Craque", 25, "Atacante", 88)
    titular = Jogador("Titular", 25, "Atacante", 80)
    # gente melhor que o reserva em todas as vagas de ataque
    outros = [Jogador(f"Bom {i}", 25, "Atacante", 75) for i in range(5)]
    reservas = [Jogador("Reserva", 25, "Atacante", 60)]
    for j in (craque, titular, *outros, *reservas):
        casa.contratar_jogador(j)

    assert torcida.revolta_da_venda(casa, neutro, craque) == 0
    assert torcida.revolta_da_venda(casa, rival, craque) == torcida.VENDA_RIVAL_CRAQUE
    assert torcida.revolta_da_venda(casa, rival, titular) == torcida.VENDA_RIVAL_TITULAR
    assert torcida.revolta_da_venda(casa, rival, reservas[-1]) == torcida.VENDA_RIVAL

    assert torcida.reagir_a_venda(casa, neutro, titular) is None
    antes, depois = torcida.reagir_a_venda(casa, rival, craque)
    assert (antes, depois) == (1_000_000, round(1_000_000 * (1 + torcida.VENDA_RIVAL_CRAQUE)))
    assert casa.torcedores == depois
    assert rival.torcedores == round(1_000_000 * (1 + torcida.RIVAL_COMEMORA))


def test_revolta_da_torcida_na_caixa():
    from app.domain.jogador import Jogador

    msg = caixa.revolta_da_torcida(
        Jogador("Fulano", 25, "Atacante", 80), _clube("Rival"), 1_000_000, 950_000,
    )
    assert msg["setor"] == "Marketing"
    assert "perdemos 5% da torcida" in msg["corpo"]


# --- freio: tamanho natural (v1.4) -----------------------------------------

def test_torcida_volta_aos_poucos_ao_tamanho_natural():
    acima, abaixo, igual = _clube("Acima"), _clube("Abaixo"), _clube("Igual")
    acima.torcedores, abaixo.torcedores = 4_000_000, 250_000
    for clube in (acima, abaixo):
        torcida.voltar_ao_natural(clube)
    torcida.voltar_ao_natural(igual)

    # 15% do caminho em escala log: 4× vira 4^0,85, ¼ vira ¼^0,85
    fator = 1 - torcida.VOLTA_AO_NATURAL
    assert acima.torcedores == round(1_000_000 * 4 ** fator)
    assert abaixo.torcedores == round(1_000_000 * 0.25 ** fator)
    assert 1_000_000 < acima.torcedores < 4_000_000
    assert 250_000 < abaixo.torcedores < 1_000_000
    assert igual.torcedores == 1_000_000


def test_sem_tamanho_natural_nao_ha_freio():
    clube = _clube()
    clube.torcedores_base = 0
    clube.torcedores = 3_000_000
    torcida.voltar_ao_natural(clube)
    assert clube.torcedores == 3_000_000


def test_titulo_aumenta_o_tamanho_natural():
    clubes = [_clube(f"C{i}") for i in range(20)]
    torcida.fim_de_temporada(clubes)
    assert clubes[0].torcedores_base == round(1_000_000 * (1 + torcida.TITULO_NATURAL))
    assert all(c.torcedores_base == 1_000_000 for c in clubes[1:])


def test_dinastia_cresce_mas_nao_dispara():
    """Campeão todo ano: com o freio, a torcida se estabiliza no ritmo do
    tamanho natural (+5% por título) em vez de crescer ~16% por ano."""
    campeao = _clube()
    por_ano = 1.11 * (1 + torcida.variacao_da_posicao(1))   # jogos + título
    for _ in range(30):
        torcida._aplicar(campeao, 0.11)   # ~25 vitórias na temporada
        torcida.fim_de_temporada([campeao] + [_clube(f"C{i}") for i in range(19)])
    # sem o freio seriam ~99 mi; com ele, ~8 mi
    assert campeao.torcedores < 1_000_000 * por_ano ** 30 / 10
    # acima do natural (que também cresceu), mas a uns 2×, não 20×
    assert campeao.torcedores_base < campeao.torcedores < 3 * campeao.torcedores_base


def test_snapshot_guarda_o_tamanho_natural():
    campeonato = carregar_campeonato()
    campeonato.clubes[0].torcedores_base = 123_000
    blob = snapshot_estado(campeonato)

    estado = random.getstate()
    try:
        novo = carregar_campeonato()
        restaurar_estado(novo, blob)
    finally:
        random.setstate(estado)
    assert novo.clubes[0].torcedores_base == 123_000


def test_virada_leva_o_tamanho_natural():
    from app.domain.carreira import preparar_nova_temporada

    campeonato = carregar_campeonato()
    clube = campeonato.clubes[0]
    seed = clube.torcedores_base
    finais = [
        {"nome": c.nome, "dinheiro": c.dinheiro, "torcedores": c.torcedores,
         "torcedores_base": 999_000 if c is clube else 0}
        for c in campeonato.clubes
    ]
    jogadores = [
        {"nome": j.nome, "clube": c.nome, "idade": j.idade, "overall": j.overall,
         "potencial": j.potencial, "salario": j.salario,
         "contrato_anos": j.contrato_anos, "multa_rescisoria": j.multa_rescisoria}
        for c in campeonato.clubes for j in c.jogadores
    ]
    novo = preparar_nova_temporada(carregar_campeonato(), finais, jogadores)
    assert novo.clubes[0].torcedores_base == 999_000
    # saves antigos (0): fica o da seed
    assert novo.clubes[1].torcedores_base == campeonato.clubes[1].torcedores_base
    assert seed > 0
