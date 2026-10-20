"""Renovação de contrato (v0.7).

O técnico propõe salário, duração e multa rescisória; o jogador pede um
salário (o de referência ajustado pela importância dele e pela multa) e
responde como o vendedor numa compra: aceita, contrapropõe ou recusa.

O trade-off central é a multa: multa alta (ou nenhuma) protege o jogador de
propostas de outros clubes, mas ele cobra por isso no salário.

Determinístico, como o resto do mercado: não mexe na sorte da temporada.
"""

from app.domain import mercado, papeis
from app.domain.mercado import Resposta

FATOR_CRAQUE = 1.4
FATOR_TITULAR = 1.2
FATOR_ULTIMO_ANO = 1.1     # contrato acabando: o jogador tem a faca e o queijo
FAIXA_CONTRAPROPOSTA = 0.9
MAX_TENTATIVAS = 3         # por jogador, por rodada

DURACAO_MAX = 5
DURACAO_MAX_VETERANO = 2
IDADE_VETERANO = 32

# opção de multa -> (múltiplo do valor de mercado ou None, fator no salário)
MULTAS = {
    "sem": (None, 1.15),   # clube protegido de tudo: o jogador cobra
    "2x": (2, 0.95),       # multa barata: o jogador gosta da liberdade
    "3x": (3, 1.0),
    "5x": (5, 1.1),        # multa alta: preso ao clube, cobra mais
}


class ContratoInvalido(ValueError):
    """A proposta de renovação fere alguma regra (duração, multa...)."""


def duracao_max(jogador):
    return DURACAO_MAX_VETERANO if jogador.idade >= IDADE_VETERANO else DURACAO_MAX


def valor_multa(jogador, opcao):
    """Valor da multa para uma opção (None = sem multa), múltiplo de 100 mil."""
    if opcao not in MULTAS:
        raise ContratoInvalido(f"Opção de multa inválida: {opcao!r}")
    multiplo, _ = MULTAS[opcao]
    if multiplo is None:
        return None
    return max(500_000, round(jogador.valor_mercado() * multiplo / 100_000) * 100_000)


# papel prometido (v1.7): cada nível acima do atual, ele pede 5% a menos;
# cada nível abaixo, 10% a mais (titular > rotação > promessa > reserva)
FATOR_PAPEL_ACIMA = 0.95
FATOR_PAPEL_ABAIXO = 1.10


def fator_papel(jogador, papel, base=None):
    """`base`: o papel de partida (o atual, na renovação; o que ele espera
    no clube novo, na chegada)."""
    base = base or jogador.papel
    if papel is None or base is None:
        return 1.0
    diferenca = papeis.NIVEL[papel] - papeis.NIVEL[base]
    if diferenca >= 0:
        return FATOR_PAPEL_ACIMA ** diferenca
    return FATOR_PAPEL_ABAIXO ** -diferenca


def salario_pedido(jogador, clube, opcao_multa, papel=None):
    """Quanto o jogador quer por temporada para renovar com esta multa (e,
    v1.7, com este papel prometido; None = o atual)."""

    salario = jogador.salario_referencia()

    if mercado.eh_craque(clube, jogador):
        salario *= FATOR_CRAQUE
    elif mercado.seria_titular(clube, jogador):
        salario *= FATOR_TITULAR

    if jogador.contrato_anos <= 1:
        salario *= FATOR_ULTIMO_ANO

    salario *= MULTAS[opcao_multa][1]
    salario *= fator_papel(jogador, papel)

    return max(1_000, round(salario / 1_000) * 1_000)


def validar(jogador, anos, opcao_multa, papel=None):
    if papel is not None:
        motivo = papeis.motivo_papel_bloqueado(jogador, papel)
        if motivo:
            raise ContratoInvalido(motivo)
    if opcao_multa not in MULTAS:
        raise ContratoInvalido(f"Opção de multa inválida: {opcao_multa!r}")
    maximo = duracao_max(jogador)
    if not 1 <= anos <= maximo:
        extra = f" (aos {jogador.idade} anos)" if maximo < DURACAO_MAX else ""
        raise ContratoInvalido(
            f"{jogador.nome} aceita de 1 a {maximo} temporadas{extra}"
        )


def avaliar_renovacao(jogador, clube, salario, anos, opcao_multa, papel=None):
    """Resposta do jogador à proposta. Se fechou, `Resposta.valor` é o
    salário do contrato novo."""

    validar(jogador, anos, opcao_multa, papel)
    pedido = salario_pedido(jogador, clube, opcao_multa, papel)

    # quer sair por falta de tempo de jogo (v1.7): nem conversa
    if jogador.humor == "quer_sair":
        return Resposta(
            "recusada", pedido,
            f"{jogador.nome} quer sair do clube e não aceita renovar",
        )
    if salario >= pedido:
        return Resposta("aceita", salario, f"{jogador.nome} aceitou renovar")
    if salario >= FAIXA_CONTRAPROPOSTA * pedido:
        return Resposta(
            "contraproposta", pedido,
            f"{jogador.nome} topa renovar, mas quer um salário maior",
        )
    return Resposta(
        "recusada", pedido, f"{jogador.nome} achou a proposta baixa demais",
    )


def renovar(jogador, anos, salario, opcao_multa, papel=None):
    jogador.assinar_contrato(anos, salario, valor_multa(jogador, opcao_multa))
    # o papel combinado no contrato (v1.7): ele aceitou, então rebaixar aqui
    # não incomoda; promover deixa contente
    if papel is not None and papel != jogador.papel:
        if jogador.papel is not None and papeis.NIVEL[papel] > papeis.NIVEL[jogador.papel]:
            jogador.humor = papeis.CONTENTE
        jogador.papel = papel


# ---------------------------------------------------------------------------
# contrato de quem chega (v1.7): a etapa 2 da negociação
# ---------------------------------------------------------------------------
#
# Acertado o valor com o clube (ou, para um livre, direto), o jogador
# negocia salário, anos, multa e papel. Pede o de mercado ajustado pela
# importância que teria no clube novo, pela multa, pelo papel prometido e
# (v1.9) pelo interesse em vir — `vontade.interesse`, que substituiu o
# fator de descer para um clube mais fraco; se vem de outro clube, cobra
# pela mudança e nunca aceita ganhar menos do que já ganha.

FATOR_MUDANCA = 1.10      # trocar de clube: quer ganhar para isso


def papel_esperado(clube, jogador):
    """O papel que o jogador imagina ter no `clube` (a base do papel
    prometido na chegada)."""
    if mercado.seria_titular(clube, jogador):
        return papeis.TITULAR
    if (jogador.idade <= papeis.IDADE_PROMESSA
            and jogador.potencial - jogador.overall >= papeis.MARGEM_PROMESSA):
        return papeis.PROMESSA
    acima = sum(1 for j in clube.jogadores if j is not jogador and j.overall > jogador.overall)
    return papeis.ROTACAO if acima < 11 + papeis.VAGAS_ROTACAO else papeis.RESERVA


def salario_pedido_chegada(jogador, comprador, vendedor, opcao_multa, papel=None,
                           interesse=None):
    """Quanto o jogador quer para assinar com o `comprador`. `vendedor` None
    = está livre (sem custo de mudança). `interesse`: o `vontade.Interesse`
    (v1.9); sem ele, neutro."""

    salario = jogador.salario_referencia()

    if jogador.overall >= max((j.overall for j in comprador.jogadores), default=0):
        salario *= FATOR_CRAQUE
    elif mercado.seria_titular(comprador, jogador):
        salario *= FATOR_TITULAR

    salario *= MULTAS[opcao_multa][1]
    salario *= fator_papel(jogador, papel, base=papel_esperado(comprador, jogador))
    if interesse is not None:
        salario *= interesse.fator

    if vendedor is not None:
        salario *= FATOR_MUDANCA
        salario = max(salario, jogador.salario)

    return max(1_000, round(salario / 1_000) * 1_000)


def salario_sugerido_chegada(jogador, comprador, vendedor):
    """Um ponto de partida para a proposta: o de mercado com o custo da
    mudança e o peso do papel que ele espera, sem os fatores escondidos
    (craque, multa, interesse). Nunca abaixo do que já ganha."""
    salario = jogador.salario_referencia()
    if mercado.seria_titular(comprador, jogador):
        salario *= FATOR_TITULAR
    if vendedor is not None:
        salario = max(salario * FATOR_MUDANCA, jogador.salario)
    return max(1_000, round(salario / 1_000) * 1_000)


# o que o jogador acrescenta à resposta, conforme o interesse (v1.9)
_COMENTARIO = {
    "quer_vir": " — ele quer muito vir",
    "resistente": " — e ele não está animado com a mudança",
}


def avaliar_chegada(jogador, comprador, vendedor, salario, anos, opcao_multa, papel,
                    interesse=None, para_bater=None, concorrente=None):
    """Resposta do jogador ao contrato oferecido pelo `comprador`.
    `para_bater` (v1.9): o salário que vence a proposta do `concorrente`
    (nome do clube) — `disputa.salario_para_bater`; o pedido nunca fica
    abaixo dele."""

    validar(jogador, anos, opcao_multa, papel)
    if interesse is not None and interesse.bloqueio:
        raise ContratoInvalido(interesse.bloqueio)
    pedido = salario_pedido_chegada(
        jogador, comprador, vendedor, opcao_multa, papel, interesse,
    )
    comentario = _COMENTARIO.get(interesse.nivel, "") if interesse else ""
    if para_bater is not None and para_bater > pedido:
        # quem decide é a outra proposta
        pedido = para_bater
        comentario = f" — ele prefere a proposta do {concorrente}"

    if salario >= pedido:
        return Resposta("aceita", salario, f"{jogador.nome} aceitou o contrato")
    if salario >= FAIXA_CONTRAPROPOSTA * pedido:
        return Resposta(
            "contraproposta", pedido,
            f"{jogador.nome} topa vir, mas pede um salário maior{comentario}",
        )
    return Resposta(
        "recusada", pedido, f"{jogador.nome} achou o salário baixo demais{comentario}",
    )
