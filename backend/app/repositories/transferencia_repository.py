"""Acesso à tabela `transferencia` (histórico do mercado de uma simulação)."""


def inserir(conn, simulacao_id, rodada, jogador_id, de_clube_id,
            para_clube_id, valor):
    cur = conn.execute(
        """
        INSERT INTO transferencia
            (simulacao_id, rodada, jogador_id, de_clube_id, para_clube_id, valor)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (simulacao_id, rodada, jogador_id, de_clube_id, para_clube_id, valor),
    )
    return cur.lastrowid


def listar_por_simulacao(conn, simulacao_id):
    """Mais recentes primeiro, com os nomes já resolvidos."""
    return conn.execute(
        """
        SELECT t.*, j.nome AS jogador, j.posicao,
               de.nome AS de_clube, para.nome AS para_clube
        FROM transferencia t
        JOIN jogador j  ON j.id = t.jogador_id
        JOIN clube de   ON de.id = t.de_clube_id
        JOIN clube para ON para.id = t.para_clube_id
        WHERE t.simulacao_id = ?
        ORDER BY t.id DESC
        """,
        (simulacao_id,),
    ).fetchall()
