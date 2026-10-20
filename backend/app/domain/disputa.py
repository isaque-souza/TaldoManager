"""Disputa pela contratação (v1.9, passo 3).

Regras puras, sem banco. Quando o técnico acerta o valor com o clube (ou
abre a negociação com um livre), um clube da CPU pode entrar na disputa:

- chance de `CHANCE_BASE`, mais `CHANCE_CRAQUE` para quem tem overall
  `OVERALL_CRAQUE`+;
- entra quem precisa da posição, pode pagar o mesmo valor e para onde o
  jogador iria (não é "não vem"); entre esses, o de que ele mais gosta
  (`vontade.interesse`);
- o concorrente oferece o salário que o jogador pediria a ele, com uma
  variação (`VARIACAO`).

O jogador compara "pacotes": o salário dividido pelo fator de interesse no
clube. Para ficar com o técnico, o salário precisa bater o do concorrente
pesado pelos dois interesses (`salario_para_bater`). Se o técnico não fecha
o contrato até jogar a rodada (ou o jogador desiste), ele assina com o
concorrente no fim dela.

O sorteio usa um `random.Random` próprio, semeado pela simulação, janela e
jogador (`semente`): não mexe nas partidas, e recarregar não muda o
concorrente.
"""

import math
import random
from dataclasses import dataclass

from app.domain import contrato, mercado, ofertas, vontade

CHANCE_BASE = 0.25
CHANCE_CRAQUE = 0.25
OVERALL_CRAQUE = 85
VARIACAO = (0.95, 1.10)
ANOS_CONCORRENTE = 3          # o contrato que ele assina com o concorrente
ALGARISMOS = 2                # o técnico vê o salário do concorrente com 2 algarismos


@dataclass
class Concorrente:
    clube: object
    salario: int
    fator: float          # o fator de interesse do jogador no concorrente


def semente(simulacao_id, rodada, nome):
    return random.Random(f"disputa:{simulacao_id}:{rodada}:{nome}")


def chance(jogador):
    return CHANCE_BASE + (CHANCE_CRAQUE if jogador.overall >= OVERALL_CRAQUE else 0)


def _pode_entrar(clube, jogador, valor, clubes):
    return (
        ofertas._precisa(clube, jogador)
        and mercado.motivo_entrada_bloqueada(clube, valor) is None
        and vontade.motivo_nao_vem(jogador, clube, clubes) is None
    )


def concorrente(jogador, vendedor, comprador, valor, clubes, rng, prest=None):
    """O `Concorrente` que entra na disputa pelo jogador, ou None. `vendedor`
    None = está livre (`valor` = as luvas)."""
    # os dois sorteios sempre acontecem: o resultado de um não muda o outro
    entra = rng.random() < chance(jogador)
    variacao = rng.uniform(*VARIACAO)
    if not entra:
        return None

    prest = prest if prest is not None else vontade.prestigio(clubes)
    candidatos = []
    for clube in clubes:
        if clube is comprador or clube is vendedor:
            continue
        if not _pode_entrar(clube, jogador, valor, clubes):
            continue
        interesse = vontade.interesse(jogador, clube, vendedor, clubes, prest)
        candidatos.append((interesse, clube))
    if not candidatos:
        return None

    interesse, clube = min(candidatos, key=lambda c: (-c[0].pontos, c[1].nome))
    pedido = contrato.salario_pedido_chegada(
        jogador, clube, vendedor, "3x", interesse=interesse,
    )
    salario = max(1_000, round(pedido * variacao / 1_000) * 1_000)
    return Concorrente(clube, salario, interesse.fator)


def salario_para_bater(salario_concorrente, fator_concorrente, fator_comprador):
    """O menor salário do comprador que vale mais, para o jogador, que a
    proposta do concorrente (arredondado para cima, em mil)."""
    valor = salario_concorrente * fator_comprador / fator_concorrente
    return math.ceil(valor / 1_000) * 1_000


def aproximado(salario):
    """O salário do concorrente como o técnico fica sabendo, "cerca de":
    com `ALGARISMOS` algarismos (827 mil → 830 mil; 12,3 mi → 12 mi)."""
    passo = 10 ** max(0, len(str(int(salario))) - ALGARISMOS)
    return round(salario / passo) * passo
