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


def fator_papel(jogador, papel):
    if papel is None or jogador.papel is None:
        return 1.0
    diferenca = papeis.NIVEL[papel] - papeis.NIVEL[jogador.papel]
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
