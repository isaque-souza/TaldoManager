"""Número de camisa (v1.1): cada jogador tem o seu, único dentro do clube.

O número é do jogador e vai com ele pela carreira. Ao entrar num clube
(seed, compra, base, saída de graça na virada) ele mantém o número se
estiver livre lá; senão pega o primeiro livre da lista da posição dele —
por isso o goleiro titular da seed é o 1 e o centroavante, o 9.
"""

# números preferidos por posição, na ordem de quem chega primeiro
PREFERENCIAS = {
    "Goleiro": (1, 12, 23, 31, 40),
    "Defesa": (2, 3, 4, 5, 6, 13, 14, 15, 16, 22, 24, 25, 26),
    "Meio-Campo": (8, 10, 5, 6, 15, 16, 17, 18, 20, 21, 28),
    "Atacante": (9, 11, 7, 19, 17, 20, 27, 29),
}

MAIOR_NUMERO = 99


def numero_livre(clube, jogador):
    """Primeiro número livre no clube para a posição do jogador (ignora o
    próprio jogador, que pode já estar no elenco)."""
    usados = {j.numero for j in clube.jogadores if j is not jogador}
    for n in PREFERENCIAS.get(jogador.posicao, ()):
        if n not in usados:
            return n
    return next(n for n in range(1, MAIOR_NUMERO + 1) if n not in usados)


def garantir_numero(clube, jogador):
    """Dá um número ao jogador que entra no clube: mantém o dele se estiver
    livre, senão o primeiro livre da posição."""
    ocupados = {j.numero for j in clube.jogadores if j is not jogador}
    if jogador.numero is None or jogador.numero in ocupados:
        jogador.numero = numero_livre(clube, jogador)


def revisar(clube):
    """Rede de segurança depois de remontar um elenco por fora de
    contratar_jogador (restaurar um save, virada): quem está sem número ou
    repete o de alguém que vem antes no elenco ganha um livre."""
    vistos = set()
    for jogador in clube.jogadores:
        if jogador.numero is None or jogador.numero in vistos:
            jogador.numero = numero_livre(clube, jogador)
        vistos.add(jogador.numero)
