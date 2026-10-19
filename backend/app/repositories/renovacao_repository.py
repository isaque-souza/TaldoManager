"""Acesso à tabela `renovacao` (propostas de renovação de contrato)."""


def inserir(conn, simulacao_id, rodada, jogador_id, salario, anos, multa,
            resposta, salario_pedido=None, papel=None):
    cur = conn.execute(
        """
        INSERT INTO renovacao (simulacao_id, rodada, jogador_id, salario,
                               anos, multa, resposta, salario_pedido, papel)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (simulacao_id, rodada, jogador_id, salario, anos, multa, resposta,
         salario_pedido, papel),
    )
    return cur.lastrowid


def listar_do_jogador(conn, simulacao_id, rodada, jogador_id):
    """Tentativas por este jogador antes desta rodada, em ordem."""
    return conn.execute(
        """
        SELECT * FROM renovacao
        WHERE simulacao_id = ? AND rodada = ? AND jogador_id = ?
        ORDER BY id
        """,
        (simulacao_id, rodada, jogador_id),
    ).fetchall()
