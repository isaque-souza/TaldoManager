"""Acesso à tabela `relatorio` (v2.0): os relatórios de contratação que o
olheiro faz, pelo nome do jogador."""


def listar(conn, simulacao_id):
    """Na ordem em que foram pedidos."""
    return conn.execute(
        "SELECT * FROM relatorio WHERE simulacao_id = ? ORDER BY id",
        (simulacao_id,),
    ).fetchall()


def inserir(conn, simulacao_id, nome, pedido_em, pronto_em):
    conn.execute(
        """
        INSERT INTO relatorio (simulacao_id, nome, pedido_em, pronto_em)
        VALUES (?, ?, ?, ?)
        """,
        (simulacao_id, nome, pedido_em, pronto_em),
    )


def marcar_prontos(conn, simulacao_id, ate):
    """Os que ficaram prontos até o dia `ate` (ISO): marca e devolve os nomes."""
    nomes = [
        r["nome"] for r in conn.execute(
            "SELECT nome FROM relatorio WHERE simulacao_id = ? AND pronto = 0 "
            "AND pronto_em <= ? ORDER BY pronto_em, id",
            (simulacao_id, ate),
        )
    ]
    conn.execute(
        "UPDATE relatorio SET pronto = 1 WHERE simulacao_id = ? AND pronto = 0 AND pronto_em <= ?",
        (simulacao_id, ate),
    )
    return nomes


def proximo_pronto(conn, simulacao_id):
    """O dia (ISO) em que o próximo relatório fica pronto, ou None."""
    r = conn.execute(
        "SELECT MIN(pronto_em) AS dia FROM relatorio WHERE simulacao_id = ? AND pronto = 0",
        (simulacao_id,),
    ).fetchone()
    return r["dia"]
