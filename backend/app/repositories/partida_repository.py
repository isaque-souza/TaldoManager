"""Acesso à tabela `partida`."""

CAMPOS = (
    "rodada", "gols_mandante", "gols_visitante", "posse_mandante",
    "finalizacoes_mandante", "finalizacoes_visitante",
    "finalizacoes_gol_mandante", "finalizacoes_gol_visitante",
    "escanteios_mandante", "escanteios_visitante", "acrescimos",
    "publico",
)

# campos que partidas de antes não trazem (ficam NULL)
_OPCIONAIS = ("publico",)


def inserir(conn, simulacao_id, mapa_clubes, partidas):
    """`partidas` são dicts com os CAMPOS + "mandante"/"visitante" (nomes).

    Devolve a lista de ids gerados, na mesma ordem de `partidas`, para ligar
    lances e atuações."""

    ids = []
    for p in partidas:
        cur = conn.execute(
            f"""
            INSERT INTO partida
                (simulacao_id, mandante_id, visitante_id, {", ".join(CAMPOS)})
            VALUES (?, ?, ?, {", ".join("?" * len(CAMPOS))})
            """,
            (
                simulacao_id,
                mapa_clubes[p["mandante"]],
                mapa_clubes[p["visitante"]],
                *(p.get(c) if c in _OPCIONAIS else p[c] for c in CAMPOS),
            ),
        )
        ids.append(cur.lastrowid)

    return ids


def _com_nomes(conn, where, params):
    """Junta os nomes dos clubes para não precisar de outra query no serviço."""
    return conn.execute(
        f"""
        SELECT
            p.*,
            m.nome AS mandante_nome,
            v.nome AS visitante_nome
        FROM partida p
        JOIN clube m ON m.id = p.mandante_id
        JOIN clube v ON v.id = p.visitante_id
        WHERE {where}
        ORDER BY p.rodada, p.id
        """,
        params,
    ).fetchall()


def listar_por_simulacao(conn, simulacao_id):
    return _com_nomes(conn, "p.simulacao_id = ?", (simulacao_id,))


def listar_por_clube(conn, clube_id):
    return _com_nomes(
        conn, "p.mandante_id = ? OR p.visitante_id = ?", (clube_id, clube_id)
    )


def buscar(conn, partida_id):
    linhas = _com_nomes(conn, "p.id = ?", (partida_id,))
    return linhas[0] if linhas else None
