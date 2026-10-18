"""Acesso à tabela `plano` (planos de jogo do técnico, v1.2)."""

import json


def _dict(r):
    return {
        "id": r["id"],
        "nome": r["nome"],
        "formacao": r["formacao"],
        "tatica": r["tatica"],
        "xi": json.loads(r["xi"]),
        "padrao": bool(r["padrao"]),
    }


def listar(conn, simulacao_id):
    rows = conn.execute(
        "SELECT * FROM plano WHERE simulacao_id = ? ORDER BY id",
        (simulacao_id,),
    ).fetchall()
    return [_dict(r) for r in rows]


def buscar(conn, simulacao_id, plano_id):
    r = conn.execute(
        "SELECT * FROM plano WHERE simulacao_id = ? AND id = ?",
        (simulacao_id, plano_id),
    ).fetchone()
    return _dict(r) if r else None


def criar(conn, simulacao_id, nome, formacao, tatica, xi, padrao=False):
    cur = conn.execute(
        """
        INSERT INTO plano (simulacao_id, nome, formacao, tatica, xi, padrao)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (simulacao_id, nome, formacao, tatica,
         json.dumps(xi, ensure_ascii=False), int(padrao)),
    )
    return cur.lastrowid


def atualizar(conn, plano_id, nome, formacao, tatica, xi):
    conn.execute(
        "UPDATE plano SET nome = ?, formacao = ?, tatica = ?, xi = ? WHERE id = ?",
        (nome, formacao, tatica, json.dumps(xi, ensure_ascii=False), plano_id),
    )


def definir_padrao(conn, simulacao_id, plano_id):
    """Só um padrão por save: marca este e desmarca os outros."""
    conn.execute(
        "UPDATE plano SET padrao = (id = ?) WHERE simulacao_id = ?",
        (plano_id, simulacao_id),
    )


def deletar(conn, plano_id):
    conn.execute("DELETE FROM plano WHERE id = ?", (plano_id,))
