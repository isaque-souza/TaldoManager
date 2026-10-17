"""Mercado de transferências (v0.7).

Regras puras, sem banco: quando a janela está aberta, quem pode vender e
comprar, e a transferência em si (troca o jogador de elenco e lança o
dinheiro nos dois caixas).

Por enquanto o preço é sempre o valor de mercado e o vendedor aceita se a
venda não desmontar o elenco dele. Negociação (propostas, recusas, disputa
entre clubes) vem num passo seguinte.
"""

# rodadas ANTES das quais a janela está aberta: pré-temporada e virada do turno
JANELAS = (1, 20)

ELENCO_MIN = 16
ELENCO_MAX = 25
GOLEIROS_MIN = 2


class TransferenciaInvalida(ValueError):
    """A transferência fere alguma regra do mercado."""


def janela_aberta(rodada):
    return rodada in JANELAS


def _goleiros(clube):
    return sum(1 for j in clube.jogadores if j.posicao == "Goleiro")


def motivo_saida_bloqueada(clube, jogador):
    """Por que `clube` não pode abrir mão de `jogador` (None = pode)."""

    if len(clube.jogadores) <= ELENCO_MIN:
        return f"{clube.nome} ficaria com menos de {ELENCO_MIN} jogadores"
    if jogador.posicao == "Goleiro" and _goleiros(clube) <= GOLEIROS_MIN:
        return f"{clube.nome} ficaria com menos de {GOLEIROS_MIN} goleiros"
    return None


def motivo_entrada_bloqueada(clube, preco):
    """Por que `clube` não pode contratar por `preco` (None = pode)."""

    if len(clube.jogadores) >= ELENCO_MAX:
        return f"{clube.nome} já tem {ELENCO_MAX} jogadores"
    if clube.dinheiro < preco:
        return f"{clube.nome} não tem caixa para pagar {preco:,}".replace(",", ".")
    return None


def transferir(jogador, vendedor, comprador, preco):
    """Move `jogador` de `vendedor` para `comprador` pagando `preco`.
    Levanta `TransferenciaInvalida` se alguma regra impedir."""

    if jogador not in vendedor.jogadores:
        raise TransferenciaInvalida(f"{jogador.nome} não joga no {vendedor.nome}")
    if vendedor is comprador:
        raise TransferenciaInvalida("Vendedor e comprador são o mesmo clube")

    motivo = (
        motivo_saida_bloqueada(vendedor, jogador)
        or motivo_entrada_bloqueada(comprador, preco)
    )
    if motivo:
        raise TransferenciaInvalida(motivo)

    vendedor.jogadores.remove(jogador)
    for lista in (vendedor.titulares, vendedor.reservas):
        if jogador in lista:
            lista.remove(jogador)
    vendedor.xi_preferido.discard(jogador)
    comprador.contratar_jogador(jogador)

    comprador.lancar("despesa_compras", preco)
    vendedor.lancar("receita_vendas", preco)


def melhor_comprador(jogador, clubes, preco, excluir=()):
    """O clube mais rico (fora `excluir`) que pode pagar `preco`. None se
    ninguém pode."""

    candidatos = [
        c for c in clubes
        if c not in excluir
        and jogador not in c.jogadores
        and motivo_entrada_bloqueada(c, preco) is None
    ]
    return max(candidatos, key=lambda c: c.dinheiro, default=None)
