"""Acesso às tabelas `emprestimo` e `pedido_emprestimo` (v1.7)."""


def inserir(conn, simulacao_id, rodada, jogador_id, jogador, de_clube, para_clube,
            duracao, volta, parte_salario, taxa, opcao_compra=None):
    cur = conn.execute(
        """
        INSERT INTO emprestimo
            (simulacao_id, rodada, jogador_id, jogador, de_clube, para_clube,
             duracao, volta, parte_salario, taxa, opcao_compra)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (simulacao_id, rodada, jogador_id, jogador, de_clube, para_clube,
         duracao, volta, parte_salario, taxa, opcao_compra),
    )
    return cur.lastrowid


def buscar(conn, emprestimo_id):
    return conn.execute(
        "SELECT * FROM emprestimo WHERE id = ?", (emprestimo_id,)
    ).fetchone()


def listar_por_simulacao(conn, simulacao_id):
    """Os empréstimos da temporada, na ordem em que foram feitos."""
    return conn.execute(
        "SELECT * FROM emprestimo WHERE simulacao_id = ? ORDER BY id",
        (simulacao_id,),
    ).fetchall()


def marcar_comprado(conn, emprestimo_id):
    conn.execute("UPDATE emprestimo SET comprado = 1 WHERE id = ?", (emprestimo_id,))


# --- pedidos ----------------------------------------------------------------

def inserir_pedido(conn, simulacao_id, rodada, jogador_id, duracao, parte_salario,
                   opcao, taxa, resposta, taxa_pedida=None):
    cur = conn.execute(
        """
        INSERT INTO pedido_emprestimo
            (simulacao_id, rodada, jogador_id, duracao, parte_salario, opcao,
             taxa, resposta, taxa_pedida)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (simulacao_id, rodada, jogador_id, duracao, parte_salario, int(opcao),
         taxa, resposta, taxa_pedida),
    )
    return cur.lastrowid


def listar_pedidos_da_janela(conn, simulacao_id, rodada):
    """Pedidos feitos antes desta rodada (uma janela), em ordem."""
    return conn.execute(
        """
        SELECT * FROM pedido_emprestimo
        WHERE simulacao_id = ? AND rodada = ?
        ORDER BY id
        """,
        (simulacao_id, rodada),
    ).fetchall()
