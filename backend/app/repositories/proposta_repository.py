"""Acesso à tabela `proposta` (negociações de compra do técnico)."""


def inserir(conn, simulacao_id, rodada, jogador_id, valor, resposta,
            valor_pedido=None):
    cur = conn.execute(
        """
        INSERT INTO proposta
            (simulacao_id, rodada, jogador_id, valor, resposta, valor_pedido)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (simulacao_id, rodada, jogador_id, valor, resposta, valor_pedido),
    )
    return cur.lastrowid


def listar_da_janela(conn, simulacao_id, rodada):
    """Propostas feitas antes desta rodada (uma janela), na ordem em que
    foram feitas."""
    return conn.execute(
        """
        SELECT * FROM proposta
        WHERE simulacao_id = ? AND rodada = ?
        ORDER BY id
        """,
        (simulacao_id, rodada),
    ).fetchall()
