"""Acesso à tabela `jogador` (snapshot de um jogador dentro de uma simulação)."""

CAMPOS = (
    "nome", "posicao", "idade", "overall", "partidas", "gols", "assistencias",
    "nota_media", "melhor_nota", "pior_nota", "melhor_em_campo",
    "clean_sheets", "hat_tricks", "amarelos", "vermelhos",
    "penaltis", "penaltis_perdidos", "faltas",
    "potencial", "contrato_anos", "valor_mercado", "salario",
    "multa_rescisoria",
)


def inserir(conn, simulacao_id, mapa_clubes, jogadores):
    """`jogadores` são dicts com os CAMPOS + a chave "clube" (nome do clube).

    Devolve um mapa {(clube, nome): id} para ligar lances e atuações."""

    mapa = {}
    for j in jogadores:
        cur = conn.execute(
            f"""
            INSERT INTO jogador (simulacao_id, clube_id, {", ".join(CAMPOS)})
            VALUES (?, ?, {", ".join("?" * len(CAMPOS))})
            """,
            (simulacao_id, mapa_clubes[j["clube"]], *(j[c] for c in CAMPOS)),
        )
        mapa[(j["clube"], j["nome"])] = cur.lastrowid

    return mapa


def atualizar(conn, simulacao_id, mapa_clubes, jogadores):
    """Regrava as stats acumuladas dos jogadores de uma temporada em andamento.
    UPDATE por (simulacao_id, nome) — e não por clube, porque com
    transferências o jogador muda de clube; o `clube_id` é regravado junto.
    Devolve o mesmo mapa {(clube, nome): id} que `inserir`, para ligar
    lances e atuações da rodada recém-jogada."""

    mapa = {}
    for j in jogadores:
        conn.execute(
            f"""
            UPDATE jogador
               SET clube_id = ?,
                   {", ".join(f"{c} = ?" for c in CAMPOS if c != "nome")}
             WHERE simulacao_id = ? AND nome = ?
            """,
            (
                mapa_clubes[j["clube"]],
                *(j[c] for c in CAMPOS if c != "nome"),
                simulacao_id,
                j["nome"],
            ),
        )

    for r in conn.execute(
        """
        SELECT j.id, j.nome, c.nome AS clube
        FROM jogador j JOIN clube c ON c.id = j.clube_id
        WHERE j.simulacao_id = ?
        """,
        (simulacao_id,),
    ):
        mapa[(r["clube"], r["nome"])] = r["id"]

    return mapa


# traz o nome do clube junto (a visão e o frontend usam "clube")
_SELECT = """
    SELECT j.*, c.nome AS clube
    FROM jogador j
    JOIN clube c ON c.id = j.clube_id
"""


def listar_por_simulacao(conn, simulacao_id):
    return conn.execute(
        _SELECT + " WHERE j.simulacao_id = ?", (simulacao_id,)
    ).fetchall()


def listar_por_clube(conn, clube_id):
    return conn.execute(
        _SELECT + " WHERE j.clube_id = ? ORDER BY j.nota_media DESC",
        (clube_id,),
    ).fetchall()


def buscar_por_nome(conn, simulacao_id, nome):
    return conn.execute(
        _SELECT + " WHERE j.simulacao_id = ? AND j.nome = ?", (simulacao_id, nome)
    ).fetchone()


def buscar(conn, jogador_id):
    return conn.execute(
        _SELECT + " WHERE j.id = ?", (jogador_id,)
    ).fetchone()
