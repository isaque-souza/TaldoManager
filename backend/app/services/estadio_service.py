"""Estádio (v1.5): capacidade, faixa do ingresso e o público da temporada.
As regras ficam em `app.domain.estadio`; aqui é carregar o estado vivo
(como no mercado), trocar a faixa, regravar e somar os jogos em casa.

Só saves "em andamento": a faixa vale a partir do próximo jogo em casa.
"""

from app.db.conexao import conectar
from app.domain import estadio
from app.repositories import clube_repository as clube_repo
from app.repositories import partida_repository as partida_repo
from app.services.mercado_service import _carregar


class IngressoInvalido(ValueError):
    """Faixa de ingresso desconhecida."""


def _temporada(conn, simulacao_id, clube):
    """Os jogos em casa já disputados: público médio, ocupação e lotados."""
    clube_id = next(
        r["id"] for r in clube_repo.listar_por_simulacao(conn, simulacao_id)
        if r["nome"] == clube.nome
    )
    publicos = [
        p["publico"] for p in partida_repo.listar_por_clube(conn, clube_id)
        if p["mandante_id"] == clube_id and p["publico"] is not None
    ]
    medio = round(sum(publicos) / len(publicos)) if publicos else 0
    return {
        "jogos_em_casa": len(publicos),
        "publico_medio": medio,
        "ocupacao_media": round(estadio.ocupacao(medio, clube.capacidade) * 100, 1),
        "lotados": sum(1 for p in publicos if p >= clube.capacidade),
        "bilheteria": clube.receita_bilheteria,
    }


def _visao(conn, ctx):
    clube = ctx.alvo
    faixas = []
    for faixa, f in estadio.FAIXAS.items():
        publico = estadio.publico_tipico(clube, faixa)
        faixas.append({
            "faixa": faixa,
            "nome": f["nome"],
            "descricao": f["descricao"],
            "preco": round(estadio.preco(clube, faixa), 2),
            "publico": publico,
            "ocupacao": round(estadio.ocupacao(publico, clube.capacidade) * 100, 1),
            "bilheteria": round(publico * estadio.preco(clube, faixa)),
            "mando_de_campo": round(estadio.mando_de_campo(publico), 2),
        })
    return {
        "capacidade": clube.capacidade,
        "ingresso": clube.ingresso,
        "torcedores": clube.torcedores,
        "caixa": clube.dinheiro,
        "faixas": faixas,
        "temporada": _temporada(conn, ctx.sim["id"], clube),
    }


def ver(simulacao_id):
    """Estádio do clube dirigido. None se a simulação não existe."""
    conn = conectar()
    try:
        ctx = _carregar(conn, simulacao_id)
        if ctx is None:
            return None
        return _visao(conn, ctx)
    finally:
        conn.close()


def definir_ingresso(simulacao_id, faixa):
    """Troca a faixa do ingresso. Devolve a visão atualizada; None se a
    simulação não existe; `IngressoInvalido` se a faixa não existe."""
    motivo = estadio.motivo_faixa_invalida(faixa)
    if motivo:
        raise IngressoInvalido(motivo)

    conn = conectar()
    try:
        ctx = _carregar(conn, simulacao_id)
        if ctx is None:
            return None
        ctx.alvo.ingresso = faixa
        with conn:
            ctx.gravar()
        return _visao(conn, ctx)
    finally:
        conn.close()
