"""Acesso à tabela `movimento_virada` (v0.8)."""

CAMPOS = ("tipo", "jogador", "clube", "posicao", "idade", "overall", "detalhe")


def inserir(conn, simulacao_id, movimentos):
    conn.executemany(
        f"""
        INSERT INTO movimento_virada (simulacao_id, {", ".join(CAMPOS)})
        VALUES (?, {", ".join("?" * len(CAMPOS))})
        """,
        [(simulacao_id, *(m[c] for c in CAMPOS)) for m in movimentos],
    )


def listar_por_simulacao(conn, simulacao_id):
    return conn.execute(
        f"SELECT {', '.join(CAMPOS)} FROM movimento_virada"
        " WHERE simulacao_id = ? ORDER BY id",
        (simulacao_id,),
    ).fetchall()
