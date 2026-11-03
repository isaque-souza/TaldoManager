"""Regras financeiras dos clubes (v0.7; dinheiro por liga na v2.5).

Toda rodada cada clube recebe a cota de TV e paga a folha salarial; o
mandante ainda fica com a bilheteria (público × ingresso, v1.5; ver
`app.domain.estadio`). No fim da temporada sai a premiação
pela posição final.

O dinheiro da liga (v2.5) segue o modelo da Premier League real: a maior
parte é igual para todos (`PARTE_IGUAL`), uma parte vem da audiência (a
torcida do clube perto da maior da liga, `AUDIENCIA_MAX`) e o mérito é
linear pela posição (`MERITO_DEGRAU`): o campeão leva pouco mais que o
vice, e o último ainda recebe ~60% do que o campeão recebe. Cada liga tem o
seu tamanho (`PESO_LIGA`): a mesma posição paga mais numa liga rica.

Tudo aqui é determinístico, de propósito: nada de `random`. Se as finanças
sorteassem algo, consumiriam números da sequência aleatória e mudariam todos
os resultados das partidas para um mesmo seed. Isso também deixa o histórico
do caixa reconstruível a partir das partidas salvas.

As constantes ficam juntas para facilitar o balanceamento.
"""

from app.domain import diretoria, emprestimo, estadio

BILHETERIA_POR_TORCEDOR = 0.02     # por jogo em casa, sem estádio registrado

# a versão da economia (v2.5) vai na simulação: um save em andamento da v1
# termina a temporada com as regras antigas e passa para a nova na virada
ECONOMIA_ATUAL = 2

# economia v1 (até a v2.4)
COTA_TV_V1 = 1_500_000             # igual para todos, dividida pelas rodadas
PREMIO_CAMPEAO_V1 = 10_000_000
PREMIO_DEGRAU_V1 = 500_000

# o tamanho de cada liga: multiplica a TV e o mérito (Premier = 1,0)
PESO_LIGA = {"premier": 1.0, "taldo": 0.8}
PESO_PADRAO = 0.6                  # liga sem peso definido

# na liga de peso 1,0, por temporada
PARTE_IGUAL = 8_000_000            # TV: igual para todos, dividida pelas rodadas
AUDIENCIA_MAX = 3_000_000          # TV: o clube de maior torcida da liga
MERITO_DEGRAU = 400_000            # prêmio: cada posição acima vale isto
# patrocínio e receita comercial: o elenco mais forte da liga e a maior
# torcida atraem mais (como Real Madrid e City no mundo real). Sem isso, os
# clubes grandes não pagariam a folha das estrelas
PATROCINIO_FORCA = 18_000_000      # o 1º do ranking de força (cai ao quadrado)
PATROCINIO_TORCIDA = 4_000_000     # a maior torcida (raiz, como a audiência)


def economia_do_save(sim):
    """A versão das regras de dinheiro de uma linha de `simulacao`; saves
    de antes da coluna são da v1."""
    try:
        return sim["economia"] or 1
    except (KeyError, IndexError):
        return 1


def peso(liga):
    return PESO_LIGA.get(liga, PESO_PADRAO)


def cota_tv_temporada(liga="taldo"):
    """A parte igual da TV, por temporada."""
    return round(PARTE_IGUAL * peso(liga))


def cota_tv_rodada(total_rodadas, liga="taldo"):
    return round(cota_tv_temporada(liga) / total_rodadas)


def audiencia_temporada(torcedores, maior_torcida, liga="taldo"):
    """A parte da TV que vem da audiência: a raiz da torcida do clube perto
    da maior da liga (metade da maior torcida rende ~71% do máximo)."""
    if not maior_torcida or torcedores <= 0:
        return 0
    return round(AUDIENCIA_MAX * peso(liga) * min(1.0, torcedores / maior_torcida) ** 0.5)


def bilheteria(clube, publico=None):
    """Com público (clube com estádio), pagantes × ingresso; sem, pela
    torcida inteira, como antes da v1.5."""
    if publico:
        return estadio.bilheteria(clube, publico)
    return round(clube.torcedores * BILHETERIA_POR_TORCEDOR)


def folha_salarial(clube, cedidos=0):
    """Soma dos salários do elenco atual, por temporada. Calculada na hora:
    quando o elenco mudar (transferências), a folha acompanha. De quem veio
    emprestado entra só a parte combinada; `cedidos` é o que o clube ainda
    paga pelos que emprestou (v1.7)."""
    return sum(emprestimo.salario_do_tomador(j) for j in clube.jogadores) + cedidos


def salarios_cedidos(clubes):
    """{clube de origem: o que ainda paga pelos emprestados}, por temporada."""
    cedidos = {}
    for clube in clubes:
        for j in clube.jogadores:
            if j.emprestimo:
                de = j.emprestimo["de"]
                cedidos[de] = cedidos.get(de, 0) + emprestimo.salario_do_cedente(j)
    return cedidos


def salarios_rodada(clube, total_rodadas, cedidos=0):
    return round(folha_salarial(clube, cedidos) / total_rodadas)


def patrocinio_temporada(ranking, clubes, torcedores, maior_torcida, liga="taldo"):
    """O patrocínio da temporada: o ranking de força na liga (1 = o mais
    forte) pesa ao quadrado — o topo leva muito mais que o meio — e a
    torcida perto da maior da liga entra pela raiz."""
    forca = ((clubes - ranking) / (clubes - 1)) ** 2 if clubes > 1 else 1.0
    torcida = min(1.0, torcedores / maior_torcida) ** 0.5 if maior_torcida and torcedores > 0 else 0
    return round(peso(liga) * (PATROCINIO_FORCA * forca + PATROCINIO_TORCIDA * torcida))


def premiacao(posicao, liga="taldo", clubes=20, economia=ECONOMIA_ATUAL):
    """O mérito pela posição final: linear, o último leva um degrau."""
    if economia < 2:
        return max(PREMIO_DEGRAU_V1, PREMIO_CAMPEAO_V1 - (posicao - 1) * PREMIO_DEGRAU_V1)
    return round(MERITO_DEGRAU * peso(liga) * max(1, clubes + 1 - posicao))


def processar_rodada(confrontos, total_rodadas, publicos=None, economia=ECONOMIA_ATUAL):
    """Lança as receitas e despesas de uma rodada. `confrontos` é a lista de
    pares (mandante, visitante) do calendário; `publicos`, os pagantes de
    cada mandante ({nome: público}, v1.5); `economia`, a versão das regras
    do save (v2.5)."""

    publicos = publicos or {}
    cedidos = salarios_cedidos([c for par in confrontos for c in par])
    # a maior torcida de cada liga, entre quem joga a rodada (todos jogam)
    maior = {}
    por_liga = {}
    for par in confrontos:
        for c in par:
            maior[c.liga] = max(maior.get(c.liga, 0), c.torcedores)
            por_liga.setdefault(c.liga, []).append(c)
    ranking = {}
    if economia >= 2:
        for cs in por_liga.values():
            ranking.update({nome: (pos, len(cs)) for nome, pos in diretoria.ranking_de_forca(cs).items()})

    for mandante, visitante in confrontos:
        mandante.lancar(
            "receita_bilheteria", bilheteria(mandante, publicos.get(mandante.nome))
        )
        if mandante.lugares_ampliados:
            mandante.lancar("despesa_estadio", estadio.manutencao(mandante))
        for clube in (mandante, visitante):
            if economia < 2:
                clube.lancar("receita_tv", round(COTA_TV_V1 / total_rodadas))
            else:
                clube.lancar("receita_tv", cota_tv_rodada(total_rodadas, clube.liga) + round(
                    audiencia_temporada(clube.torcedores, maior[clube.liga], clube.liga) / total_rodadas
                ))
                pos, n = ranking[clube.nome]
                clube.lancar("receita_patrocinio", round(
                    patrocinio_temporada(pos, n, clube.torcedores, maior[clube.liga], clube.liga)
                    / total_rodadas
                ))
            clube.lancar("despesa_salarios", salarios_rodada(
                clube, total_rodadas, cedidos.get(clube.nome, 0),
            ))


def pagar_premiacao(classificacao, economia=ECONOMIA_ATUAL):
    """`classificacao`: a tabela de UMA liga, do 1º ao último."""
    for posicao, clube in enumerate(classificacao, start=1):
        clube.lancar("receita_premiacao", premiacao(
            posicao, clube.liga, len(classificacao), economia,
        ))


def migrar_salarios_v1(jogadores):
    """Na virada de um save da economia v1 para a v2: os contratos
    assinados na escala antiga sobem para a nova. Quem já assinou na escala
    nova (no fim da temporada v1) ganha mais de 2× a referência antiga e
    fica como está."""
    from app.domain.jogador import Jogador

    for j in jogadores:
        antiga = Jogador.salario_de_mercado_v1(j.overall)
        if j.salario and j.salario <= 2 * antiga:
            fator = Jogador.salario_de_mercado(j.overall) / antiga
            j.salario = max(1_000, round(j.salario * fator / 1_000) * 1_000)
