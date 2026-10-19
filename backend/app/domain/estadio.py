"""Estádio (v1.5): capacidade, público, ingresso e bilheteria.

A cada jogo em casa, parte da torcida vai ao estádio. A demanda cresce com
a torcida, mas com retorno decrescente (torcida 10× maior não leva 10× mais
gente): ~5 mil pagantes para uma torcida de 200 mil, ~60 mil para 12
milhões. Clássico e boa fase enchem mais; quem não cabe fica de fora.

O técnico escolhe a faixa do ingresso: popular (mais barato, enche o
estádio), normal ou premium (mais caro, menos gente). O preço normal sobe
com o tamanho do clube (clube grande cobra mais caro), de um jeito que, na
média, a bilheteria segue a de antes do estádio (proporcional à torcida).

O público presente é o que empurra o time: o mando de campo vem dele (ver
`mando_de_campo`).

Como a torcida e as finanças, tudo aqui é determinístico: nada de
`random`, para não mexer na sequência aleatória de um mesmo seed.

As constantes ficam juntas para facilitar o balanceamento.
"""

import math
import zlib

# demanda: PUBLICO_REF pagantes para TORCIDA_REF torcedores, no expoente
TORCIDA_REF = 12_500_000
PUBLICO_REF = 60_000
EXPOENTE = 0.6

MULT_CLASSICO = 1.3
POR_JOGO_DA_FASE = 0.04   # por vitória (+) ou derrota (−) nos últimos 5 jogos

FAIXAS = {
    "popular": {
        "nome": "Popular",
        "descricao": "Ingresso barato: estádio cheio e o time empurrado.",
        "preco": 0.6, "demanda": 1.35,
    },
    "normal": {
        "nome": "Normal",
        "descricao": "O preço de sempre.",
        "preco": 1.0, "demanda": 1.0,
    },
    "premium": {
        "nome": "Premium",
        "descricao": "Ingresso caro: menos gente, mais receita por cabeça.",
        "preco": 1.6, "demanda": 0.6,
    },
}
FAIXA_PADRAO = "normal"

# preço normal = PRECO_REF × (torcida / TORCIDA_REF) ^ (1 − EXPOENTE): com a
# demanda no expoente EXPOENTE, a receita fica proporcional à torcida, como
# a bilheteria de antes (0,02 por torcedor por jogo). Calibrado para a liga
# arrecadar o mesmo que antes na primeira temporada (os estádios lotados
# deixam um pouco de gente de fora)
PRECO_REF = 4.05

# capacidade inicial: a demanda típica do clube vezes um fator entre
# CAPACIDADE_MIN e CAPACIDADE_MAX (sai do nome: o mesmo em toda execução),
# em milhares. Uns começam folgados, outros já lotam nos jogos grandes
CAPACIDADE_MIN, CAPACIDADE_MAX = 0.9, 1.3
CAPACIDADE_PISO = 5_000

# mando de campo pelo público presente (antes, pela torcida inteira). O
# público cresce com a torcida no expoente EXPOENTE, então a inclinação em
# público é a da torcida dividida por ele: a mesma escala de antes
MANDO_BASE = 2.5
MANDO_POR_DEZ_VEZES = 0.75 / EXPOENTE
MANDO_MIN, MANDO_MAX = 1.5, 3.5


def demanda_base(torcedores):
    """Quanta gente a torcida leva a um jogo comum, com o ingresso normal."""
    if torcedores <= 0:
        return 0
    return PUBLICO_REF * (torcedores / TORCIDA_REF) ** EXPOENTE


# o meio da liga (3 milhões de torcedores, como na v1.4) dá o mando base
PUBLICO_MEIO = demanda_base(3_000_000)


def capacidade_inicial(nome, torcedores):
    fator = CAPACIDADE_MIN + (CAPACIDADE_MAX - CAPACIDADE_MIN) * (
        zlib.crc32(nome.encode("utf-8")) % 1000 / 999
    )
    lugares = round(demanda_base(torcedores) * fator, -3)
    return max(CAPACIDADE_PISO, int(lugares))


def preco_normal(torcedores):
    if torcedores <= 0:
        return 0.0
    return PRECO_REF * (torcedores / TORCIDA_REF) ** (1 - EXPOENTE)


def preco(clube, faixa=None):
    """Preço do ingresso do clube na faixa (a dele, se não disser)."""
    return preco_normal(clube.torcedores) * FAIXAS[faixa or clube.ingresso]["preco"]


def fator_da_fase(forma):
    ultimos = forma[-5:]
    return 1 + POR_JOGO_DA_FASE * (ultimos.count("V") - ultimos.count("D"))


def demanda(mandante, visitante, faixa=None):
    """Quanta gente quer ver o jogo (antes da capacidade)."""
    classico = (
        visitante.nome in mandante.rivais or mandante.nome in visitante.rivais
    )
    return (
        demanda_base(mandante.torcedores)
        * FAIXAS[faixa or mandante.ingresso]["demanda"]
        * (MULT_CLASSICO if classico else 1)
        * fator_da_fase(mandante.forma)
    )


def publico(mandante, visitante, faixa=None):
    """Pagantes no jogo: a demanda, até a capacidade. Clube sem estádio
    registrado (montado à mão, nos testes): 0."""
    if mandante.capacidade <= 0:
        return 0
    return min(mandante.capacidade, round(demanda(mandante, visitante, faixa)))


def publico_tipico(clube, faixa=None):
    """Público de um jogo comum em casa (sem clássico), na fase atual: o
    que a tela mostra como estimativa. Sem estádio registrado: 0."""
    if clube.capacidade <= 0:
        return 0
    demanda_comum = (
        demanda_base(clube.torcedores)
        * FAIXAS[faixa or clube.ingresso]["demanda"]
        * fator_da_fase(clube.forma)
    )
    return min(clube.capacidade, round(demanda_comum))


def bilheteria(clube, publico_do_jogo):
    return round(publico_do_jogo * preco(clube))


def mando_de_campo(publico_do_jogo):
    """Vantagem do mandante pelo público presente, em pontos de força."""
    if publico_do_jogo <= 0:
        return MANDO_BASE
    mando = MANDO_BASE + MANDO_POR_DEZ_VEZES * math.log10(
        publico_do_jogo / PUBLICO_MEIO
    )
    return min(MANDO_MAX, max(MANDO_MIN, mando))


def ocupacao(publico_do_jogo, capacidade):
    return publico_do_jogo / capacidade if capacidade else 0.0


def motivo_faixa_invalida(faixa):
    if faixa not in FAIXAS:
        return "Faixa de ingresso desconhecida"
    return None


# ampliação (v1.5): obras pagas à vista, uma por vez. O custo por lugar é o
# preço normal do ingresso vezes `jogos` (por isso a obra se paga no mesmo
# tempo em qualquer clube: ~3,5 temporadas de 19 jogos com o lugar novo
# ocupado). Obra maior sai mais barata por lugar, mas demora mais. Cada
# rodada jogada desconta 1 do prazo; a obra que não acabar na temporada
# segue na próxima
OBRAS = {
    "pequena": {
        "nome": "Anel provisório",
        "descricao": "Arquibancada tubular atrás do gol.",
        "lugares": 5_000, "rodadas": 10, "jogos": 70,
    },
    "media": {
        "nome": "Novo setor",
        "descricao": "Um setor inteiro de arquibancada.",
        "lugares": 10_000, "rodadas": 19, "jogos": 65,
    },
    "grande": {
        "nome": "Segundo anel",
        "descricao": "Um anel novo em volta do estádio.",
        "lugares": 20_000, "rodadas": 38, "jogos": 60,
    },
}
OBRA_CUSTO_MINIMO = 50_000

# manutenção, só dos lugares ampliados (os de origem já estão na conta da
# calibração): fração do preço normal por lugar, a cada jogo em casa
MANUTENCAO_POR_LUGAR = 0.15


def custo_da_obra(tipo, torcedores):
    o = OBRAS[tipo]
    return max(OBRA_CUSTO_MINIMO,
               int(round(o["lugares"] * preco_normal(torcedores) * o["jogos"], -3)))


def motivo_obra_bloqueada(clube, tipo):
    if tipo not in OBRAS:
        return "Obra desconhecida"
    if clube.obra_lugares:
        return "Já há uma obra em andamento"
    if clube.dinheiro < custo_da_obra(tipo, clube.torcedores):
        return "Não há caixa para essa obra"
    return None


def iniciar_obra(clube, tipo):
    """Cobra a obra e põe no canteiro. Devolve o custo."""
    custo = custo_da_obra(tipo, clube.torcedores)
    clube.lancar("despesa_estadio", custo)
    clube.obra_lugares = OBRAS[tipo]["lugares"]
    clube.obra_rodadas = OBRAS[tipo]["rodadas"]
    return custo


def avancar_obra(clube):
    """Uma rodada a menos no canteiro. Na última, os lugares entram no
    estádio. Devolve os lugares entregues (0 se a obra não acabou)."""
    if not clube.obra_lugares:
        return 0
    clube.obra_rodadas -= 1
    if clube.obra_rodadas > 0:
        return 0
    lugares = clube.obra_lugares
    clube.capacidade += lugares
    clube.lugares_ampliados += lugares
    clube.obra_lugares = clube.obra_rodadas = 0
    return lugares


def manutencao(clube):
    """Custo de manter os lugares ampliados, por jogo em casa."""
    return round(clube.lugares_ampliados * preco_normal(clube.torcedores)
                 * MANUTENCAO_POR_LUGAR)


# a CPU amplia na virada (v1.5) quando lotou em LOTADOS_PARA_AMPLIAR dos
# jogos em casa da temporada que acabou. Constrói o que falta para um
# clássico caber (sem passar disso; no mínimo a obra pequena) e só se, depois
# de pagar, sobrar uma folha salarial anual em caixa. Como o estádio cresce e
# a falta diminui, a CPU para sozinha
LOTADOS_PARA_AMPLIAR = 8


def obra_da_cpu(clube, lotados):
    """Que obra a CPU faz (tipo), ou None."""
    if clube.capacidade <= 0 or clube.obra_lugares or lotados < LOTADOS_PARA_AMPLIAR:
        return None
    falta = demanda_base(clube.torcedores) * MULT_CLASSICO - clube.capacidade
    por_tamanho = sorted(OBRAS, key=lambda t: OBRAS[t]["lugares"], reverse=True)
    cabem = [t for t in por_tamanho if OBRAS[t]["lugares"] <= falta] or [por_tamanho[-1]]
    folha = sum(j.salario for j in clube.jogadores)
    for tipo in cabem:
        if clube.dinheiro - custo_da_obra(tipo, clube.torcedores) >= folha:
            return tipo
    return None


def cpu_amplia(campeonato, lotados, clube_usuario):
    """Os clubes da CPU que começam uma obra. `lotados`: {nome: jogos em
    casa lotados na temporada anterior}. Devolve [(clube, tipo)]."""
    obras = []
    for clube in campeonato.clubes:
        if clube.nome == clube_usuario:
            continue
        tipo = obra_da_cpu(clube, lotados.get(clube.nome, 0))
        if tipo:
            iniciar_obra(clube, tipo)
            obras.append((clube, tipo))
    return obras
