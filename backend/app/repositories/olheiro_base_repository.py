"""Acesso às tabelas `missao_base` e `indicado_base` (v2.0): os olheiros da
base em missão e os jovens que eles indicaram."""

from datetime import date, timedelta

from app.domain.base import Jovem


# --- missões ----------------------------------------------------------------

def listar_missoes(conn, simulacao_id):
    return conn.execute(
        "SELECT * FROM missao_base WHERE simulacao_id = ? ORDER BY proximo_relatorio, id",
        (simulacao_id,),
    ).fetchall()


def inserir_missao(conn, simulacao_id, regiao, meses, enviado_em, proximo, custo):
    conn.execute(
        """
        INSERT INTO missao_base
            (simulacao_id, regiao, meses, enviado_em, proximo_relatorio, custo)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (simulacao_id, regiao, meses, enviado_em, proximo, custo),
    )


def proximo_relatorio(conn, simulacao_id):
    """O dia (ISO) do próximo relatório, ou None."""
    return conn.execute(
        "SELECT MIN(proximo_relatorio) FROM missao_base WHERE simulacao_id = ?",
        (simulacao_id,),
    ).fetchone()[0]


def vencidas(conn, simulacao_id, dia):
    """A missão com relatório até `dia` (ISO) que vence primeiro, ou None."""
    return conn.execute(
        """
        SELECT * FROM missao_base WHERE simulacao_id = ? AND proximo_relatorio <= ?
        ORDER BY proximo_relatorio, id LIMIT 1
        """,
        (simulacao_id, dia),
    ).fetchone()


def avancar_missao(conn, missao_id, proximo):
    conn.execute(
        """
        UPDATE missao_base SET relatorios_feitos = relatorios_feitos + 1,
            proximo_relatorio = ? WHERE id = ?
        """,
        (proximo, missao_id),
    )


def encerrar_missao(conn, missao_id):
    conn.execute("DELETE FROM missao_base WHERE id = ?", (missao_id,))


# --- indicados ----------------------------------------------------------------

def _jovem(r):
    return Jovem(nome=r["nome"], idade=r["idade"], funcao=r["funcao"],
                 overall=r["overall"], potencial=r["potencial"], id=r["id"],
                 pais=r["pais"])


def listar_indicados(conn, simulacao_id):
    """[(Jovem, linha)] do melhor para o pior."""
    rows = conn.execute(
        """
        SELECT * FROM indicado_base WHERE simulacao_id = ?
        ORDER BY overall DESC, potencial DESC, id
        """,
        (simulacao_id,),
    ).fetchall()
    return [(_jovem(r), r) for r in rows]


def buscar_indicado(conn, simulacao_id, indicado_id):
    r = conn.execute(
        "SELECT * FROM indicado_base WHERE simulacao_id = ? AND id = ?",
        (simulacao_id, indicado_id),
    ).fetchone()
    return None if r is None else _jovem(r)


def nomes_indicados(conn, simulacao_id):
    return {r[0] for r in conn.execute(
        "SELECT nome FROM indicado_base WHERE simulacao_id = ?", (simulacao_id,)
    )}


def inserir_indicados(conn, simulacao_id, regiao, jovens, chegou_em, expira_em):
    conn.executemany(
        """
        INSERT INTO indicado_base
            (simulacao_id, regiao, nome, idade, funcao, overall, potencial, pais,
             chegou_em, expira_em)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [(simulacao_id, regiao, j.nome, j.idade, j.funcao, j.overall, j.potencial,
          j.pais, chegou_em, expira_em) for j in jovens],
    )


def expirar_indicados(conn, simulacao_id, dia):
    """Tira os indicados com prazo até `dia` (ISO)."""
    conn.execute(
        "DELETE FROM indicado_base WHERE simulacao_id = ? AND expira_em <= ?",
        (simulacao_id, dia),
    )


def apagar_indicado(conn, indicado_id):
    conn.execute("DELETE FROM indicado_base WHERE id = ?", (indicado_id,))


# --- virada -------------------------------------------------------------------

def _adiar(iso, dias):
    return (date.fromisoformat(iso) + timedelta(days=dias)).isoformat()


def mover(conn, de_id, para_id, dias):
    """Leva missões e indicados para a temporada nova, com as datas
    adiadas em `dias` (as férias entre uma temporada e outra não contam)."""
    for m in listar_missoes(conn, de_id):
        conn.execute(
            "UPDATE missao_base SET simulacao_id = ?, proximo_relatorio = ? WHERE id = ?",
            (para_id, _adiar(m["proximo_relatorio"], dias), m["id"]),
        )
    for _, r in listar_indicados(conn, de_id):
        conn.execute(
            "UPDATE indicado_base SET simulacao_id = ?, expira_em = ? WHERE id = ?",
            (para_id, _adiar(r["expira_em"], dias), r["id"]),
        )
