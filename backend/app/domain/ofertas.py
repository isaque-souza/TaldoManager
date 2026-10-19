"""Ofertas da CPU pelos jogadores do técnico (v1.7, passo 5).

Regras puras, sem banco. Antes, vender era um balcão: na janela, todo
clube que podia pagar tinha uma oferta pronta por qualquer jogador. Agora
quem toma a iniciativa é a CPU:

- À VENDA: quando a janela abre (ou quando o técnico põe alguém na lista com
  a janela aberta), até 3 clubes que precisam da posição e podem pagar fazem
  oferta — um pouco abaixo do valor, porque sabem que o clube quer vender.
- ASSÉDIO: em cada janela, uma chance de um dos 3 melhores jogadores (fora
  da lista) receber uma oferta alta de um clube mais forte — ou, se o
  técnico já tem o elenco mais forte, de um dos 3 que vêm logo abaixo.

O técnico aceita, recusa ou contrapropõe uma vez: o clube aceita até um teto
que ele não vê e, acima dele, retira a oferta. Por enquanto a CPU não paga
a multa rescisória: toda oferta fica abaixo dela.

O sorteio usa um `random.Random` próprio, semeado pela temporada, rodada e
jogador (`semente`): não mexe na sequência aleatória das partidas, e o mesmo
save sorteia sempre as mesmas ofertas.
"""

import random
from dataclasses import dataclass

from app.domain import diretoria, mercado

MAX_OFERTAS = 3
CHANCE_NENHUMA = 0.15            # à venda e ninguém se interessa
DESCONTO_A_VENDA = 0.9           # sabem que o clube quer vender
VARIACAO = (0.85, 1.10)
CHANCE_ASSEDIO = 0.5             # por janela
CRAQUES_ASSEDIADOS = 3           # o assédio mira um dos 3 melhores
ASSEDIADORES_DO_MAIS_FORTE = 3   # sem clube mais forte: os 3 logo abaixo
FAIXA_ASSEDIO = (1.2, 1.5)
FAIXA_TETO = (1.05, 1.25)        # até quanto o clube aceita na contraproposta


@dataclass
class OfertaCpu:
    clube: object
    valor: int
    teto: int            # o máximo que ele aceita numa contraproposta
    espontanea: bool     # assédio (o jogador não estava à venda)


def semente(simulacao_id, rodada, nome=""):
    """O gerador das ofertas de uma janela (e de um jogador)."""
    return random.Random(f"ofertas:{simulacao_id}:{rodada}:{nome}")


def _abaixo_da_multa(jogador, valor):
    multa = jogador.multa_rescisoria
    if multa is not None and valor >= multa:
        return multa - 10_000
    return valor


def _precisa(clube, jogador):
    """O clube quer o jogador: ele seria titular lá, ou falta gente na
    posição (menos de dois por vaga)."""
    if mercado.seria_titular(clube, jogador):
        return True
    na_posicao = sum(1 for j in clube.jogadores if j.posicao == jogador.posicao)
    return na_posicao < 2 * mercado.vagas(clube, jogador.posicao)


def _oferta(rng, clube, jogador, valor, espontanea):
    valor = _abaixo_da_multa(jogador, mercado._arredondar(valor))
    if valor <= 0 or mercado.motivo_entrada_bloqueada(clube, valor):
        return None
    teto = mercado._arredondar(valor * rng.uniform(*FAIXA_TETO))
    return OfertaCpu(clube, valor, _abaixo_da_multa(jogador, teto), espontanea)


def para_venda(jogador, vendedor, clubes, rng):
    """As ofertas por um jogador da lista de transferências: de 0 a 3, das
    maiores para as menores."""

    if mercado.motivo_saida_bloqueada(vendedor, jogador):
        return []
    interessados = sorted(
        (c for c in clubes if c is not vendedor and _precisa(c, jogador)),
        key=lambda c: c.nome,   # ordem estável antes do sorteio
    )
    if not interessados or rng.random() < CHANCE_NENHUMA:
        return []
    escolhidos = rng.sample(interessados, rng.randint(1, min(MAX_OFERTAS, len(interessados))))

    lista = []
    for clube in escolhidos:
        fator = mercado.OFERTA_TITULAR if mercado.seria_titular(clube, jogador) else mercado.OFERTA_BANCO
        valor = jogador.valor_mercado() * fator * rng.uniform(*VARIACAO) * DESCONTO_A_VENDA
        oferta = _oferta(rng, clube, jogador, valor, espontanea=False)
        if oferta:
            lista.append(oferta)
    lista.sort(key=lambda o: (-o.valor, o.clube.nome))
    return lista


def assedio(vendedor, clubes, rng):
    """(jogador, oferta) — um dos melhores, fora da lista, cobiçado por um
    clube mais forte — ou None (na maioria das janelas sem sorte, ou sem
    clube que possa pagar)."""

    if rng.random() >= CHANCE_ASSEDIO:
        return None
    craques = sorted(
        (j for j in vendedor.jogadores
         if not j.a_venda and not mercado.motivo_saida_bloqueada(vendedor, j)),
        key=lambda j: (-j.overall, j.nome),
    )[:CRAQUES_ASSEDIADOS]
    if not craques:
        return None
    jogador = rng.choice(craques)

    forca = diretoria.forca_do_elenco(vendedor)
    outros = sorted(
        (c for c in clubes if c is not vendedor),
        key=lambda c: (-diretoria.forca_do_elenco(c), c.nome),
    )
    maiores = [c for c in outros if diretoria.forca_do_elenco(c) > forca] \
        or outros[:ASSEDIADORES_DO_MAIS_FORTE]
    rng.shuffle(maiores)
    valor = jogador.valor_mercado() * rng.uniform(*FAIXA_ASSEDIO)
    for clube in maiores:
        oferta = _oferta(rng, clube, jogador, valor, espontanea=True)
        if oferta:
            return jogador, oferta
    return None


def responder_contraproposta(valor_oferta, teto, pedido):
    """O que o clube faz com o pedido do técnico: "aceita" (fecha pelo
    pedido) ou "retirada" (desiste da oferta)."""
    if pedido <= valor_oferta:
        raise mercado.TransferenciaInvalida(
            "A contraproposta precisa pedir mais do que a oferta"
        )
    return "aceita" if pedido <= teto else "retirada"
