import random

from app.domain.jogador import Jogador


def test_criar_jogador():
    jogador = Jogador(
        "Louis Silva",
        25,
        "Atacante",
        85
    )

    assert jogador.nome == "Louis Silva"
    assert jogador.idade == 25
    assert jogador.posicao == "Atacante"
    assert jogador.overall == 85

def test_nota_media_sem_partidas():
    jogador = Jogador(
        "Teste",
        25,
        "Atacante",
        80
    )

    assert jogador.nota_media() == 0.0


def test_nota_media_com_partidas():
    jogador = Jogador(
        "Teste",
        25,
        "Atacante",
        80
    )

    jogador.partidas = 3
    jogador.soma_nota = 24.75

    assert jogador.nota_media() == 8.25
    
def test_score_escalacao_normal():
    jogador = Jogador(
        "Teste",
        25,
        "Atacante",
        80
    )

    jogador.energia = 100
    jogador.condicao = "Normal"

    assert jogador.score_escalacao() == 95.0


def test_score_escalacao_cansado():
    jogador = Jogador(
        "Teste",
        25,
        "Atacante",
        80
    )

    jogador.energia = 60
    jogador.condicao = "Cansado"

    assert jogador.score_escalacao() == 84.0


def test_score_escalacao_exausto():
    jogador = Jogador(
        "Teste",
        25,
        "Atacante",
        80
    )

    jogador.energia = 30
    jogador.condicao = "Exausto"

    assert jogador.score_escalacao() == 69.5


def test_score_escalacao_preferido_ganha_bonus():
    jogador = Jogador("Teste", 25, "Atacante", 80)
    jogador.energia = 100
    jogador.condicao = "Normal"

    base = jogador.score_escalacao()
    assert jogador.score_escalacao(preferido=True) == base + 12

def test_peso_gol_goleiro_e_defesa():
    goleiro = Jogador("Goleiro", 25, "Goleiro", 80)
    defesa = Jogador("Defesa", 25, "Defesa", 80)

    assert goleiro.peso_gol() == 0
    assert defesa.peso_gol() == 0


def test_peso_gol_atacante_maior_que_meio_campo():
    meia = Jogador("Meia", 25, "Meio-Campo", 90)
    atacante = Jogador("Atacante", 25, "Atacante", 90)

    assert atacante.peso_gol() > meia.peso_gol()


def test_peso_gol_escala_forte_com_o_overall():
    fraco = Jogador("Fraco", 25, "Atacante", 72)
    forte = Jogador("Forte", 25, "Atacante", 88)

    # um atacante muito melhor finaliza bem mais (base para a artilharia)
    assert forte.peso_gol() >= fraco.peso_gol() * 1.6


def test_peso_gol_considera_condicao():
    jogador = Jogador("Atacante", 25, "Atacante", 90)

    normal = jogador.peso_gol()

    jogador.condicao = "Cansado"
    cansado = jogador.peso_gol()

    jogador.condicao = "Exausto"
    exausto = jogador.peso_gol()

    assert exausto < cansado < normal

def test_peso_assistencia_goleiro():
    jogador = Jogador(
        "Goleiro",
        25,
        "Goleiro",
        90
    )

    assert jogador.peso_assistencia() == 1


def test_peso_assistencia_por_posicao():
    atacante = Jogador("Atacante", 25, "Atacante", 80)
    meia = Jogador("Meia", 25, "Meio-Campo", 80)
    defesa = Jogador("Defesa", 25, "Defesa", 80)

    # base da posição + o passe (v1.3; antes, o overall)
    assert atacante.peso_assistencia() == 7 + atacante.atributo("passe") // 8
    assert meia.peso_assistencia() == 13 + meia.atributo("passe") // 8
    assert defesa.peso_assistencia() == 2 + defesa.atributo("passe") // 8
    assert meia.peso_assistencia() > atacante.peso_assistencia() > defesa.peso_assistencia()


def test_peso_assistencia_considera_condicao():
    jogador = Jogador(
        "Meia",
        25,
        "Meio-Campo",
        80
    )

    jogador.condicao = "Cansado"

    assert jogador.peso_assistencia() == 20

    jogador.condicao = "Exausto"

    assert jogador.peso_assistencia() == 16
    
def test_reduzir_energia_realmente_desconta():
    random.seed(0)
    jogador = Jogador("Teste", 25, "Meio-Campo", 80)

    antes = jogador.energia
    jogador.reduzir_energia()

    assert jogador.energia < antes


def test_reduzir_energia_nunca_fica_negativa():
    jogador = Jogador("Teste", 25, "Atacante", 80)
    jogador.energia = 2

    for _ in range(10):
        jogador.reduzir_energia()

    assert jogador.energia == 0
    assert jogador.condicao == "Exausto"


def test_reduzir_energia_atualiza_condicao():
    jogador = Jogador("Teste", 25, "Defesa", 80)
    jogador.energia = 62

    jogador.reduzir_energia()

    assert jogador.energia < 62
    assert jogador.condicao == "Cansado"


def test_resetar_estatisticas_partida():
    jogador = Jogador(
        "Teste",
        25,
        "Atacante",
        80
    )

    jogador.chutes_partida = 5
    jogador.chutes_gol_partida = 3
    jogador.passes_chave_partida = 2
    jogador.dribles_partida = 4
    jogador.desarmes_partida = 3
    jogador.interceptacoes_partida = 2
    jogador.cortes_partida = 1
    jogador.bloqueios_partida = 2
    jogador.defesas_partida = 1
    jogador.gols_sofridos_partida = 2
    jogador.faltas_partida = 4
    jogador.amarelos_partida = 1
    jogador.expulso = True

    jogador.resetar_estatisticas_partida()

    assert jogador.chutes_partida == 0
    assert jogador.chutes_gol_partida == 0
    assert jogador.passes_chave_partida == 0
    assert jogador.dribles_partida == 0
    assert jogador.desarmes_partida == 0
    assert jogador.interceptacoes_partida == 0
    assert jogador.cortes_partida == 0
    assert jogador.bloqueios_partida == 0
    assert jogador.defesas_partida == 0
    assert jogador.gols_sofridos_partida == 0
    assert jogador.faltas_partida == 0
    assert jogador.amarelos_partida == 0
    assert jogador.expulso is False
    