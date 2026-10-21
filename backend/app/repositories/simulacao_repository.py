"""Acesso à tabela `simulacao`."""

import json
from datetime import datetime, timezone


def _agora():
    return datetime.now(timezone.utc).isoformat()


def criar(conn, seed, campeao, rodadas, criada_em,
          clube_usuario=None, tatica=None, formacao=None, xi_preferido=None,
          estado="concluida", rodada_atual=None, estado_json=None,
          carreira_id=None, temporada=1, meta_posicao=None, ranking_forca=None,
          ligas=None, data_atual=None):
    """`ligas`: as ligas do save (v1.6), lista; None = só a Taldo.
    `data_atual`: o dia do calendário (v2.0), ISO."""
    cur = conn.execute(
        """
        INSERT INTO simulacao
            (seed, criada_em, campeao, rodadas,
             clube_usuario, tatica, formacao, xi_preferido,
             estado, rodada_atual, estado_json, carreira_id, temporada,
             atualizada_em, meta_posicao, ranking_forca, ligas, data_atual)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (seed, criada_em, campeao, rodadas,
         clube_usuario, tatica, formacao, xi_preferido,
         estado, rodada_atual, estado_json, carreira_id, temporada,
         criada_em, meta_posicao, ranking_forca,
         json.dumps(list(ligas)) if ligas else None, data_atual),
    )
    return cur.lastrowid


def atualizar_estado(conn, simulacao_id, *, estado, rodada_atual,
                     estado_json, campeao, tatica=None, formacao=None,
                     xi_preferido=None):
    """Avança (ou encerra) uma temporada em andamento. `tatica`/`formacao`/
    `xi_preferido` refletem a escolha do técnico para a rodada recém-jogada.
    Todo save do estado vivo passa por aqui, então é aqui que `atualizada_em`
    (o "jogado por último" da listagem) anda."""
    conn.execute(
        """
        UPDATE simulacao
           SET estado = ?, rodada_atual = ?, estado_json = ?, campeao = ?,
               tatica = ?, formacao = ?, xi_preferido = ?, atualizada_em = ?
         WHERE id = ?
        """,
        (estado, rodada_atual, estado_json, campeao,
         tatica, formacao, xi_preferido, _agora(), simulacao_id),
    )


def definir_livres(conn, simulacao_id, livres_json):
    """Os livres no fim da temporada (v1.6), para a virada da carreira."""
    conn.execute(
        "UPDATE simulacao SET livres_json = ? WHERE id = ?",
        (livres_json, simulacao_id),
    )


def definir_copa(conn, simulacao_id, copa_json):
    """A copa no fim da temporada (v1.6), para a tela e o histórico."""
    conn.execute(
        "UPDATE simulacao SET copa_json = ? WHERE id = ?",
        (copa_json, simulacao_id),
    )


def definir_ao_vivo(conn, simulacao_id, ao_vivo_json):
    """Abre/atualiza (JSON) ou encerra (None) a partida transmitida em curso.
    Não mexe em `atualizada_em`: só o estado vivo da temporada anda ali."""
    conn.execute(
        "UPDATE simulacao SET ao_vivo_json = ? WHERE id = ?",
        (ao_vivo_json, simulacao_id),
    )


def definir_plano_em_uso(conn, simulacao_id, plano_id):
    """O plano carregado para a próxima partida (None = nenhum)."""
    conn.execute(
        "UPDATE simulacao SET plano_em_uso = ? WHERE id = ?",
        (plano_id, simulacao_id),
    )


def listar(conn, usuario_id=None):
    """`usuario_id`: só os saves desse técnico (None = todos)."""
    # sem `estado_json` — o blob não interessa numa listagem
    filtro = "" if usuario_id is None else "WHERE usuario_id = ?"
    return conn.execute(
        f"""
        SELECT id, seed, criada_em, campeao, rodadas, clube_usuario,
               tatica, formacao, xi_preferido, estado, rodada_atual,
               carreira_id, temporada, atualizada_em, meta_posicao
        FROM simulacao
        {filtro}
        ORDER BY atualizada_em DESC, id DESC
        """,
        () if usuario_id is None else (usuario_id,),
    ).fetchall()


def definir_dono(conn, simulacao_id, usuario_id):
    conn.execute(
        "UPDATE simulacao SET usuario_id = ? WHERE id = ?",
        (usuario_id, simulacao_id),
    )


def buscar(conn, simulacao_id):
    return conn.execute(
        "SELECT * FROM simulacao WHERE id = ?", (simulacao_id,)
    ).fetchone()


def vincular_carreira(conn, simulacao_id, carreira_id, temporada):
    conn.execute(
        "UPDATE simulacao SET carreira_id = ?, temporada = ? WHERE id = ?",
        (carreira_id, temporada, simulacao_id),
    )


def sucessora(conn, simulacao_id):
    """A temporada seguinte desta na mesma carreira (ou None)."""
    return conn.execute(
        """
        SELECT prox.*
        FROM simulacao atual
        JOIN simulacao prox
          ON prox.carreira_id = atual.carreira_id
         AND prox.temporada = atual.temporada + 1
        WHERE atual.id = ?
        """,
        (simulacao_id,),
    ).fetchone()


def deletar(conn, simulacao_id):
    cur = conn.execute("DELETE FROM simulacao WHERE id = ?", (simulacao_id,))
    return cur.rowcount > 0


def antecessora(conn, simulacao_id):
    """A temporada anterior a esta na mesma carreira (ou None)."""
    return conn.execute(
        """
        SELECT ant.*
        FROM simulacao atual
        JOIN simulacao ant
          ON ant.carreira_id = atual.carreira_id
         AND ant.temporada = atual.temporada - 1
        WHERE atual.id = ?
        """,
        (simulacao_id,),
    ).fetchone()


def definir_data(conn, simulacao_id, dia):
    """O dia do calendário em que o save está (v2.0)."""
    conn.execute(
        "UPDATE simulacao SET data_atual = ? WHERE id = ?",
        (dia.isoformat() if dia else None, simulacao_id),
    )


def marcar_peneira(conn, simulacao_id, dia):
    """O dia da última peneira da base (v2.0)."""
    conn.execute(
        "UPDATE simulacao SET ultima_peneira = ? WHERE id = ?",
        (dia.isoformat(), simulacao_id),
    )
