"""Olheiro profissional (v2.0): ver o nível e trocá-lo. As regras ficam em
`app.domain.olheiro`; aqui é carregar o estado vivo (como no estádio),
cobrar a troca e regravar.

Só saves "em andamento". A estimativa do potencial que o olheiro faz
aparece nas fichas do mercado (`mercado_service`) e na página do jogador
(`simulacao_service.game_log_jogador`).
"""

from app.db.conexao import conectar
from app.domain import olheiro
from app.services.mercado_service import _carregar


class TrocaInvalida(ValueError):
    """Nível que não existe, o mesmo de agora ou sem caixa."""


def _visao(ctx):
    return olheiro.resumo(ctx.alvo, ctx.rodada - 1, len(ctx.campeonato.calendario))


def ver(simulacao_id):
    """O olheiro do clube dirigido. None se a simulação não existe."""
    conn = conectar()
    try:
        ctx = _carregar(conn, simulacao_id)
        if ctx is None:
            return None
        return _visao(ctx)
    finally:
        conn.close()


def trocar(simulacao_id, nivel):
    """Troca o olheiro pelo de `nivel`, pagando a diferença até o fim da
    temporada (descer é de graça). Devolve a visão atualizada; None se a
    simulação não existe; `TrocaInvalida` se não dá."""
    try:
        olheiro.validar(nivel)
    except olheiro.NivelInvalido as e:
        raise TrocaInvalida(str(e)) from e

    conn = conectar()
    try:
        ctx = _carregar(conn, simulacao_id)
        if ctx is None:
            return None
        clube = ctx.alvo
        custo = olheiro.custo_da_troca(
            clube.nivel_olheiro, nivel, ctx.rodada - 1, len(ctx.campeonato.calendario),
        )
        motivo = olheiro.motivo_troca_bloqueada(clube, nivel, custo)
        if motivo:
            raise TrocaInvalida(motivo)
        if custo:
            clube.lancar("despesa_olheiros", custo)
        clube.nivel_olheiro = nivel
        with conn:
            ctx.gravar()
        return _visao(ctx)
    finally:
        conn.close()
