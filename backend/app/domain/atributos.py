"""Atributos do jogador (v1.3), como os seis do FIFA/EA FC.

Jogador de linha: Velocidade, Finalização, Passe, Drible, Marcação e
Físico. Goleiro: Reflexos e Posicionamento.

Cada atributo é o overall + o perfil da posição + o estilo do jogador:

- o perfil diz o que a posição pede (o centroavante finaliza, o zagueiro
  marca, o ponta corre e dribla...);
- o estilo são pequenas variações individuais, fixas, tiradas do nome do
  jogador (hash, não sorteio): dois centroavantes de 85 jogam diferente, o
  mesmo jogador é igual em qualquer save, e nada precisa ser guardado.

Por acompanhar o overall, os atributos evoluem com ele na carreira.
"""

import hashlib
from functools import lru_cache

from app.domain import posicoes

LINHA = ("velocidade", "finalizacao", "passe", "drible", "marcacao", "fisico")
GOLEIRO = ("reflexos", "posicionamento")

SIGLA = {
    "velocidade": "VEL", "finalizacao": "FIN", "passe": "PAS",
    "drible": "DRI", "marcacao": "MAR", "fisico": "FIS",
    "reflexos": "REF", "posicionamento": "POS",
}

NOME = {
    "velocidade": "Velocidade", "finalizacao": "Finalização", "passe": "Passe",
    "drible": "Drible", "marcacao": "Marcação", "fisico": "Físico",
    "reflexos": "Reflexos", "posicionamento": "Posicionamento",
}

# o que cada posição pede, em pontos acima (ou abaixo) do overall, na ordem
# de LINHA (VEL, FIN, PAS, DRI, MAR, FIS)
PERFIL = {
    "Zagueiro":         (-6, -25, -10, -15,   6,   5),
    "Lateral":          ( 5, -18,  -2,  -3,   2,   0),
    "Volante":          (-5, -15,   2,  -6,   5,   4),
    "Meia central":     (-3,  -6,   5,   2,  -4,   0),
    "Meia-atacante":    ( 0,   2,   5,   5, -20,  -6),
    "Ponta":            ( 7,   0,  -2,   5, -22,  -6),
    "Segundo atacante": ( 2,   3,   2,   4, -22,  -4),
    "Centroavante":     ( 0,   6,  -8,   0, -25,   4),
}
PERFIL_GOLEIRO = (2, 0)   # REF, POS

ESTILO_MAX = 6      # variação individual de cada atributo, para mais ou menos
MINIMO, MAXIMO = 20, 99


@lru_cache(maxsize=4096)
def _estilo(nome, quantos):
    """Variações individuais do jogador, de −ESTILO_MAX a +ESTILO_MAX, com
    soma ~0 (o estilo muda o jeito, não o nível). Saem do nome: as mesmas
    em qualquer save."""
    bruto = hashlib.sha256(nome.encode("utf-8")).digest()
    valores = [bruto[i] % (2 * ESTILO_MAX + 1) - ESTILO_MAX for i in range(quantos)]
    media = sum(valores) / quantos
    return tuple(round(v - media) for v in valores)


def _limitar(valor):
    return max(MINIMO, min(MAXIMO, valor))


def calcular(nome, posicao, funcao, overall):
    """{atributo: valor} a partir dos dados do jogador (de um Jogador ou de
    uma linha do banco). Goleiro tem os de goleiro; sem posição específica
    (saves antigos), a padrão do setor."""
    if posicao == "Goleiro":
        nomes, perfil = GOLEIRO, PERFIL_GOLEIRO
    else:
        funcao = posicoes.nome_atual(funcao or posicoes.PADRAO_DO_SETOR[posicao])
        nomes, perfil = LINHA, PERFIL[funcao]
    estilo = _estilo(nome, len(nomes))
    return {a: _limitar(overall + p + e) for a, p, e in zip(nomes, perfil, estilo)}


def de(jogador):
    """{atributo: valor} do jogador (os de goleiro, se ele é goleiro)."""
    return calcular(jogador.nome, jogador.posicao, jogador.funcao, jogador.overall)
