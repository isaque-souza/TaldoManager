"""Posições específicas e overall por posição (v1.3).

Cada jogador tem uma posição natural (`Jogador.funcao`: zagueiro, lateral,
volante...) e, às vezes, posições secundárias. Fora delas ele rende menos:
o overall na vaga é o overall menos a perda da tabela abaixo — um volante 80
rende 74 de zagueiro. Numa secundária a perda é pequena.

O motor de partida continua pensando por setor (`Jogador.posicao`: Goleiro,
Defesa, Meio-Campo, Atacante); a posição específica decide quem joga em que
vaga e quanto ele rende ali (Clube.escalar_time / calcular_forca).
"""

FUNCOES = (
    "Goleiro", "Zagueiro", "Lateral", "Volante", "Meia", "Ponta",
    "Centroavante",
)

SETOR = {
    "Goleiro": "Goleiro",
    "Zagueiro": "Defesa",
    "Lateral": "Defesa",
    "Volante": "Meio-Campo",
    "Meia": "Meio-Campo",
    "Ponta": "Atacante",
    "Centroavante": "Atacante",
}

SIGLA = {
    "Goleiro": "GOL",
    "Zagueiro": "ZAG",
    "Lateral": "LAT",
    "Volante": "VOL",
    "Meia": "MEI",
    "Ponta": "PON",
    "Centroavante": "CA",
}

# posição de quem não tem uma definida (saves de antes da v1.3)
PADRAO_DO_SETOR = {
    "Goleiro": "Goleiro",
    "Defesa": "Zagueiro",
    "Meio-Campo": "Meia",
    "Atacante": "Centroavante",
}

# perda de overall jogando fora da posição (simétrica): vizinhos perdem
# pouco, o outro lado do campo perde muito
_PERDA = {
    ("Zagueiro", "Lateral"): 6,
    ("Zagueiro", "Volante"): 6,
    ("Zagueiro", "Meia"): 14,
    ("Zagueiro", "Ponta"): 18,
    ("Zagueiro", "Centroavante"): 16,
    ("Lateral", "Volante"): 9,
    ("Lateral", "Meia"): 10,
    ("Lateral", "Ponta"): 8,
    ("Lateral", "Centroavante"): 16,
    ("Volante", "Meia"): 4,
    ("Volante", "Ponta"): 12,
    ("Volante", "Centroavante"): 14,
    ("Meia", "Ponta"): 5,
    ("Meia", "Centroavante"): 7,
    ("Ponta", "Centroavante"): 5,
}
PERDA_GOLEIRO = 35        # goleiro na linha ou jogador de linha no gol
PERDA_SECUNDARIA = 2

# vagas de cada formação, da defesa para o ataque. Batem com
# Clube.FORMACOES (defensores, meias, atacantes) por setor.
VAGAS = {
    "4-4-2": ("Zagueiro",) * 2 + ("Lateral",) * 2
             + ("Volante",) * 2 + ("Meia",) * 2 + ("Centroavante",) * 2,
    "4-3-3": ("Zagueiro",) * 2 + ("Lateral",) * 2
             + ("Volante",) + ("Meia",) * 2 + ("Ponta",) * 2 + ("Centroavante",),
    "4-5-1": ("Zagueiro",) * 2 + ("Lateral",) * 2
             + ("Volante",) * 2 + ("Meia",) * 3 + ("Centroavante",),
    "4-2-4": ("Zagueiro",) * 2 + ("Lateral",) * 2
             + ("Volante",) * 2 + ("Ponta",) * 2 + ("Centroavante",) * 2,
    "3-5-2": ("Zagueiro",) * 3
             + ("Volante",) * 2 + ("Meia",) * 3 + ("Centroavante",) * 2,
    "3-4-3": ("Zagueiro",) * 3
             + ("Volante",) * 2 + ("Meia",) * 2 + ("Ponta",) * 2 + ("Centroavante",),
    "5-3-2": ("Zagueiro",) * 3 + ("Lateral",) * 2
             + ("Volante",) + ("Meia",) * 2 + ("Centroavante",) * 2,
    "5-4-1": ("Zagueiro",) * 3 + ("Lateral",) * 2
             + ("Volante",) * 2 + ("Meia",) * 2 + ("Centroavante",),
}


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
