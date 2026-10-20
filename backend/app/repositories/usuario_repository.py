"""Acesso às tabelas `usuario` e `sessao` (v2.1)."""


def criar(conn, nome, senha_hash, criado_em):
    cur = conn.execute(
        "INSERT INTO usuario (nome, senha_hash, criado_em) VALUES (?, ?, ?)",
        (nome, senha_hash, criado_em),
    )
    return cur.lastrowid


def buscar_por_nome(conn, nome):
    # a coluna é COLLATE NOCASE: "Isaque" e "isaque" são a mesma conta
    return conn.execute(
        "SELECT * FROM usuario WHERE nome = ?", (nome,)
    ).fetchone()


def buscar(conn, usuario_id):
    return conn.execute(
        "SELECT * FROM usuario WHERE id = ?", (usuario_id,)
    ).fetchone()


def criar_sessao(conn, token_hash, usuario_id, expira_em):
    conn.execute(
        "INSERT INTO sessao (token_hash, usuario_id, expira_em) VALUES (?, ?, ?)",
        (token_hash, usuario_id, expira_em),
    )


def buscar_sessao(conn, token_hash):
    return conn.execute(
        "SELECT * FROM sessao WHERE token_hash = ?", (token_hash,)
    ).fetchone()


def apagar_sessao(conn, token_hash):
    conn.execute("DELETE FROM sessao WHERE token_hash = ?", (token_hash,))


def apagar_sessoes_vencidas(conn, agora):
    conn.execute("DELETE FROM sessao WHERE expira_em < ?", (agora,))


def dono_da_simulacao(conn, simulacao_id):
    """(existe, usuario_id) do save."""
    r = conn.execute(
        "SELECT usuario_id FROM simulacao WHERE id = ?", (simulacao_id,)
    ).fetchone()
    return (False, None) if r is None else (True, r["usuario_id"])


def donos_da_carreira(conn, carreira_id):
    """Os donos das temporadas da carreira (normalmente um só)."""
    rows = conn.execute(
        "SELECT DISTINCT usuario_id FROM simulacao WHERE carreira_id = ?",
        (carreira_id,),
    ).fetchall()
    return {r["usuario_id"] for r in rows}


def contar_jogos(conn, usuario_id):
    """Jogos do técnico: cada carreira conta uma vez, cada save avulso, um."""
    r = conn.execute(
        """
        SELECT COUNT(DISTINCT COALESCE('c' || carreira_id, 's' || id)) AS n
        FROM simulacao WHERE usuario_id = ?
        """,
        (usuario_id,),
    ).fetchone()
    return r["n"]


def dar_saves_sem_dono(conn, usuario_id):
    cur = conn.execute(
        "UPDATE simulacao SET usuario_id = ? WHERE usuario_id IS NULL",
        (usuario_id,),
    )
    return cur.rowcount
