"""Relatório de contratação (v2.0, passo 3).

O técnico pede ao olheiro um relatório sobre um jogador que observa. Ele
fica pronto depois de alguns dias (`DIAS`, pelo nível do olheiro) e vale até
o fim da temporada, sempre com a situação de agora: se o contrato do jogador
encurta ou o clube dele se endivida, o preço acompanha.

O relatório mostra:
- a faixa do preço que o clube vai pedir (ou das luvas, se está livre) e a
  do salário que o jogador pediria — mais estreitas quanto maior o nível
  (`MARGEM`), sempre contendo o valor certo, com o deslocamento vindo do
  nome (crc32), como a faixa do potencial;
- a vontade dele de vir (`vontade.interesse`), que sem relatório fica
  escondida — menos o "não vem", que bloqueia a proposta;
- a dificuldade (`dificuldade`) e a chance de outro clube entrar na disputa
  (`disputa.chance`).

Nada de `random`: não mexe na sequência das partidas.
"""

import math
import zlib

from app.domain import disputa, mercado, vontade

# nível do olheiro: dias até ficar pronto e meia largura das faixas (fração)
DIAS = {1: 10, 2: 8, 3: 6, 4: 4, 5: 2}
MARGEM = {1: 0.25, 2: 0.20, 3: 0.15, 4: 0.10, 5: 0.05}
ALGARISMOS = 2                   # as faixas com 2 algarismos (18–24 mi)

FACIL, MEDIA, DIFICIL, IMPOSSIVEL = "facil", "media", "dificil", "impossivel"
FRACAO_FACIL = 0.25              # preço até 1/4 do caixa
FRACAO_DIFICIL = 0.5             # preço acima de metade do caixa


def limite(nivel):
    """Quantos relatórios o olheiro faz ao mesmo tempo."""
    return nivel


def _fracao(nome, chave):
    return zlib.crc32(f"relatorio:{chave}:{nome}".encode()) / 0xFFFFFFFF


def _passo(valor):
    return 10 ** max(0, len(str(int(valor))) - ALGARISMOS)


def faixa(valor, nome, nivel, chave):
    """(mínimo, máximo) em volta de `valor`, com 2 algarismos e arredondado
    para fora (o valor certo nunca fica de fora)."""
    largura = 2 * MARGEM[nivel] * valor
    minimo = valor - _fracao(nome, chave) * largura
    maximo = minimo + largura
    passo = _passo(max(maximo, 1))
    return (max(0, math.floor(minimo / passo) * passo), math.ceil(maximo / passo) * passo)


def dificuldade(interesse, preco, caixa, motivo_clube=None, rival=False):
    """Fácil, média, difícil ou impossível: o que pesa é se ele vem, se o
    clube vende, se o preço cabe no caixa e se ele está animado."""
    if interesse.bloqueio or motivo_clube or preco > caixa:
        return IMPOSSIVEL
    if interesse.nivel == vontade.RESISTENTE or rival or preco > caixa * FRACAO_DIFICIL:
        return DIFICIL
    if interesse.nivel == vontade.QUER_VIR and preco <= caixa * FRACAO_FACIL:
        return FACIL
    return MEDIA


def motivo_dificuldade(interesse, preco, caixa, motivo_clube=None, rival=False):
    """Por que a dificuldade é a que é, em uma frase."""
    if interesse.bloqueio:
        return interesse.bloqueio
    if motivo_clube:
        return motivo_clube
    if preco > caixa:
        return "O preço não cabe no caixa"
    if rival:
        return "É do rival: tudo sai mais caro"
    if interesse.nivel == vontade.RESISTENTE:
        return "Ele não está animado com a mudança"
    if preco > caixa * FRACAO_DIFICIL:
        return "O preço passa de metade do caixa"
    if interesse.nivel == vontade.QUER_VIR and preco <= caixa * FRACAO_FACIL:
        return "Ele quer vir e o preço cabe com folga"
    return "Dá para negociar"


def montar(jogador, vendedor, comprador, interesse, preco, salario, nivel):
    """O relatório pronto: faixas, vontade, dificuldade e disputa.
    `vendedor` None = livre (`preco` = as luvas)."""
    motivo_clube = mercado.motivo_saida_bloqueada(vendedor, jogador) if vendedor else None
    rival = vendedor is not None and mercado.sao_rivais(vendedor, comprador)
    caixa = comprador.dinheiro
    return {
        "preco": list(faixa(preco, jogador.nome, nivel, "preco")),
        "salario": list(faixa(salario, jogador.nome, nivel, "salario")),
        "dificuldade": dificuldade(interesse, preco, caixa, motivo_clube, rival),
        "motivo": motivo_dificuldade(interesse, preco, caixa, motivo_clube, rival),
        "chance_disputa": round(disputa.chance(jogador) * 100),
    }
