"""Acesso à tabela `observado` (v1.7): a lista de jogadores que o técnico
acompanha, pelo nome."""


def listar(conn, simulacao_id):
    """Na ordem em que entraram na lista."""
    return conn.execute(
        "SELECT * FROM observado WHERE simulacao_id = ? ORDER BY id",
        (simulacao_id,),
    ).fetchall()


def inserir(conn, simulacao_id, nome, clube, overall, valor, temporada, rodada):
    """Põe na lista; quem já está fica como estava."""
    conn.execute(
        """
        INSERT OR IGNORE INTO observado
            (simulacao_id, nome, clube, overall, valor, temporada, rodada)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (simulacao_id, nome, clube, overall, valor, temporada, rodada),
    )


def remover(conn, simulacao_id, nome):
    conn.execute(
        "DELETE FROM observado WHERE simulacao_id = ? AND nome = ?",
        (simulacao_id, nome),
    )


def copiar(conn, de_simulacao, para_simulacao):
    """Virada de temporada: a lista segue como está (com o "desde" de
    quando cada um entrou)."""
    conn.execute(
        """
        INSERT INTO observado
            (simulacao_id, nome, clube, overall, valor, temporada, rodada)
        SELECT ?, nome, clube, overall, valor, temporada, rodada
        FROM observado WHERE simulacao_id = ? ORDER BY id
        """,
        (para_simulacao, de_simulacao),
    )
