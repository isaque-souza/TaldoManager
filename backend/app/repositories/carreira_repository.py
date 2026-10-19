"""Acesso à tabela `carreira` (v0.8): um save que atravessa temporadas."""


def criar(conn, clube_usuario, seed, criada_em):
    cur = conn.execute(
        "INSERT INTO carreira (clube_usuario, seed, criada_em) VALUES (?, ?, ?)",
        (clube_usuario, seed, criada_em),
    )
    return cur.lastrowid


def buscar(conn, carreira_id):
    return conn.execute(
        "SELECT * FROM carreira WHERE id = ?", (carreira_id,)
    ).fetchone()


def listar_temporadas(conn, carreira_id):
    """As simulações da carreira, da temporada 1 em diante."""
    return conn.execute(
        """
        SELECT id, temporada, seed, campeao, estado, rodada_atual, rodadas,
               copa_json
        FROM simulacao
        WHERE carreira_id = ?
        ORDER BY temporada
        """,
        (carreira_id,),
    ).fetchall()
