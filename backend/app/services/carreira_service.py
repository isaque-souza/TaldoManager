"""Modo carreira (v0.8): continuar um save na temporada seguinte.

A carreira nasce sob demanda: a primeira vez que uma temporada concluída é
continuada, ela vira a temporada 1 de uma carreira nova. Assim qualquer save
antigo com clube dirigido pode virar carreira, sem migrar dados.
"""

import json
import random
from datetime import datetime, timezone

from app.db.conexao import conectar
from app.domain.base import subir_jovens
from app.domain.carreira import (
    aposentar,
    envelhecer,
    preparar_nova_temporada,
    resolver_contratos,
    seed_da_temporada,
)
from app.domain.temporada import snapshot_estado
from app.repositories import carreira_repository as carreira_repo
from app.repositories import clube_repository as clube_repo
from app.repositories import jogador_repository as jogador_repo
from app.repositories import movimento_repository as movimento_repo
from app.repositories import simulacao_repository as simulacao_repo
from app.services import simulacao_service
from scripts.data_loader import carregar_campeonato, carregar_jogadores


class CarreiraInvalida(Exception):
    """A temporada não pode ser continuada (em andamento, sem clube dirigido
    ou já continuada)."""


def _nomes_usados(conn, carreira_id):
    """Seed + todos que já jogaram em alguma temporada da carreira."""
    seed = {j.nome for j in carregar_jogadores().values()}
    rows = conn.execute(
        "SELECT DISTINCT j.nome FROM jogador j"
        " JOIN simulacao s ON s.id = j.simulacao_id"
        " WHERE s.carreira_id = ?",
        (carreira_id,),
    )
    return seed | {r["nome"] for r in rows}


def proxima_temporada(simulacao_id):
    """Cria a temporada seguinte, em andamento e parada antes da rodada 1.
    Devolve `{simulacao_id, carreira_id, temporada}`; None se a simulação
    não existe; `CarreiraInvalida` se ela não pode ser continuada."""

    conn = conectar()
    try:
        sim = simulacao_repo.buscar(conn, simulacao_id)
        if sim is None:
            return None
        if sim["estado"] != "concluida":
            raise CarreiraInvalida("A temporada ainda não terminou")
        if not sim["clube_usuario"]:
            raise CarreiraInvalida(
                "Só dá para continuar uma temporada com clube dirigido"
            )
        # só a última temporada da carreira continua: senão daria para
        # criar duas "temporadas 2" a partir da mesma temporada 1
        if sim["carreira_id"] is not None and simulacao_repo.sucessora(
            conn, simulacao_id
        ):
            raise CarreiraInvalida("Esta temporada já foi continuada")

        clube_usuario = sim["clube_usuario"]
        agora = datetime.now(timezone.utc).isoformat()

        clubes_finais = [
            dict(r) for r in clube_repo.listar_por_simulacao(conn, simulacao_id)
        ]
        jogadores_finais = [
            dict(r) for r in jogador_repo.listar_por_simulacao(conn, simulacao_id)
        ]

        with conn:
            carreira_id = sim["carreira_id"]
            if carreira_id is None:
                carreira_id = carreira_repo.criar(
                    conn, clube_usuario, sim["seed"], agora
                )
                simulacao_repo.vincular_carreira(conn, simulacao_id, carreira_id, 1)
                temporada_anterior = 1
            else:
                temporada_anterior = sim["temporada"]

            carreira = carreira_repo.buscar(conn, carreira_id)
            temporada = temporada_anterior + 1
            seed = seed_da_temporada(carreira["seed"], temporada)

            if seed is not None:
                random.seed(seed)
            else:
                random.seed()

            campeonato = carregar_campeonato()
            preparar_nova_temporada(campeonato, clubes_finais, jogadores_finais)
            envelhecer(campeonato, jogadores_finais, random)
            # aposentadoria antes dos contratos: quem vai parar não renova
            movimentos = aposentar(campeonato, random)
            movimentos += resolver_contratos(campeonato, clube_usuario)
            # a base repõe quem saiu; nomes não se repetem na carreira
            movimentos += subir_jovens(
                campeonato, _nomes_usados(conn, carreira_id), random
            )

            # o técnico mantém tática, formação e XI — menos quem saiu do clube
            alvo = next(c for c in campeonato.clubes if c.nome == clube_usuario)
            elenco = {j.nome for j in alvo.jogadores}
            xi = json.loads(sim["xi_preferido"]) if sim["xi_preferido"] else []
            xi = [n for n in xi if n in elenco] or None
            simulacao_service._configurar_clube(
                alvo, sim["tatica"] or "equilibrado", sim["formacao"], xi
            )

            cru = simulacao_service._serializar(
                campeonato, seed, clube_usuario,
                alvo.tatica, alvo.formacao, xi,
            )

            nova_id = simulacao_repo.criar(
                conn,
                seed=seed,
                campeao="",
                rodadas=len(campeonato.calendario),
                criada_em=agora,
                clube_usuario=clube_usuario,
                tatica=alvo.tatica,
                formacao=alvo.formacao,
                xi_preferido=json.dumps(xi, ensure_ascii=False) if xi else None,
                estado="em_andamento",
                rodada_atual=1,
                estado_json=json.dumps(snapshot_estado(campeonato)),
                carreira_id=carreira_id,
                temporada=temporada,
            )
            mapa = clube_repo.inserir(conn, nova_id, cru["clubes"])
            jogador_repo.inserir(conn, nova_id, mapa, cru["jogadores"])
            movimento_repo.inserir(conn, nova_id, movimentos)

        return {
            "simulacao_id": nova_id,
            "carreira_id": carreira_id,
            "temporada": temporada,
        }
    finally:
        conn.close()


def detalhe_carreira(carreira_id):
    """A carreira e suas temporadas (com o campeão de cada). None se não
    existe."""

    conn = conectar()
    try:
        carreira = carreira_repo.buscar(conn, carreira_id)
        if carreira is None:
            return None
        return {
            "id": carreira["id"],
            "clube_usuario": carreira["clube_usuario"],
            "seed": carreira["seed"],
            "criada_em": carreira["criada_em"],
            "temporadas": [
                {
                    "simulacao_id": t["id"],
                    "temporada": t["temporada"],
                    "seed": t["seed"],
                    "campeao": t["campeao"] or None,
                    "estado": t["estado"],
                    "rodada_atual": t["rodada_atual"],
                }
                for t in carreira_repo.listar_temporadas(conn, carreira_id)
            ],
        }
    finally:
        conn.close()
