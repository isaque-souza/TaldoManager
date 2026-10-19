"""Acesso à tabela `transferencia` (histórico do mercado de uma simulação).

Desde a v1.7 ela guarda também os livres contratados (`tipo` 'livre', sem
clube de origem) e as dispensas ('dispensa', sem clube de destino)."""


def inserir(conn, simulacao_id, rodada, jogador_id, de_clube_id,
            para_clube_id, valor, tipo="transferencia"):
    cur = conn.execute(
        """
        INSERT INTO transferencia
            (simulacao_id, rodada, jogador_id, de_clube_id, para_clube_id,
             valor, tipo)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (simulacao_id, rodada, jogador_id, de_clube_id, para_clube_id, valor, tipo),
    )
    return cur.lastrowid


_SELECT = """
    SELECT t.*, j.nome AS jogador, j.posicao, s.temporada,
           de.nome AS de_clube, para.nome AS para_clube
    FROM transferencia t
    JOIN simulacao s     ON s.id = t.simulacao_id
    JOIN jogador j       ON j.id = t.jogador_id
    LEFT JOIN clube de   ON de.id = t.de_clube_id
    LEFT JOIN clube para ON para.id = t.para_clube_id
"""


def listar_por_simulacao(conn, simulacao_id):
    """Mais recentes primeiro, com os nomes já resolvidos (None no clube que
    não há: o de origem de um livre, o de destino de uma dispensa)."""
    return conn.execute(
        _SELECT + " WHERE t.simulacao_id = ? ORDER BY t.id DESC",
        (simulacao_id,),
    ).fetchall()


def listar_por_carreira(conn, carreira_id):
    """As de todas as temporadas de uma carreira (v1.7), mais recentes
    primeiro."""
    return conn.execute(
        _SELECT + " WHERE s.carreira_id = ? ORDER BY s.temporada DESC, t.id DESC",
        (carreira_id,),
    ).fetchall()
