"""Regras financeiras dos clubes (v0.7).

Toda rodada cada clube recebe a cota de TV e paga a folha salarial; o
mandante ainda fica com a bilheteria (público × ingresso, v1.5; ver
`app.domain.estadio`). No fim da temporada sai a premiação
pela posição final.

Tudo aqui é determinístico, de propósito: nada de `random`. Se as finanças
sorteassem algo, consumiriam números da sequência aleatória e mudariam todos
os resultados das partidas para um mesmo seed. Isso também deixa o histórico
do caixa reconstruível a partir das partidas salvas.

As constantes ficam juntas para facilitar o balanceamento.
"""

from app.domain import estadio

COTA_TV_TEMPORADA = 1_500_000      # igual para todos, dividida pelas rodadas
BILHETERIA_POR_TORCEDOR = 0.02     # por jogo em casa, sem estádio registrado
PREMIO_CAMPEAO = 10_000_000
PREMIO_DEGRAU = 500_000            # quanto o prêmio cai a cada posição


def cota_tv_rodada(total_rodadas):
    return round(COTA_TV_TEMPORADA / total_rodadas)


def bilheteria(clube, publico=None):
    """Com público (clube com estádio), pagantes × ingresso; sem, pela
    torcida inteira, como antes da v1.5."""
    if publico:
        return estadio.bilheteria(clube, publico)
    return round(clube.torcedores * BILHETERIA_POR_TORCEDOR)


def folha_salarial(clube):
    """Soma dos salários do elenco atual, por temporada. Calculada na hora:
    quando o elenco mudar (transferências), a folha acompanha."""
    return sum(j.salario for j in clube.jogadores)


def salarios_rodada(clube, total_rodadas):
    return round(folha_salarial(clube) / total_rodadas)


def premiacao(posicao):
    return max(PREMIO_DEGRAU, PREMIO_CAMPEAO - (posicao - 1) * PREMIO_DEGRAU)


def processar_rodada(confrontos, total_rodadas, publicos=None):
    """Lança as receitas e despesas de uma rodada. `confrontos` é a lista de
    pares (mandante, visitante) do calendário; `publicos`, os pagantes de
    cada mandante ({nome: público}, v1.5)."""

    tv = cota_tv_rodada(total_rodadas)
    publicos = publicos or {}

    for mandante, visitante in confrontos:
        mandante.lancar(
            "receita_bilheteria", bilheteria(mandante, publicos.get(mandante.nome))
        )
        if mandante.lugares_ampliados:
            mandante.lancar("despesa_estadio", estadio.manutencao(mandante))
        for clube in (mandante, visitante):
            clube.lancar("receita_tv", tv)
            clube.lancar("despesa_salarios", salarios_rodada(clube, total_rodadas))


def pagar_premiacao(classificacao):
    for posicao, clube in enumerate(classificacao, start=1):
        clube.lancar("receita_premiacao", premiacao(posicao))
