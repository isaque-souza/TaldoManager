"""Acesso à tabela `oferta_recebida` (ofertas da CPU pelos jogadores do
técnico, v1.7)."""


def inserir(conn, simulacao_id, rodada, jogador_id, clube, valor, teto, espontanea,
            sonho=False):
    cur = conn.execute(
        """
        INSERT INTO oferta_recebida
            (simulacao_id, rodada, jogador_id, clube, valor, teto, espontanea, sonho)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (simulacao_id, rodada, jogador_id, clube, valor, teto, int(espontanea), int(sonho)),
    )
    return cur.lastrowid


_SELECT = """
    SELECT o.*, j.nome AS jogador
    FROM oferta_recebida o JOIN jogador j ON j.id = o.jogador_id
"""


def buscar(conn, oferta_id):
    return conn.execute(_SELECT + " WHERE o.id = ?", (oferta_id,)).fetchone()


def listar_da_janela(conn, simulacao_id, rodada):
    """Todas as desta janela, as maiores primeiro."""
    return conn.execute(
        _SELECT + " WHERE o.simulacao_id = ? AND o.rodada = ? ORDER BY o.valor DESC, o.id",
        (simulacao_id, rodada),
    ).fetchall()


def jogadores_com_oferta(conn, simulacao_id, rodada):
    """Ids de quem já recebeu oferta nesta janela (qualquer status): a CPU
    não oferta duas vezes pelo mesmo jogador na mesma janela."""
    return {
        r["jogador_id"] for r in conn.execute(
            "SELECT DISTINCT jogador_id FROM oferta_recebida WHERE simulacao_id = ? AND rodada = ?",
            (simulacao_id, rodada),
        )
    }


def responder(conn, oferta_id, status, pedido=None):
    conn.execute(
        "UPDATE oferta_recebida SET status = ?, pedido = COALESCE(?, pedido) WHERE id = ?",
        (status, pedido, oferta_id),
    )


def retirar_do_jogador(conn, simulacao_id, rodada, jogador_id):
    """Ele saiu do elenco (vendido a outro, dispensado): as outras ofertas
    abertas por ele caem."""
    conn.execute(
        """
        UPDATE oferta_recebida SET status = 'retirada'
        WHERE simulacao_id = ? AND rodada = ? AND jogador_id = ? AND status = 'aberta'
        """,
        (simulacao_id, rodada, jogador_id),
    )


def expirar_abertas(conn, simulacao_id, rodada):
    """A rodada foi jogada: as ofertas abertas desta janela caem."""
    conn.execute(
        """
        UPDATE oferta_recebida SET status = 'expirada'
        WHERE simulacao_id = ? AND rodada = ? AND status = 'aberta'
        """,
        (simulacao_id, rodada),
    )


def listar_do_sonho_abertas(conn, simulacao_id, rodada):
    """As ofertas do clube do sonho ainda abertas nesta janela (v1.9): a
    rodada vai ser jogada e elas vão expirar."""
    return conn.execute(
        _SELECT + """ WHERE o.simulacao_id = ? AND o.rodada = ? AND o.sonho = 1
                        AND o.status = 'aberta'""",
        (simulacao_id, rodada),
    ).fetchall()
