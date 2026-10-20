"""Acesso à tabela `mensagem` (caixa de entrada do técnico, v1.3)."""

from datetime import datetime, timezone

from app.domain import calendario


def _hoje(conn, simulacao_id):
    """O dia do calendário em que o save está (v2.0), em ISO."""
    sim = conn.execute(
        "SELECT temporada, rodada_atual, data_atual FROM simulacao WHERE id = ?",
        (simulacao_id,),
    ).fetchone()
    if sim is None:
        return None
    return calendario.data_atual(
        sim["temporada"], sim["rodada_atual"], sim["data_atual"],
    ).isoformat()


def inserir(conn, simulacao_id, rodada, mensagens):
    """`mensagens`: dicts com setor, assunto e corpo (app.domain.caixa). Elas
    levam o dia do calendário em que o save está."""
    agora = datetime.now(timezone.utc).isoformat()
    mensagens = [m for m in mensagens if m]
    if not mensagens:
        return
    dia = _hoje(conn, simulacao_id)
    conn.executemany(
        """
        INSERT INTO mensagem (simulacao_id, rodada, setor, assunto, corpo, criada_em, data)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (simulacao_id, rodada, m["setor"], m["assunto"], m["corpo"], agora, dia)
            for m in mensagens
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
