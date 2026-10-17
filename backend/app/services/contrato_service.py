"""Renovação de contrato numa temporada rodada a rodada (v0.7).

Ao contrário das transferências, renovar não depende de janela: vale em
qualquer rodada, só para jogadores do clube dirigido. As regras ficam em
`app.domain.contrato`; o carregar/regravar do estado vivo é o mesmo do
mercado (`mercado_service._carregar` + `_Contexto.gravar`).
"""

from app.db.conexao import conectar
from app.domain import contrato
from app.domain.contrato import ContratoInvalido
from app.repositories import renovacao_repository as renovacao_repo
from app.services.mercado_service import _carregar


def _do_meu_elenco(ctx, jogador_id):
    jogador, dono = ctx.jogador(jogador_id)
    if jogador is None:
        return None
    if dono is not ctx.alvo:
        raise ContratoInvalido(f"{jogador.nome} não é do seu elenco")
    return jogador


def _tentativas(ctx, jogador_id):
    return renovacao_repo.listar_do_jogador(
        ctx.conn, ctx.sim["id"], ctx.rodada, jogador_id
    )


def ver_contrato(simulacao_id, jogador_id):
    """Contrato atual, referência de mercado e as opções de renovação. O
    salário pedido NÃO é revelado (só numa contraproposta). None se a
    simulação ou o jogador não existem."""

    conn = conectar()
    try:
        ctx = _carregar(conn, simulacao_id)
        if ctx is None:
            return None
        jogador = _do_meu_elenco(ctx, jogador_id)
        if jogador is None:
            return None

        feitas = _tentativas(ctx, jogador_id)
        ultima = feitas[-1] if feitas else None
        return {
            "jogador_id": jogador_id,
            "jogador": jogador.nome,
            "idade": jogador.idade,
            "overall": jogador.overall,
            "contrato_anos": jogador.contrato_anos,
            "salario": jogador.salario,
            "salario_referencia": jogador.salario_referencia(),
            "multa_rescisoria": jogador.multa_rescisoria,
            "valor_mercado": jogador.valor_mercado(),
            "duracao_max": contrato.duracao_max(jogador),
            "opcoes_multa": [
                {"opcao": op, "valor": contrato.valor_multa(jogador, op)}
                for op in contrato.MULTAS
            ],
            "tentativas_restantes": max(0, contrato.MAX_TENTATIVAS - len(feitas)),
            "contraproposta": (
                {
                    "salario": ultima["salario_pedido"],
                    "anos": ultima["anos"],
                    "multa": ultima["multa"],
                }
                if ultima and ultima["resposta"] == "contraproposta"
                else None
            ),
        }
    finally:
        conn.close()


def renovar(simulacao_id, jogador_id, salario, anos, multa):
    """Proposta de renovação. Devolve a resposta do jogador e, se fechou, o
    contrato novo. None se a simulação ou o jogador não existem."""

    if salario <= 0:
        raise ContratoInvalido("O salário precisa ser positivo")

    conn = conectar()
    try:
        ctx = _carregar(conn, simulacao_id)
        if ctx is None:
            return None
        jogador = _do_meu_elenco(ctx, jogador_id)
        if jogador is None:
            return None
        contrato.validar(jogador, anos, multa)   # inválida não gasta tentativa

        feitas = _tentativas(ctx, jogador_id)
        ultima = feitas[-1] if feitas else None
        # aceitar a contraproposta (mesmas condições) sempre vale
        aceitando_contra = (
            ultima is not None
            and ultima["resposta"] == "contraproposta"
            and ultima["anos"] == anos
            and ultima["multa"] == multa
            and salario >= ultima["salario_pedido"]
        )
        if len(feitas) >= contrato.MAX_TENTATIVAS and not aceitando_contra:
            raise ContratoInvalido(
                f"{jogador.nome} não quer mais conversar sobre contrato nesta "
                "rodada"
            )

        resposta = contrato.avaliar_renovacao(
            jogador, ctx.alvo, salario, anos, multa
        )

        with conn:
            renovacao_repo.inserir(
                conn, simulacao_id, ctx.rodada, jogador_id, salario, anos,
                multa, resposta.tipo,
                resposta.valor if resposta.tipo == "contraproposta" else None,
            )
            novo = None
            if resposta.fechou:
                contrato.renovar(jogador, anos, resposta.valor, multa)
                ctx.gravar()
                novo = {
                    "contrato_anos": jogador.contrato_anos,
                    "salario": jogador.salario,
                    "multa_rescisoria": jogador.multa_rescisoria,
                }

        restantes = max(0, contrato.MAX_TENTATIVAS - len(feitas) - 1)
        return {
            "resposta": resposta.tipo,
            "motivo": resposta.motivo,
            "salario_pedido": (
                resposta.valor if resposta.tipo == "contraproposta" else None
            ),
            "tentativas_restantes": 0 if resposta.fechou else restantes,
            "contrato": novo,
        }
    finally:
        conn.close()
