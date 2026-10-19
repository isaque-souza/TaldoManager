"""Acesso à tabela `clube` (snapshot de um clube dentro de uma simulação)."""

CAMPOS = (
    "nome", "pais", "posicao_final", "pontos", "jogos",
    "vitorias", "empates", "derrotas", "gols_marcados", "gols_sofridos",
    "dinheiro_inicial", "dinheiro", "receita_tv", "receita_bilheteria",
    "receita_premiacao", "despesa_salarios",
    "receita_vendas", "despesa_compras", "historico_caixa",
    "torcedores", "torcedores_inicial", "despesa_marketing",
    "torcedores_base", "capacidade", "ingresso", "liga",
)

# campos mais novos que quem monta os dicts pode não mandar
_PADRAO = {
    "torcedores": 0, "torcedores_inicial": 0, "despesa_marketing": 0,
    "torcedores_base": 0, "capacidade": 0, "ingresso": "normal",
    "liga": "taldo",
}


def _valor(clube, campo):
    return clube[campo] if campo in clube or campo not in _PADRAO else _PADRAO[campo]


def inserir(conn, simulacao_id, clubes):
    """Insere os clubes e devolve um mapa {nome: id} para ligar jogadores
    e partidas."""

    mapa = {}
    for clube in clubes:
        cur = conn.execute(
            f"""
            INSERT INTO clube (simulacao_id, {", ".join(CAMPOS)})
            VALUES (?, {", ".join("?" * len(CAMPOS))})
            """,
            (simulacao_id, *(_valor(clube, c) for c in CAMPOS)),
        )
        mapa[clube["nome"]] = cur.lastrowid

    return mapa


def atualizar(conn, simulacao_id, clubes):
    """Regrava as stats acumuladas dos clubes de uma temporada em andamento.
    Faz UPDATE por (simulacao_id, nome) — não dá pra apagar e reinserir porque
    as partidas já jogadas apontam pra `clube.id` com ON DELETE CASCADE."""

    for clube in clubes:
        conn.execute(
            f"""
            UPDATE clube
               SET {", ".join(f"{c} = ?" for c in CAMPOS if c != "nome")}
             WHERE simulacao_id = ? AND nome = ?
            """,
            (
                *(_valor(clube, c) for c in CAMPOS if c != "nome"),
                simulacao_id,
                clube["nome"],
            ),
        )

    return {
        r["nome"]: r["id"]
        for r in conn.execute(
            "SELECT id, nome FROM clube WHERE simulacao_id = ?", (simulacao_id,)
        )
    }


def listar_por_simulacao(conn, simulacao_id):
    return conn.execute(
        "SELECT * FROM clube WHERE simulacao_id = ? ORDER BY posicao_final",
        (simulacao_id,),
    ).fetchall()


def buscar(conn, clube_id):
    return conn.execute(
        "SELECT * FROM clube WHERE id = ?", (clube_id,)
    ).fetchone()
