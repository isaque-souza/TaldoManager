"""Autosave da escalação (v0.9).

Tática, formação e XI titular de uma temporada em andamento são gravados
sem jogar a rodada — o técnico monta o time, fecha a página e, ao voltar,
está tudo lá. A fonte da verdade continua sendo o estado vivo
(`simulacao.estado_json`): é ele que `proxima_rodada` mostra e `avancar` usa.

Salvar a decisão e depois jogar sem corpo dá exatamente a mesma rodada que
jogar mandando a decisão: nada aqui sorteia, e o snapshot mantém a corrente
de RNG da temporada (o mesmo cuidado do mercado — ver `_Contexto.gravar`).
"""

import json

from app.db.conexao import conectar
from app.repositories import simulacao_repository as simulacao_repo
from app.services import simulacao_service
from app.services.mercado_service import _carregar
from app.services.temporada_service import TemporadaConcluida


def salvar_decisao(simulacao_id, tatica=None, formacao=None, xi_preferido=None,
                   posicionamento=None):
    """Grava a escalação do técnico para a próxima rodada. O que não vier
    fica como está (mesma regra do `avancar`). None se a simulação não
    existe; `TemporadaConcluida` se já terminou; ValueError se a escolha não
    bate com o elenco."""

    conn = conectar()
    try:
        sim = simulacao_repo.buscar(conn, simulacao_id)
        if sim is None:
            return None
        if sim["estado"] != "em_andamento":
            raise TemporadaConcluida("Esta temporada já foi concluída")

        ctx = _carregar(conn, simulacao_id)
        alvo = ctx.alvo
        simulacao_service._configurar_clube(
            alvo, tatica or alvo.tatica, formacao or alvo.formacao,
            xi_preferido, posicionamento,
        )

        with conn:
            ctx.gravar()

        gravada = simulacao_repo.buscar(conn, simulacao_id)
        return {
            "tatica": gravada["tatica"],
            "formacao": gravada["formacao"],
            "xi_preferido": (
                json.loads(gravada["xi_preferido"])
                if gravada["xi_preferido"] else None
            ),
            "atualizada_em": gravada["atualizada_em"],
        }
    finally:
        conn.close()
