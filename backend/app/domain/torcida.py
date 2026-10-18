"""Torcida (v1.4): cresce e encolhe com a campanha.

Cada jogo mexe um pouco no número de torcedores — vitória atrai, derrota
afasta, clássico vale o dobro, goleada e sequência de vitórias dão um
empurrão a mais — e o fim da temporada pesa pela posição final (título é
festa; brigar lá embaixo espanta gente). A torcida vai para a temporada
seguinte e alimenta a bilheteria (`financas.bilheteria`).

Como as finanças, tudo aqui é determinístico, de propósito: nada de
`random`, para não mexer na sequência aleatória e nos resultados de um
mesmo seed.

As constantes ficam juntas para facilitar o balanceamento.
"""

import math

from app.domain import mercado

# por jogo, em fração da torcida atual
VITORIA = 0.003
EMPATE = 0.0
DERROTA = -0.003
GOLEADA = 0.002           # 3+ gols de diferença: a mais para quem goleou,
                          # a menos para quem foi goleado
SEQUENCIA = 3             # vitórias seguidas para empolgar a torcida
BONUS_SEQUENCIA = 0.001
MULT_CLASSICO = 2         # contra o rival, tudo pesa o dobro

# no fim da temporada, pela posição final: [(até a posição, variação)]
POR_POSICAO = (
    (1, 0.05),     # campeão
    (4, 0.02),     # G-4
    (8, 0.01),
    (16, 0.0),
    (20, -0.02),   # Z-4
)

MINIMO = 50_000    # a torcida mais fiel não vai embora

# vender para o rival (v1.4): a torcida não perdoa — e a do rival comemora.
# Quanto mais importante o jogador, maior a revolta
VENDA_RIVAL = -0.02
VENDA_RIVAL_TITULAR = -0.03
VENDA_RIVAL_CRAQUE = -0.05
RIVAL_COMEMORA = 0.01

# mando de campo (v1.4): jogar em casa sempre conforta, e estádio cheio
# empurra mais. Em pontos de "overall" somados à força do mandante; a
# referência é o meio da liga (média geométrica das torcidas da seed), então
# na média o mando segue o de antes e a calibragem do motor não muda
MANDO_BASE = 2.5
MANDO_REFERENCIA = 3_000_000
MANDO_POR_DEZ_VEZES = 0.75   # torcida 10× maior → +0,75 de mando
MANDO_MIN, MANDO_MAX = 1.5, 3.5


def _aplicar(clube, fracao):
    clube.torcedores = max(MINIMO, round(clube.torcedores * (1 + fracao)))


def variacao_do_jogo(gols_pro, gols_contra, classico=False, sequencia=0):
    """Fração que a torcida muda depois de um jogo. `sequencia` = vitórias
    seguidas do clube, contando este jogo."""
    saldo = gols_pro - gols_contra
    if saldo > 0:
        fracao = VITORIA
        if sequencia >= SEQUENCIA:
            fracao += BONUS_SEQUENCIA
    elif saldo < 0:
        fracao = DERROTA
    else:
        fracao = EMPATE
    if abs(saldo) >= 3:
        fracao += GOLEADA if saldo > 0 else -GOLEADA
    return fracao * (MULT_CLASSICO if classico else 1)


def _sequencia_de_vitorias(clube):
    n = 0
    for r in reversed(clube.forma):
        if r != "V":
            break
        n += 1
    return n


def processar_jogo(mandante, visitante, gols_mandante, gols_visitante):
    """Atualiza a torcida dos dois clubes depois do jogo. Chamar com a
    forma já atualizada (a sequência conta este jogo)."""
    classico = (
        visitante.nome in mandante.rivais or mandante.nome in visitante.rivais
    )
    for clube, pro, contra in (
        (mandante, gols_mandante, gols_visitante),
        (visitante, gols_visitante, gols_mandante),
    ):
        _aplicar(clube, variacao_do_jogo(
            pro, contra, classico, _sequencia_de_vitorias(clube)
        ))


def variacao_da_posicao(posicao):
    for ate, fracao in POR_POSICAO:
        if posicao <= ate:
            return fracao
    return POR_POSICAO[-1][1]


def fim_de_temporada(classificacao):
    for posicao, clube in enumerate(classificacao, start=1):
        _aplicar(clube, variacao_da_posicao(posicao))


def mando_de_campo(torcedores):
    """Vantagem do mandante pela torcida. Sem torcida registrada (clubes
    montados à mão, nos testes), o mando de sempre."""
    if torcedores <= 0:
        return MANDO_BASE
    mando = MANDO_BASE + MANDO_POR_DEZ_VEZES * math.log10(
        torcedores / MANDO_REFERENCIA
    )
    return min(MANDO_MAX, max(MANDO_MIN, mando))


def revolta_venda_rival(vendedor, comprador, jogador):
    """Fração que a torcida do `vendedor` perde se o jogador for para o
    `comprador` (0 se não são rivais). Chamar antes da transferência: o
    peso do jogador é medido no elenco de onde ele sai."""
    if not mercado.sao_rivais(vendedor, comprador):
        return 0.0
    if mercado.eh_craque(vendedor, jogador):
        return VENDA_RIVAL_CRAQUE
    if mercado.seria_titular(vendedor, jogador):
        return VENDA_RIVAL_TITULAR
    return VENDA_RIVAL


def vender_ao_rival(vendedor, comprador, jogador):
    """Aplica a revolta (e a festa do rival). Devolve (antes, depois) da
    torcida do vendedor, ou None se não são rivais."""
    fracao = revolta_venda_rival(vendedor, comprador, jogador)
    if not fracao:
        return None
    antes = vendedor.torcedores
    _aplicar(vendedor, fracao)
    _aplicar(comprador, RIVAL_COMEMORA)
    return antes, vendedor.torcedores


def variacao_percentual(atual, inicial):
    """Quanto a torcida mudou na temporada, em % (None sem base)."""
    if not inicial:
        return None
    return (atual / inicial - 1) * 100
