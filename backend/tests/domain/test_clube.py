from app.domain.clube import Clube
from app.domain.jogador import Jogador


def test_criar_clube():
    clube = Clube(
        "FC Taldo",
        "Brasil",
        1000000,
        50000
    )

    assert clube.nome == "FC Taldo"
    assert clube.pais == "Brasil"
    assert clube.dinheiro == 1000000
    assert clube.torcedores == 50000


def test_contratar_jogador():
    clube = Clube(
        "FC Taldo",
        "Brasil",
        1000000
    )

    jogador = Jogador(
        "Louis Silva",
        25,
        "Atacante",
        85
    )

    clube.contratar_jogador(jogador)

    assert jogador in clube.jogadores
    assert len(clube.jogadores) == 1
    assert jogador not in clube.titulares
    assert jogador not in clube.reservas
    
def test_contratar_reserva():
    clube = Clube(
        "FC Taldo",
        "Brasil",
        1000000
    )

    jogador = Jogador(
        "Carlos Silva",
        22,
        "Meio-Campo",
        80
    )

    clube.contratar_reserva(jogador)

    assert jogador in clube.jogadores
    assert jogador in clube.reservas
    assert jogador not in clube.titulares
    assert len(clube.jogadores) == 1
    assert len(clube.reservas) == 1
    
def test_escalar_time():
    clube = Clube(
        "FC Taldo",
        "Brasil",
        1000000
    )

    jogadores = [
        Jogador("Goleiro", 25, "Goleiro", 80),
        Jogador("Defesa 1", 25, "Defesa", 80),
        Jogador("Defesa 2", 25, "Defesa", 80),
        Jogador("Defesa 3", 25, "Defesa", 80),
        Jogador("Defesa 4", 25, "Defesa", 80),
        Jogador("Defesa 5", 25, "Defesa", 70),
        Jogador("Meia 1", 25, "Meio-Campo", 80),
        Jogador("Meia 2", 25, "Meio-Campo", 80),
        Jogador("Meia 3", 25, "Meio-Campo", 80),
        Jogador("Meia 4", 25, "Meio-Campo", 70),
        Jogador("Atacante 1", 25, "Atacante", 80),
        Jogador("Atacante 2", 25, "Atacante", 80),
        Jogador("Atacante 3", 25, "Atacante", 80),
        Jogador("Atacante 4", 25, "Atacante", 70),
    ]

    for jogador in jogadores:
        clube.contratar_jogador(jogador)

    clube.escalar_time()

    assert len(clube.titulares) == 11
    assert len(clube.reservas) == 3

    assert sum(j.posicao == "Goleiro" for j in clube.titulares) == 1
    assert sum(j.posicao == "Defesa" for j in clube.titulares) == 4
    assert sum(j.posicao == "Meio-Campo" for j in clube.titulares) == 3
    assert sum(j.posicao == "Atacante" for j in clube.titulares) == 3
    
def test_escalar_time_escolhe_melhores_jogadores():
    clube = Clube(
        "FC Taldo",
        "Brasil",
        1000000
    )

    jogadores = [
        Jogador("Goleiro Fraco", 25, "Goleiro", 60),
        Jogador("Goleiro Forte", 25, "Goleiro", 90),

        Jogador("Defesa 1", 25, "Defesa", 90),
        Jogador("Defesa 2", 25, "Defesa", 85),
        Jogador("Defesa 3", 25, "Defesa", 80),
        Jogador("Defesa 4", 25, "Defesa", 75),
        Jogador("Defesa Reserva", 25, "Defesa", 60),

        Jogador("Meia 1", 25, "Meio-Campo", 90),
        Jogador("Meia 2", 25, "Meio-Campo", 85),
        Jogador("Meia 3", 25, "Meio-Campo", 80),
        Jogador("Meia Reserva", 25, "Meio-Campo", 60),

        Jogador("Atacante 1", 25, "Atacante", 90),
        Jogador("Atacante 2", 25, "Atacante", 85),
        Jogador("Atacante 3", 25, "Atacante", 80),
        Jogador("Atacante Reserva", 25, "Atacante", 60),
    ]

    for jogador in jogadores:
        clube.contratar_jogador(jogador)

    clube.escalar_time()

    assert jogadores[1] in clube.titulares

    assert jogadores[6] not in clube.titulares
    assert jogadores[6] in clube.reservas

    assert jogadores[8] in clube.titulares

    assert jogadores[10] not in clube.titulares
    assert jogadores[10] in clube.reservas
    
def test_jogador_expulso_nao_entra_na_forca_do_clube():
    clube = Clube(
        "FC Taldo",
        "Brasil",
        1000000
    )

    jogador1 = Jogador(
        "Jogador 1",
        25,
        "Atacante",
        90
    )

    jogador2 = Jogador(
        "Jogador 2",
        25,
        "Atacante",
        60
    )

    jogador1.expulso = True

    clube.contratar_jogador(jogador1)
    clube.contratar_jogador(jogador2)

    clube.titulares = [jogador1, jogador2]

    forca = clube.calcular_forca()

    assert forca == 60
    
def test_jogador_expulso_nao_contribui_para_forca():
    clube = Clube(
        "FC Taldo",
        "Brasil",
        1000000
    )

    jogador_ativo = Jogador(
        "Jogador Ativo",
        25,
        "Atacante",
        80
    )

    jogador_expulso = Jogador(
        "Jogador Expulso",
        25,
        "Atacante",
        80
    )

    jogador_expulso.expulso = True

    clube.titulares = [
        jogador_ativo,
        jogador_expulso
    ]

    forca = clube.calcular_forca()

    assert forca == 80
    
def test_expulsao_aplica_penalidade_na_forca():
    clube = Clube(
        "FC Taldo",
        "Brasil",
        1000000
    )

    jogador = Jogador(
        "Jogador",
        25,
        "Atacante",
        80
    )

    clube.titulares = [jogador]
    clube.penalidade_expulsao = 5

    forca = clube.calcular_forca()

    assert forca == 75
    
def test_duas_expulsoes_acumulam_penalidade():
    clube = Clube(
        "FC Taldo",
        "Brasil",
        1000000
    )

    jogador = Jogador(
        "Jogador",
        25,
        "Atacante",
        80
    )

    clube.titulares = [jogador]
    clube.penalidade_expulsao = 10

    forca = clube.calcular_forca()

    assert forca == 70


# ---------------------------------------------------------------------------
# Tática (postura do técnico)
# ---------------------------------------------------------------------------

def test_tatica_padrao_e_equilibrada_e_neutra():
    clube = Clube("FC Taldo", "Brasil", 1000000)

    assert clube.tatica == "equilibrado"
    assert clube.mod_ataque() == 1.0
    assert clube.mod_defesa() == 1.0


def test_ofensivo_cria_mais_e_concede_mais():
    clube = Clube("FC Taldo", "Brasil", 1000000)
    clube.tatica = "ofensivo"

    assert clube.mod_ataque() > 1.0     # cria mais
    assert clube.mod_defesa() < 1.0     # concede mais


def test_defensivo_cria_menos_e_concede_menos():
    clube = Clube("FC Taldo", "Brasil", 1000000)
    clube.tatica = "defensivo"

    assert clube.mod_ataque() < 1.0
    assert clube.mod_defesa() > 1.0


def test_tatica_desconhecida_cai_no_neutro():
    clube = Clube("FC Taldo", "Brasil", 1000000)
    clube.tatica = "loucura"

    assert clube.mod_ataque() == 1.0
    assert clube.mod_defesa() == 1.0


# ---------------------------------------------------------------------------
# Formação + XI preferido na escalação
# ---------------------------------------------------------------------------

def _elenco(nome="FC Taldo"):
    """2 GK, 6 DEF, 6 MEI, 4 ATA — como no seed."""
    clube = Clube(nome, "Brasil", 1_000_000)
    for posicao, qtd in (("Goleiro", 2), ("Defesa", 6), ("Meio-Campo", 6), ("Atacante", 4)):
        for i in range(qtd):
            clube.contratar_jogador(Jogador(f"{posicao} {i}", 25, posicao, 75))
    return clube


def test_formacao_muda_a_contagem_de_titulares():
    clube = _elenco()
    clube.formacao = "4-4-2"
    clube.escalar_time()

    por_pos = lambda p: sum(1 for j in clube.titulares if j.posicao == p)
    assert por_pos("Goleiro") == 1
    assert por_pos("Defesa") == 4
    assert por_pos("Meio-Campo") == 4
    assert por_pos("Atacante") == 2
    assert len(clube.titulares) == 11


def test_formacao_5_3_2():
    clube = _elenco()
    clube.formacao = "5-3-2"
    clube.escalar_time()

    por_pos = lambda p: sum(1 for j in clube.titulares if j.posicao == p)
    assert (por_pos("Defesa"), por_pos("Meio-Campo"), por_pos("Atacante")) == (5, 3, 2)


def test_formacao_desconhecida_cai_no_4_3_3():
    clube = _elenco()
    clube.formacao = "sei-la"
    clube.escalar_time()

    por_pos = lambda p: sum(1 for j in clube.titulares if j.posicao == p)
    assert (por_pos("Defesa"), por_pos("Meio-Campo"), por_pos("Atacante")) == (4, 3, 3)


def test_xi_preferido_coloca_um_jogador_pior_como_titular():
    clube = _elenco()
    # todos OVR 75; rebaixo um atacante e marco como preferido
    fraco = next(j for j in clube.jogadores if j.posicao == "Atacante")
    fraco.overall = 67

    clube.escalar_time()
    assert fraco not in clube.titulares      # sem preferência, não entra

    clube.xi_preferido = {fraco}
    clube.escalar_time()
    assert fraco in clube.titulares           # com preferência (bônus), joga


def _elenco_completo(clube, extras=()):
    """2 GK, 6 DEF, 4 MEI, 4 ATA de overall 80, mais os `extras`: dá para
    escalar qualquer formação sem improvisar ninguém."""
    for posicao, n in (("Goleiro", 2), ("Defesa", 6), ("Meio-Campo", 4), ("Atacante", 4)):
        for i in range(n):
            clube.contratar_jogador(Jogador(f"{posicao} {i}", 25, posicao, 80))
    for j in extras:
        clube.contratar_jogador(j)


def _xi_sem(clube, *fora):
    """Os 11 que o motor escalaria hoje, menos os `fora`."""
    clube.escalar_time()
    return [j for j in clube.titulares if j not in fora]


def test_xi_do_tecnico_e_respeitado_mesmo_deixando_o_craque_no_banco():
    # o caso real: no 4-4-2 o técnico tira o melhor meia (99) e põe um de 76
    clube = Clube("FC Taldo", "Brasil", 1000000)
    craque = Jogador("Craque", 25, "Meio-Campo", 99)
    reserva = Jogador("Reserva", 25, "Meio-Campo", 76)
    _elenco_completo(clube, [craque, reserva])
    clube.formacao = "4-4-2"
    clube.xi_preferido = set(_xi_sem(clube, craque)) | {reserva}

    clube.escalar_time()
    assert reserva in clube.titulares
    assert craque not in clube.titulares


def test_escolhido_exausto_e_poupado():
    clube = Clube("FC Taldo", "Brasil", 1000000)
    exausto = Jogador("Exausto", 25, "Atacante", 99)
    exausto.energia = 20
    exausto.atualizar_condicao()
    _elenco_completo(clube, [exausto])
    clube.formacao = "4-3-3"
    clube.xi_preferido = set(_xi_sem(clube)) | {exausto}

    clube.escalar_time()
    assert exausto not in clube.titulares
    assert len(clube.titulares) == 11
