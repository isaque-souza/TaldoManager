"""Acesso à tabela `campanha` (campanhas de marketing do técnico, v1.4)."""


def inserir(conn, simulacao_id, rodada, tipo, custo, antes, depois):
    conn.execute(
        """
        INSERT INTO campanha (simulacao_id, rodada, tipo, custo,
                              torcedores_antes, torcedores_depois)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (simulacao_id, rodada, tipo, custo, antes, depois),
    )


def listar(conn, simulacao_id):
    """Da mais antiga para a mais nova."""
    return conn.execute(
        "SELECT * FROM campanha WHERE simulacao_id = ? ORDER BY id",
        (simulacao_id,),
    ).fetchall()
