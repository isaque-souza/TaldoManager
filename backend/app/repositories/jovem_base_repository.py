"""Acesso à tabela `jovem_base` (v2.0): a base do clube do técnico."""

from app.domain.base import Jovem


def _jovem(r):
    return Jovem(nome=r["nome"], idade=r["idade"], funcao=r["funcao"],
                 overall=r["overall"], potencial=r["potencial"], id=r["id"],
                 pais=r["pais"])


def listar(conn, simulacao_id):
    """Os jovens da base, do melhor para o pior (Jovem, chegou_em)."""
    rows = conn.execute(
        """
        SELECT * FROM jovem_base WHERE simulacao_id = ?
        ORDER BY overall DESC, potencial DESC, id
        """,
        (simulacao_id,),
    ).fetchall()
    return [(_jovem(r), r["chegou_em"]) for r in rows]


def buscar(conn, simulacao_id, jovem_id):
    """O jovem, só se for desta simulação (None se não)."""
    r = conn.execute(
        "SELECT * FROM jovem_base WHERE simulacao_id = ? AND id = ?",
        (simulacao_id, jovem_id),
    ).fetchone()
    return None if r is None else _jovem(r)


def contar(conn, simulacao_id):
    return conn.execute(
        "SELECT COUNT(*) FROM jovem_base WHERE simulacao_id = ?", (simulacao_id,)
    ).fetchone()[0]


def nomes(conn, simulacao_id):
    return {r[0] for r in conn.execute(
        "SELECT nome FROM jovem_base WHERE simulacao_id = ?", (simulacao_id,)
    )}


def inserir(conn, simulacao_id, jovens, chegou_em):
    conn.executemany(
        """
        INSERT INTO jovem_base
            (simulacao_id, nome, idade, funcao, overall, potencial, chegou_em, pais)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [(simulacao_id, j.nome, j.idade, j.funcao, j.overall, j.potencial, chegou_em, j.pais)
         for j in jovens],
    )


def atualizar(conn, jovens):
    """Regrava idade, overall e potencial (pelo id)."""
    conn.executemany(
        "UPDATE jovem_base SET idade = ?, overall = ?, potencial = ? WHERE id = ?",
        [(j.idade, j.overall, j.potencial, j.id) for j in jovens],
    )


def apagar(conn, jovem_id):
    conn.execute("DELETE FROM jovem_base WHERE id = ?", (jovem_id,))
