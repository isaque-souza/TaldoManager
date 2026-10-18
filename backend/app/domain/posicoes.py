"""Posições específicas, overall por posição e o desenho das formações
(v1.3).

Cada jogador tem uma posição natural (`Jogador.funcao`: zagueiro, lateral,
volante...) e, às vezes, posições secundárias. Fora delas ele rende menos:
o overall na vaga é o overall menos a perda da tabela abaixo — um volante 80
rende 74 de zagueiro. Numa secundária a perda é pequena.

O motor de partida continua pensando por setor (`Jogador.posicao`: Goleiro,
Defesa, Meio-Campo, Atacante); a posição específica decide quem joga em que
vaga e quanto ele rende ali (Clube.escalar_time / calcular_forca).

Cada formação é desenhada vaga a vaga (DESENHO), como no FIFA/EA FC e no
Football Manager: x é a largura (0 = ponta esquerda, 100 = direita) e y a
profundidade (0 = a própria linha de fundo, 100 = a do adversário). Os
laterais ficam na linha da zaga, um pouco à frente e abertos; o volante,
logo à frente da defesa; o meia central, no meio; o meia-atacante, entre o
meio e o ataque; os pontas, abertos e altos; o segundo atacante, à frente
do meia-atacante e atrás do centroavante.
"""

FUNCOES = (
    "Goleiro", "Zagueiro", "Lateral", "Volante", "Meia central",
    "Meia-atacante", "Ponta", "Segundo atacante", "Centroavante",
)

SETOR = {
    "Goleiro": "Goleiro",
    "Zagueiro": "Defesa",
    "Lateral": "Defesa",
    "Volante": "Meio-Campo",
    "Meia central": "Meio-Campo",
    "Meia-atacante": "Meio-Campo",
    "Ponta": "Atacante",
    "Segundo atacante": "Atacante",
    "Centroavante": "Atacante",
}

SIGLA = {
    "Goleiro": "GOL",
    "Zagueiro": "ZAG",
    "Lateral": "LAT",
    "Volante": "VOL",
    "Meia central": "MC",
    "Meia-atacante": "MEI",
    "Ponta": "PON",
    "Segundo atacante": "SA",
    "Centroavante": "CA",
}

# posição de quem não tem uma definida (saves de antes da v1.3)
PADRAO_DO_SETOR = {
    "Goleiro": "Goleiro",
    "Defesa": "Zagueiro",
    "Meio-Campo": "Meia central",
    "Atacante": "Centroavante",
}

# nomes antigos (saves da primeira versão da v1.3, com um "Meia" só)
NOMES_ANTIGOS = {"Meia": "Meia central"}

# perda de overall jogando fora da posição (simétrica): vizinhos perdem
# pouco, o outro lado do campo perde muito
_PERDA = {
    ("Zagueiro", "Lateral"): 6,
    ("Zagueiro", "Volante"): 6,
    ("Zagueiro", "Meia central"): 12,
    ("Zagueiro", "Meia-atacante"): 16,
    ("Zagueiro", "Ponta"): 18,
    ("Zagueiro", "Segundo atacante"): 18,
    ("Zagueiro", "Centroavante"): 16,
    ("Lateral", "Volante"): 9,
    ("Lateral", "Meia central"): 8,
    ("Lateral", "Meia-atacante"): 12,
    ("Lateral", "Ponta"): 8,
    ("Lateral", "Segundo atacante"): 15,
    ("Lateral", "Centroavante"): 16,
    ("Volante", "Meia central"): 4,
    ("Volante", "Meia-atacante"): 9,
    ("Volante", "Ponta"): 12,
    ("Volante", "Segundo atacante"): 13,
    ("Volante", "Centroavante"): 14,
    ("Meia central", "Meia-atacante"): 4,
    ("Meia central", "Ponta"): 7,
    ("Meia central", "Segundo atacante"): 8,
    ("Meia central", "Centroavante"): 10,
    ("Meia-atacante", "Ponta"): 5,
    ("Meia-atacante", "Segundo atacante"): 3,
    ("Meia-atacante", "Centroavante"): 7,
    ("Ponta", "Segundo atacante"): 5,
    ("Ponta", "Centroavante"): 5,
    ("Segundo atacante", "Centroavante"): 3,
}
PERDA_GOLEIRO = 35        # goleiro na linha ou jogador de linha no gol
PERDA_SECUNDARIA = 2


def _v(funcao, x, y, rotulo=None):
    return (funcao, x, y, rotulo or SIGLA[funcao])


_GOL = _v("Goleiro", 50, 3)
_LINHA_4 = (
    _v("Lateral", 10, 24, "LE"), _v("Zagueiro", 34, 16),
    _v("Zagueiro", 66, 16), _v("Lateral", 90, 24, "LD"),
)
_LINHA_3 = (_v("Zagueiro", 25, 17), _v("Zagueiro", 50, 18), _v("Zagueiro", 75, 17))
# com três zagueiros, os laterais viram alas: bem mais à frente
_LINHA_5 = (
    _v("Lateral", 8, 32, "ALA"), _v("Zagueiro", 28, 17), _v("Zagueiro", 50, 18),
    _v("Zagueiro", 72, 17), _v("Lateral", 92, 32, "ALA"),
)
_MEIAS_ABERTOS = (_v("Ponta", 10, 52, "ME"), _v("Ponta", 90, 52, "MD"))
_PONTAS = (_v("Ponta", 14, 76, "PE"), _v("Ponta", 86, 76, "PD"))
_DOIS_CA = (_v("Centroavante", 36, 85), _v("Centroavante", 64, 85))
_UM_CA = (_v("Centroavante", 50, 86),)

# vagas de linha de cada formação, da defesa para o ataque
DESENHO = {
    "4-3-3": _LINHA_4 + (
        _v("Volante", 50, 36), _v("Meia central", 30, 50), _v("Meia central", 70, 50),
        _PONTAS[0], _UM_CA[0], _PONTAS[1],
    ),
    "4-4-2": _LINHA_4 + (
        _MEIAS_ABERTOS[0], _v("Meia central", 36, 44), _v("Meia central", 64, 44),
        _MEIAS_ABERTOS[1],
    ) + _DOIS_CA,
    "4-2-3-1": _LINHA_4 + (
        _v("Volante", 36, 36), _v("Volante", 64, 36),
        _v("Ponta", 12, 68, "PE"), _v("Meia-atacante", 50, 62), _v("Ponta", 88, 68, "PD"),
    ) + _UM_CA,
    "4-1-2-1-2": _LINHA_4 + (   # losango
        _v("Volante", 50, 34), _v("Meia central", 26, 48), _v("Meia central", 74, 48),
        _v("Meia-atacante", 50, 62),
    ) + _DOIS_CA,
    "4-4-1-1": _LINHA_4 + (
        _MEIAS_ABERTOS[0], _v("Meia central", 36, 44), _v("Meia central", 64, 44),
        _MEIAS_ABERTOS[1], _v("Segundo atacante", 50, 68),
    ) + (_v("Centroavante", 50, 87),),
    "4-5-1": _LINHA_4 + (
        _v("Volante", 50, 34), _v("Ponta", 10, 56, "ME"), _v("Meia central", 32, 50),
        _v("Meia central", 68, 50), _v("Ponta", 90, 56, "MD"),
    ) + _UM_CA,
    "4-2-4": _LINHA_4 + (
        _v("Volante", 36, 40), _v("Volante", 64, 40),
        _v("Ponta", 12, 74, "PE"), _DOIS_CA[0], _DOIS_CA[1], _v("Ponta", 88, 74, "PD"),
    ),
    "3-5-2": _LINHA_3 + (
        _v("Lateral", 8, 46, "ALA"), _v("Volante", 50, 34), _v("Meia central", 32, 50),
        _v("Meia central", 68, 50), _v("Lateral", 92, 46, "ALA"),
    ) + _DOIS_CA,
    "3-4-3": _LINHA_3 + (
        _v("Lateral", 8, 48, "ALA"), _v("Meia central", 36, 44),
        _v("Meia central", 64, 44), _v("Lateral", 92, 48, "ALA"),
        _v("Ponta", 16, 76, "PE"), _UM_CA[0], _v("Ponta", 84, 76, "PD"),
    ),
    "5-3-2": _LINHA_5 + (
        _v("Volante", 50, 38), _v("Meia central", 30, 52), _v("Meia central", 70, 52),
    ) + _DOIS_CA,
    "5-4-1": _LINHA_5 + (
        _v("Ponta", 12, 56, "ME"), _v("Meia central", 36, 48),
        _v("Meia central", 64, 48), _v("Ponta", 88, 56, "MD"),
    ) + _UM_CA,
}

VAGAS = {f: tuple(v[0] for v in d) for f, d in DESENHO.items()}

# {formação: (defesa, meio, ataque)} contados pelo setor de cada vaga (o
# mercado usa para saber quantos titulares a formação pede por setor)
SETORES_DA_FORMACAO = {
    f: tuple(
        sum(SETOR[v] == s for v in vagas_)
        for s in ("Defesa", "Meio-Campo", "Atacante")
    )
    for f, vagas_ in VAGAS.items()
}


# o máximo que alguma formação pede de cada posição: com isso no elenco,
# qualquer formação sai sem improvisar
MINIMO_POR_POSICAO = {
    f: max((("Goleiro",) + vagas_).count(f) for vagas_ in VAGAS.values())
    for f in FUNCOES
}


def nome_atual(funcao):
    """A posição com o nome de hoje (saves antigos têm "Meia")."""
    return NOMES_ANTIGOS.get(funcao, funcao)


def perda(natural, vaga, secundarias=()):
    """Quanto de overall a posição `natural` perde jogando na `vaga`."""
    if vaga == natural:
        return 0
    if "Goleiro" in (vaga, natural):
        return PERDA_GOLEIRO
    if vaga in secundarias:
        return PERDA_SECUNDARIA
    return _PERDA.get((natural, vaga)) or _PERDA[(vaga, natural)]


def vagas(formacao):
    """Goleiro + as vagas de linha da formação (4-3-3 se desconhecida)."""
    return ("Goleiro",) + VAGAS.get(formacao, VAGAS["4-3-3"])


def desenho(formacao):
    """Goleiro + as vagas de linha, cada uma (posição, x, y, rótulo)."""
    return (_GOL,) + DESENHO.get(formacao, DESENHO["4-3-3"])


def do_setor(setor, menos=None):
    """As posições do `setor` (sem `menos`)."""
    return tuple(f for f in FUNCOES if SETOR[f] == setor and f != menos)


def menor_custo(custos):
    """Atribuição de menor custo total (algoritmo húngaro). `custos` é uma
    matriz n × m com n <= m (linhas: quem precisa de par). Devolve, para
    cada linha, o índice da coluna escolhida. Determinística."""
    n, m = len(custos), len(custos[0])
    inf = float("inf")
    u, v = [0.0] * (n + 1), [0.0] * (m + 1)
    par, caminho = [0] * (m + 1), [0] * (m + 1)
    for i in range(1, n + 1):
        par[0] = i
        j0 = 0
        menor = [inf] * (m + 1)
        usado = [False] * (m + 1)
        while True:
            usado[j0] = True
            i0, delta, j1 = par[j0], inf, 0
            for j in range(1, m + 1):
                if usado[j]:
                    continue
                atual = custos[i0 - 1][j - 1] - u[i0] - v[j]
                if atual < menor[j]:
                    menor[j], caminho[j] = atual, j0
                if menor[j] < delta:
                    delta, j1 = menor[j], j
            for j in range(m + 1):
                if usado[j]:
                    u[par[j]] += delta
                    v[j] -= delta
                else:
                    menor[j] -= delta
            j0 = j1
            if par[j0] == 0:
                break
        while j0:
            j1 = caminho[j0]
            par[j0] = par[j1]
            j0 = j1
    escolha = [None] * n
    for j in range(1, m + 1):
        if par[j]:
            escolha[par[j] - 1] = j - 1
    return escolha
