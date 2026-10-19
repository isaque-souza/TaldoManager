"""Campanhas de marketing (v1.4): o técnico gasta caixa para a torcida
crescer. As regras ficam em `app.domain.torcida`; aqui é carregar o estado
vivo (como no mercado), cobrar, regravar e registrar a campanha.

Só saves "em andamento": uma campanha por turno, com caixa para pagar.
"""

from app.db.conexao import conectar
from app.domain import caixa, estadio, torcida
from app.repositories import campanha_repository as campanha_repo
from app.repositories import mensagem_repository as mensagem_repo
from app.services.mercado_service import _carregar


class CampanhaInvalida(ValueError):
    """Campanha desconhecida, já feita no turno ou sem caixa."""


def _feitas_no_turno(feitas, rodada, total):
    atual = torcida.turno(rodada, total)
    return sum(1 for f in feitas if torcida.turno(f["rodada"], total) == atual)


def _visao(ctx, feitas):
    clube = ctx.alvo
    total = len(ctx.campeonato.calendario)
    no_turno = _feitas_no_turno(feitas, ctx.rodada, total)
    return {
        "torcedores": clube.torcedores,
        "torcedores_inicial": clube.torcedores_inicial,
        # o mando vem do público (v1.5): o de um jogo comum em casa
        "mando_de_campo": round(estadio.mando_de_campo(estadio.publico_tipico(clube)), 2),
        "caixa": clube.dinheiro,
        "turno": torcida.turno(ctx.rodada, total),
        "disponivel": no_turno < torcida.CAMPANHAS_POR_TURNO,
        "campanhas": [
            {
                "tipo": tipo,
                "nome": c["nome"],
                "descricao": c["descricao"],
                "ganho_pct": round(c["ganho"] * 100, 1),
                "torcedores_novos": round(clube.torcedores * c["ganho"]),
                "custo": torcida.custo_da_campanha(tipo, clube.torcedores),
                "bloqueio": torcida.motivo_campanha_bloqueada(clube, tipo, no_turno),
            }
            for tipo, c in torcida.CAMPANHAS.items()
        ],
        "feitas": [
            {
                "rodada": f["rodada"],
                "nome": torcida.CAMPANHAS[f["tipo"]]["nome"],
                "custo": f["custo"],
                "torcedores_novos": f["torcedores_depois"] - f["torcedores_antes"],
            }
            for f in reversed(feitas)
        ],
    }


def ver(simulacao_id):
    """Torcida do clube dirigido e as campanhas possíveis. None se a
    simulação não existe."""
    conn = conectar()
    try:
        ctx = _carregar(conn, simulacao_id)
        if ctx is None:
            return None
        return _visao(ctx, [dict(r) for r in campanha_repo.listar(conn, simulacao_id)])
    finally:
        conn.close()


def lancar(simulacao_id, tipo):
    """Faz a campanha `tipo`. Devolve a visão atualizada; None se a
    simulação não existe; `CampanhaInvalida` se não dá."""
    conn = conectar()
    try:
        ctx = _carregar(conn, simulacao_id)
        if ctx is None:
            return None
        feitas = [dict(r) for r in campanha_repo.listar(conn, simulacao_id)]
        motivo = torcida.motivo_campanha_bloqueada(
            ctx.alvo, tipo,
            _feitas_no_turno(feitas, ctx.rodada, len(ctx.campeonato.calendario)),
        )
        if motivo:
            raise CampanhaInvalida(motivo)

        custo, antes, depois = torcida.lancar_campanha(ctx.alvo, tipo)
        with conn:
            ctx.gravar()
            campanha_repo.inserir(conn, simulacao_id, ctx.rodada, tipo, custo, antes, depois)
            mensagem_repo.inserir(conn, simulacao_id, ctx.rodada, [
                caixa.campanha(torcida.CAMPANHAS[tipo]["nome"], custo, antes, depois)
            ])
        feitas.append({"rodada": ctx.rodada, "tipo": tipo, "custo": custo,
                       "torcedores_antes": antes, "torcedores_depois": depois})
        return _visao(ctx, feitas)
    finally:
        conn.close()
