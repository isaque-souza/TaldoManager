"""Clubes da CPU negociam entre si (v1.7).

Regras puras, sem banco. Quando a janela abre (pré-temporada e depois da
rodada 19), antes de o técnico mexer:

- cada clube da CPU tem uma chance de ir ao mercado atrás de UM reforço
- reforço é quem chega pelo menos `GANHO_MINIMO` acima do pior titular da
  posição; o comprador paga o que o vendedor pede (`mercado.preco_pedido`)
  e não gasta mais que `FRACAO_CAIXA` do caixa
- ninguém vende o craque nem um ídolo, rival não negocia com rival, e quem
  está emprestado não sai (vale a trava de `mercado.motivo_saida_bloqueada`)
- no máximo `MAX_POR_JANELA` negócios por janela; o clube do técnico fica
  de fora (os dele passam pelas ofertas, em `app.domain.ofertas`)
- o jogador tem vontade (v1.9): não vai para onde "não vem" e, se está
  resistente ao comprador, recusa em `CHANCE_RECUSA` das vezes

O sorteio usa um `random.Random` próprio (`semente`): não mexe na sequência
das partidas, e o mesmo save sorteia sempre os mesmos negócios.
"""

import random
from dataclasses import dataclass

from app.domain import fama, mercado, vontade

CHANCE_COMPRA = 0.35       # por clube, por janela
MAX_POR_JANELA = 10
FRACAO_CAIXA = 0.4         # o máximo do caixa que vai num reforço
GANHO_MINIMO = 2           # de overall sobre o pior titular da posição
CANDIDATOS = 5             # sorteia entre os melhores negócios
CHANCE_RECUSA = 0.5        # jogador resistente ao comprador (v1.9)


@dataclass
class Negocio:
    jogador: object
    vendedor: object
    comprador: object
    valor: int


def semente(seed, temporada, rodada):
    """O gerador dos negócios de uma janela. Sem seed (save aleatório), um
    sorteio novo: os negócios ficam gravados, não são refeitos."""
    if seed is None:
        return random.Random()
    return random.Random(f"mercado-cpu:{seed}:{temporada}:{rodada}")


def pior_titular(clube, posicao):
    """O overall do pior titular da posição (None se ela não tem vaga)."""
    vagas = mercado.vagas(clube, posicao)
    if not vagas:
        return None
    da_posicao = sorted((j.overall for j in clube.jogadores if j.posicao == posicao), reverse=True)
    return da_posicao[vagas - 1] if len(da_posicao) >= vagas else 0


def _vende(vendedor, jogador):
    return not (
        jogador.emprestimo
        or fama.idolo(jogador)
        or mercado.eh_craque(vendedor, jogador)
        or mercado.motivo_saida_bloqueada(vendedor, jogador)
    )


def _candidatos(comprador, clubes, ja, todos=None):
    """(ganho, jogador, vendedor, preço) dos reforços que cabem no caixa."""
    verba = comprador.dinheiro * FRACAO_CAIXA
    piores = {}
    lista = []
    for vendedor in clubes:
        if vendedor is comprador or mercado.sao_rivais(vendedor, comprador):
            continue
        for j in vendedor.jogadores:
            if j.nome in ja:
                continue
            if j.posicao not in piores:
                piores[j.posicao] = pior_titular(comprador, j.posicao)
            pior = piores[j.posicao]
            if pior is None or j.overall < pior + GANHO_MINIMO:
                continue
            if not _vende(vendedor, j):
                continue
            # `todos`: o clube da história pode ser o do técnico (v1.9)
            if vontade.motivo_nao_vem(j, comprador, todos or clubes):
                continue
            preco = mercado.preco_pedido(j, vendedor, comprador)
            if preco > verba or mercado.motivo_entrada_bloqueada(comprador, preco):
                continue
            lista.append((j.overall - pior, j, vendedor, preco))
    # o maior ganho primeiro; no empate, o mais barato
    lista.sort(key=lambda c: (-c[0], c[3], c[1].nome))
    return lista[:CANDIDATOS]


def negociar(clubes, clube_usuario, rng):
    """Faz os negócios da janela entre os clubes da CPU e devolve a lista
    (`Negocio`), na ordem em que aconteceram."""

    cpu = sorted((c for c in clubes if c.nome != clube_usuario), key=lambda c: c.nome)
    compradores = [c for c in cpu if rng.random() < CHANCE_COMPRA]
    rng.shuffle(compradores)

    feitos, ja = [], set()
    prest = vontade.prestigio(clubes)
    for comprador in compradores:
        if len(feitos) >= MAX_POR_JANELA:
            break
        candidatos = _candidatos(comprador, cpu, ja, clubes)
        if not candidatos:
            continue
        _, jogador, vendedor, preco = rng.choice(candidatos)
        # o jogador também decide (v1.9): resistente, às vezes recusa
        interesse = vontade.interesse(jogador, comprador, vendedor, clubes, prest)
        if interesse.nivel == vontade.RESISTENTE and rng.random() < CHANCE_RECUSA:
            continue
        mercado.transferir(jogador, vendedor, comprador, preco)
        ja.add(jogador.nome)
        feitos.append(Negocio(jogador, vendedor, comprador, preco))
    return feitos
