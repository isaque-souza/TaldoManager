"""Mercado de transferências (v0.7).

Regras puras, sem banco: quando a janela está aberta, quem pode vender e
comprar, e a transferência em si (troca o jogador de elenco e lança o
dinheiro nos dois caixas).

Negociação (v0.7, passo 4):

- COMPRA: o clube vendedor calcula um preço pedido (valor de mercado ajustado
  pela importância do jogador para ele, se é ídolo, contrato, caixa e
  rivalidade) e
  responde à proposta: aceita, contrapropõe ou recusa. Se o jogador tem multa
  rescisória e a proposta a cobre, o clube não pode recusar.
- VENDA (v1.7): a CPU faz as ofertas, com sorteio próprio — ver
  `app.domain.ofertas`.

Tudo determinístico (sem `random`): não mexe na sorte da temporada.
"""

from dataclasses import dataclass

from app.domain import fama, formato

# rodadas ANTES das quais a janela está aberta: pré-temporada e virada do turno
JANELAS = (1, 20)

# contrato que o reforço assina ao chegar (renovável depois)
CONTRATO_PADRAO_ANOS = 3

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

    if jogador.emprestimo:
        # o contrato é com o clube de origem (v1.7): não vende nem dispensa
        return f"{jogador.nome} está emprestado pelo {jogador.emprestimo['de']}"
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
        return f"{clube.nome} não tem caixa para pagar {formato.reais(preco)}"
    return None


def tirar_do_elenco(clube, jogador):
    # papel e humor são do clube (v1.7): no próximo, começa do zero
    jogador.papel = None
    jogador.humor = "contente"
    clube.jogadores.remove(jogador)
    for lista in (clube.titulares, clube.reservas):
        if jogador in lista:
            lista.remove(jogador)
    clube.xi_preferido.discard(jogador)


def transferir(jogador, vendedor, comprador, preco, contrato=None):
    """Move `jogador` de `vendedor` para `comprador` pagando `preco`.
    `contrato`: (anos, salário, multa) combinados com o jogador (v1.7); sem
    ele, o padrão. Levanta `TransferenciaInvalida` se alguma regra impedir."""

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

    tirar_do_elenco(vendedor, jogador)
    comprador.contratar_jogador(jogador)
    # a fama vem junto; a história no clube, não (v1.4)
    jogador.temporadas_no_clube = 0
    jogador.a_venda = False   # a lista era do clube antigo (v1.7)
    # chega com contrato novo: o do clube antigo não vale no novo
    jogador.assinar_contrato(*(contrato or (
        CONTRATO_PADRAO_ANOS, jogador.salario_referencia(), None,
    )))

    comprador.lancar("despesa_compras", preco)
    vendedor.lancar("receita_vendas", preco)


# --- jogadores livres (v1.6) -------------------------------------------------

# sem clube não há transferência: paga-se só as luvas, um bônus de assinatura
FATOR_LUVAS = 0.10
CONTRATO_LIVRE_ANOS = 2


def luvas(jogador):
    return _arredondar(jogador.valor_mercado() * FATOR_LUVAS)


def contratar_livre(jogador, livres, clube, contrato=None):
    """Tira `jogador` da lista de `livres` e o põe no `clube`, que paga as
    luvas. `contrato`: (anos, salário, multa) combinados (v1.7); sem ele, o
    padrão. Devolve o valor das luvas. Levanta `TransferenciaInvalida` se
    alguma regra impedir."""

    if jogador not in livres:
        raise TransferenciaInvalida(f"{jogador.nome} não está livre")
    valor = luvas(jogador)
    motivo = motivo_entrada_bloqueada(clube, valor)
    if motivo:
        raise TransferenciaInvalida(motivo)

    livres.remove(jogador)
    clube.contratar_jogador(jogador)
    jogador.temporadas_no_clube = 0
    jogador.a_venda = False
    jogador.assinar_contrato(*(contrato or (
        CONTRATO_LIVRE_ANOS, jogador.salario_referencia(), None,
    )))
    clube.lancar("despesa_compras", valor)
    return valor


# --- dispensa (v1.7) ---------------------------------------------------------

# rescindir custa metade dos salários que o contrato ainda deve
FATOR_RESCISAO = 0.5


def rescisao(jogador):
    return round(jogador.salario * jogador.contrato_anos * FATOR_RESCISAO / 10_000) * 10_000


def motivo_dispensa_bloqueada(clube, jogador):
    """Por que `clube` não pode dispensar `jogador` (None = pode). Vale a
    trava do elenco mínimo e é preciso ter caixa para a rescisão."""
    motivo = motivo_saida_bloqueada(clube, jogador)
    if motivo:
        return motivo
    custo = rescisao(jogador)
    if clube.dinheiro < custo:
        return f"{clube.nome} não tem caixa para pagar {formato.reais(custo)} de rescisão"
    return None


# --- negociação -------------------------------------------------------------

FATOR_TITULAR = 1.3            # titular do vendedor custa mais
FATOR_CRAQUE = 1.6             # o melhor do elenco custa ainda mais
FATOR_RIVAL = 1.5              # vender para o rival? só caro
FATOR_CONTRATO_LONGO = 1.2     # 4+ temporadas de contrato
FATOR_CONTRATO_ACABANDO = 0.7  # última temporada: vender ou perder de graça
FATOR_ENDIVIDADO = 0.85        # caixa negativo: o clube precisa vender
FAIXA_CONTRAPROPOSTA = 0.85    # proposta >= 85% do pedido vira contraproposta
MAX_PROPOSTAS = 3              # por jogador, por janela

# ofertas da CPU (app.domain.ofertas): paga mais por quem seria titular
OFERTA_TITULAR = 1.15
OFERTA_BANCO = 0.85


def _arredondar(valor):
    return max(10_000, round(valor / 10_000) * 10_000)


def sao_rivais(a, b):
    return b.nome in a.rivais or a.nome in b.rivais


def vagas(clube, posicao):
    """Quantos titulares a formação do clube usa nesta posição."""
    if posicao == "Goleiro":
        return 1
    n_def, n_mei, n_ata = clube.FORMACOES.get(clube.formacao, (4, 3, 3))
    return {"Defesa": n_def, "Meio-Campo": n_mei, "Atacante": n_ata}[posicao]


def seria_titular(clube, jogador):
    """O jogador estaria no XI do `clube` (por overall)? Serve tanto para quem
    já está no elenco quanto para um reforço em potencial."""
    melhores = sum(
        1 for j in clube.jogadores
        if j is not jogador
        and j.posicao == jogador.posicao
        and j.overall > jogador.overall
    )
    return melhores < vagas(clube, jogador.posicao)


def eh_craque(clube, jogador):
    return jogador.overall >= max(j.overall for j in clube.jogadores)


def preco_pedido(jogador, vendedor, comprador):
    """Quanto o `vendedor` quer para liberar o jogador para o `comprador`.
    Nunca passa da multa rescisória: pagando a multa, o jogador sai."""

    preco = jogador.valor_mercado()

    if eh_craque(vendedor, jogador):
        preco *= FATOR_CRAQUE
    elif seria_titular(vendedor, jogador):
        preco *= FATOR_TITULAR

    # tirar um ídolo da torcida custa mais (v1.4)
    if fama.idolo(jogador):
        preco *= fama.FATOR_IDOLO

    if jogador.contrato_anos >= 4:
        preco *= FATOR_CONTRATO_LONGO
    elif jogador.contrato_anos <= 1:
        preco *= FATOR_CONTRATO_ACABANDO

    if vendedor.dinheiro < 0:
        preco *= FATOR_ENDIVIDADO

    if sao_rivais(vendedor, comprador):
        preco *= FATOR_RIVAL

    preco = _arredondar(preco)
    if jogador.multa_rescisoria is not None:
        preco = min(preco, jogador.multa_rescisoria)
    return preco


@dataclass
class Resposta:
    tipo: str            # "aceita" | "multa" | "contraproposta" | "recusada"
    valor: int           # quanto custa fechar (pedido, multa ou a proposta)
    motivo: str

    @property
    def fechou(self):
        return self.tipo in ("aceita", "multa")


def avaliar_proposta(jogador, vendedor, comprador, valor):
    """Resposta do `vendedor` a uma proposta de `valor` pelo jogador."""

    multa = jogador.multa_rescisoria
    if multa is not None and valor >= multa:
        return Resposta(
            "multa", multa,
            f"Multa rescisória paga: o {vendedor.nome} não pode recusar",
        )

    pedido = preco_pedido(jogador, vendedor, comprador)
    rival = " — e para o rival sai mais caro" if sao_rivais(vendedor, comprador) else ""

    if valor >= pedido:
        return Resposta("aceita", valor, f"O {vendedor.nome} aceitou a proposta")
    if valor >= FAIXA_CONTRAPROPOSTA * pedido:
        return Resposta(
            "contraproposta", pedido,
            f"O {vendedor.nome} topa negociar, mas quer mais{rival}",
        )
    return Resposta(
        "recusada", pedido,
        f"O {vendedor.nome} achou a proposta baixa demais{rival}",
    )
