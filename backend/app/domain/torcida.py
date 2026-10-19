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

from app.domain import fama, mercado

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

# freio (v1.4): no fim da temporada a torcida volta 15% do caminho (em
# escala log) até o tamanho natural do clube, que cresce 5% a cada título.
# Sem ele, a vantagem se acumulava sem limite: em 12 temporadas a liga
# dobrava (87 → 171 mi) e o Galaxy ia de 11 a 56 mi. Com ele, a liga fica
# em ~108 mi e uma dinastia ainda dobra a torcida (11 → 25 mi)
VOLTA_AO_NATURAL = 0.15
TITULO_NATURAL = 0.05

# vender para o rival (v1.4): a torcida não perdoa — e a do rival comemora.
# Quanto mais importante o jogador, maior a revolta
VENDA_RIVAL = -0.02
VENDA_RIVAL_TITULAR = -0.03
VENDA_RIVAL_CRAQUE = -0.05
RIVAL_COMEMORA = 0.01
# vender um ídolo, para qualquer clube, também dói; para o rival, soma
VENDA_IDOLO = -0.03

# campanhas de marketing (v1.4): o técnico gasta caixa para atrair gente.
# O custo é por torcedor novo e sobe com o tamanho da campanha (retorno
# decrescente). Cada torcedor rende ~0,38 por temporada de bilheteria
# (BILHETERIA_POR_TORCEDOR × 19 jogos em casa): a campanha se paga em 2 a 3
# temporadas, fora o empurrão no mando de campo
CAMPANHAS = {
    "redes": {
        "nome": "Ação nas redes sociais",
        "descricao": "Vídeos dos bastidores e promoções online.",
        "ganho": 0.01, "custo_por_torcedor": 0.8,
    },
    "cidade": {
        "nome": "Campanha na cidade",
        "descricao": "Outdoors, escolinhas e ingresso popular.",
        "ganho": 0.03, "custo_por_torcedor": 1.0,
    },
    "nacional": {
        "nome": "Campanha nacional",
        "descricao": "Comercial na TV e excursão pelo país.",
        "ganho": 0.06, "custo_por_torcedor": 1.3,
    },
}
CAMPANHA_CUSTO_MINIMO = 5_000     # só para não sair de graça
CAMPANHAS_POR_TURNO = 1


def custo_da_campanha(tipo, torcedores):
    c = CAMPANHAS[tipo]
    novos = torcedores * c["ganho"]
    return max(CAMPANHA_CUSTO_MINIMO, int(round(novos * c["custo_por_torcedor"], -3)))


def turno(rodada, total_rodadas):
    """1 no primeiro turno, 2 no segundo (rodada = a próxima a jogar)."""
    return 1 if rodada <= total_rodadas // 2 else 2


def motivo_campanha_bloqueada(clube, tipo, feitas_no_turno):
    if tipo not in CAMPANHAS:
        return "Campanha desconhecida"
    if feitas_no_turno >= CAMPANHAS_POR_TURNO:
        return "Já houve uma campanha neste turno"
    if clube.dinheiro < custo_da_campanha(tipo, clube.torcedores):
        return "Não há caixa para essa campanha"
    return None


def lancar_campanha(clube, tipo):
    """Cobra e aplica a campanha. Devolve (custo, antes, depois)."""
    custo = custo_da_campanha(tipo, clube.torcedores)
    antes = clube.torcedores
    clube.lancar("despesa_marketing", custo)
    _aplicar(clube, CAMPANHAS[tipo]["ganho"])
    return custo, antes, clube.torcedores


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
    """Pela posição final e pelos ídolos do elenco, e depois o freio rumo ao
    tamanho natural (v1.4). Chamar depois de `fama.fim_de_temporada`."""
    for posicao, clube in enumerate(classificacao, start=1):
        _aplicar(clube, variacao_da_posicao(posicao) + fama.bonus_torcida(clube))
        if posicao == 1:
            clube.torcedores_base = round(clube.torcedores_base * (1 + TITULO_NATURAL))
        voltar_ao_natural(clube)


def voltar_ao_natural(clube):
    """A torcida anda `VOLTA_AO_NATURAL` do caminho (em log) até o tamanho
    natural: quem está acima perde um pouco, quem está abaixo recupera.
    Sem tamanho natural registrado (clubes montados à mão), nada muda."""
    base = clube.torcedores_base
    if base <= 0 or clube.torcedores <= 0:
        return
    log = math.log(clube.torcedores)
    log -= VOLTA_AO_NATURAL * (log - math.log(base))
    clube.torcedores = max(MINIMO, round(math.exp(log)))


def mando_de_campo(torcedores):
    """Vantagem do mandante pela torcida. Sem torcida registrada (clubes
    montados à mão, nos testes), o mando de sempre."""
    if torcedores <= 0:
        return MANDO_BASE
    mando = MANDO_BASE + MANDO_POR_DEZ_VEZES * math.log10(
        torcedores / MANDO_REFERENCIA
    )
    return min(MANDO_MAX, max(MANDO_MIN, mando))


def revolta_da_venda(vendedor, comprador, jogador):
    """Fração que a torcida do `vendedor` perde se o jogador for para o
    `comprador` (0 se ele não é ídolo e os clubes não são rivais). Chamar
    antes da transferência: o peso do jogador é medido no elenco de onde
    ele sai."""
    fracao = VENDA_IDOLO if fama.idolo(jogador) else 0.0
    if mercado.sao_rivais(vendedor, comprador):
        if mercado.eh_craque(vendedor, jogador):
            fracao += VENDA_RIVAL_CRAQUE
        elif mercado.seria_titular(vendedor, jogador):
            fracao += VENDA_RIVAL_TITULAR
        else:
            fracao += VENDA_RIVAL
    return fracao


def reagir_a_venda(vendedor, comprador, jogador):
    """Aplica a revolta (e, se for o rival, a festa dele). Devolve (antes,
    depois) da torcida do vendedor, ou None se a torcida não ligou."""
    fracao = revolta_da_venda(vendedor, comprador, jogador)
    if not fracao:
        return None
    antes = vendedor.torcedores
    _aplicar(vendedor, fracao)
    if mercado.sao_rivais(vendedor, comprador):
        _aplicar(comprador, RIVAL_COMEMORA)
    return antes, vendedor.torcedores


def variacao_percentual(atual, inicial):
    """Quanto a torcida mudou na temporada, em % (None sem base)."""
    if not inicial:
        return None
    return (atual / inicial - 1) * 100
