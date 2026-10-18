"""Acesso à tabela `mensagem` (caixa de entrada do técnico, v1.3)."""

from datetime import datetime, timezone


def inserir(conn, simulacao_id, rodada, mensagens):
    """`mensagens`: dicts com setor, assunto e corpo (app.domain.caixa)."""
    agora = datetime.now(timezone.utc).isoformat()
    conn.executemany(
        """
        INSERT INTO mensagem (simulacao_id, rodada, setor, assunto, corpo, criada_em)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (simulacao_id, rodada, m["setor"], m["assunto"], m["corpo"], agora)
            for m in mensagens if m
        ],
    )


def listar(conn, simulacao_id):
    """Da mais nova para a mais antiga."""
    rows = conn.execute(
        "SELECT * FROM mensagem WHERE simulacao_id = ? ORDER BY id DESC",
        (simulacao_id,),
    ).fetchall()
    return [{**dict(r), "lida": bool(r["lida"])} for r in rows]


def marcar_lida(conn, simulacao_id, mensagem_id):
    cur = conn.execute(
        "UPDATE mensagem SET lida = 1 WHERE simulacao_id = ? AND id = ?",
        (simulacao_id, mensagem_id),
    )
    return cur.rowcount > 0


def marcar_todas(conn, simulacao_id):
    conn.execute("UPDATE mensagem SET lida = 1 WHERE simulacao_id = ?", (simulacao_id,))
