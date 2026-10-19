"""Acesso à tabela `jogador` (snapshot de um jogador dentro de uma simulação)."""

import json

CAMPOS = (
    "nome", "posicao", "idade", "overall", "partidas", "gols", "assistencias",
    "nota_media", "melhor_nota", "pior_nota", "melhor_em_campo",
    "clean_sheets", "hat_tricks", "amarelos", "vermelhos",
    "penaltis", "penaltis_perdidos", "faltas",
    "potencial", "contrato_anos", "valor_mercado", "salario",
    "multa_rescisoria", "numero", "funcao", "secundarias",
    "fama", "temporadas_no_clube", "a_venda",
)

# campos que dados de antes da v1.3 (posição) e da v1.4 (fama) não trazem
# (ficam NULL)
_OPCIONAIS = ("funcao", "secundarias", "fama", "temporadas_no_clube")


def _valor(j, campo):
    if campo == "a_venda":   # v1.7; NOT NULL, então sem ela é 0
        return int(bool(j.get(campo)))
    return j.get(campo) if campo in _OPCIONAIS else j[campo]


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
            (simulacao_id, mapa_clubes[j["clube"]], *(_valor(j, c) for c in CAMPOS)),
        )
        mapa[(j["clube"], j["nome"])] = cur.lastrowid

    return mapa


def atualizar(conn, simulacao_id, mapa_clubes, jogadores):
    """Regrava as stats acumuladas dos jogadores de uma temporada em andamento.
    UPDATE por (simulacao_id, nome) — e não por clube, porque com
    transferências o jogador muda de clube; o `clube_id` é regravado junto.
    Quem ainda não tem linha (um livre recém-contratado, v1.6) é inserido.
    Quem tem linha e não está em `jogadores` foi dispensado (v1.7): fica
    marcado como `livre` (e volta ao assinar de novo).
    Devolve o mesmo mapa {(clube, nome): id} que `inserir`, para ligar
    lances e atuações da rodada recém-jogada."""

    mapa = {}
    novos = []
    for j in jogadores:
        cur = conn.execute(
            f"""
            UPDATE jogador
               SET clube_id = ?, livre = 0,
                   {", ".join(f"{c} = ?" for c in CAMPOS if c != "nome")}
             WHERE simulacao_id = ? AND nome = ?
            """,
            (
                mapa_clubes[j["clube"]],
                *(_valor(j, c) for c in CAMPOS if c != "nome"),
                simulacao_id,
                j["nome"],
            ),
        )
        if cur.rowcount == 0:
            novos.append(j)
    inserir(conn, simulacao_id, mapa_clubes, novos)

    conn.execute(
        """
        UPDATE jogador SET livre = 1
         WHERE simulacao_id = ?
           AND nome NOT IN (SELECT value FROM json_each(?))
        """,
        (simulacao_id, json.dumps([j["nome"] for j in jogadores])),
    )

    for r in conn.execute(
        """
        SELECT j.id, j.nome, c.nome AS clube
        FROM jogador j JOIN clube c ON c.id = j.clube_id
        WHERE j.simulacao_id = ? AND j.livre = 0
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


def listar_por_simulacao(conn, simulacao_id, com_livres=True):
    """Todos os jogadores da temporada. `com_livres=False` deixa de fora os
    dispensados (v1.7): é o elenco de cada clube no fim dela."""
    filtro = "" if com_livres else " AND j.livre = 0"
    return conn.execute(
        _SELECT + " WHERE j.simulacao_id = ?" + filtro + " ORDER BY j.id",
        (simulacao_id,),
    ).fetchall()


def listar_por_clube(conn, clube_id):
    """O elenco do clube (sem quem ele dispensou, v1.7)."""
    return conn.execute(
        _SELECT + " WHERE j.clube_id = ? AND j.livre = 0 ORDER BY j.nota_media DESC",
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
