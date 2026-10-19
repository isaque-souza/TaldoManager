"""Modo carreira (v0.8): continuar um save na temporada seguinte.

A carreira nasce sob demanda: a primeira vez que uma temporada concluída é
continuada, ela vira a temporada 1 de uma carreira nova. Assim qualquer save
antigo com clube dirigido pode virar carreira, sem migrar dados.
"""

import json
import random
from datetime import datetime, timezone

from app.db.conexao import conectar
from app.domain import caixa, copa, estadio, fama, historico, livres
from app.domain.base import subir_jovens
from app.domain.carreira import (
    aposentar,
    envelhecer,
    preparar_nova_temporada,
    resolver_contratos,
    seed_da_temporada,
)
from app.domain.temporada import restaurar_livres, snapshot_estado
from app.repositories import carreira_repository as carreira_repo
from app.repositories import clube_repository as clube_repo
from app.repositories import jogador_repository as jogador_repo
from app.repositories import mensagem_repository as mensagem_repo
from app.repositories import movimento_repository as movimento_repo
from app.repositories import partida_repository as partida_repo
from app.repositories import simulacao_repository as simulacao_repo
from app.services import copa_service, plano_service, simulacao_service
from scripts.data_loader import (
    LIGA_PADRAO, TODAS_AS_LIGAS, carregar_campeonato_do_save, carregar_jogadores,
    carregar_livres, ligas_do_save,
)


class CarreiraInvalida(Exception):
    """A temporada não pode ser continuada (em andamento, sem clube dirigido
    ou já continuada)."""


def _nomes_usados(conn, carreira_id):
    """Seed (com os livres, v1.6) + todos que já jogaram em alguma
    temporada da carreira."""
    seed = set()
    for liga in TODAS_AS_LIGAS:
        seed |= {j.nome for j in carregar_jogadores(liga).values()}
        seed |= {j.nome for j in carregar_livres(liga)}
    rows = conn.execute(
        "SELECT DISTINCT j.nome FROM jogador j"
        " JOIN simulacao s ON s.id = j.simulacao_id"
        " WHERE s.carreira_id = ?",
        (carreira_id,),
    )
    return seed | {r["nome"] for r in rows}


def _lotados(conn, simulacao_id, clubes_finais):
    """{clube: jogos em casa com o estádio cheio} na temporada. Pela
    capacidade final: se uma obra acabou no meio, os jogos de antes dela não
    contam como lotados (o estádio já cresceu)."""
    capacidade = {c["nome"]: c.get("capacidade") or 0 for c in clubes_finais}
    lotados = {}
    for p in partida_repo.listar_por_simulacao(conn, simulacao_id):
        nome = p["mandante_nome"]
        if p["publico"] and capacidade.get(nome) and p["publico"] >= capacidade[nome]:
            lotados[nome] = lotados.get(nome, 0) + 1
    return lotados


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
        cargo = simulacao_service.cargo_da_temporada(conn, sim)
        if cargo and cargo["estado"] == "demitido":
            raise CarreiraInvalida(f"Você foi demitido: {cargo['motivo']}")

        clube_usuario = sim["clube_usuario"]
        agora = datetime.now(timezone.utc).isoformat()

        clubes_finais = [
            dict(r) for r in clube_repo.listar_por_simulacao(conn, simulacao_id)
        ]
        # sem os dispensados (v1.7): eles seguem nos livres
        jogadores_finais = [
            dict(r) for r in jogador_repo.listar_por_simulacao(
                conn, simulacao_id, com_livres=False
            )
        ]
        # livres no fim da temporada (v1.6); antes deles, None = os da seed
        livres_finais = (
            restaurar_livres(json.loads(sim["livres_json"]))
            if sim["livres_json"] else None
        )

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

            # as ligas seguem as da temporada anterior (v1.6)
            campeonato = carregar_campeonato_do_save(sim)
            preparar_nova_temporada(
                campeonato, clubes_finais, jogadores_finais, livres_finais
            )
            envelhecer(campeonato, jogadores_finais, random)
            # os ídolos de antes da virada: quem se aposentar ganha homenagem
            idolos = {
                j.nome for c in campeonato.clubes if c.nome == clube_usuario
                for j in fama.idolos(c)
            }
            # aposentadoria antes dos contratos: quem vai parar não renova
            movimentos = aposentar(campeonato, random)
            movimentos += resolver_contratos(campeonato, clube_usuario)
            # a CPU olha os livres antes da base (v1.6)
            movimentos += livres.cpu_contrata(campeonato, clube_usuario, random)
            # a base repõe quem saiu; nomes não se repetem na carreira
            usados = _nomes_usados(conn, carreira_id) | {
                j.nome for j in campeonato.livres
            }
            movimentos += subir_jovens(campeonato, usados, random)
            livres.completar(campeonato, usados, random)
            # a CPU amplia o estádio que lotou (v1.5); nada aqui sorteia
            obras = estadio.cpu_amplia(
                campeonato, _lotados(conn, simulacao_id, clubes_finais), clube_usuario,
            )

            # a copa (v1.6): os 8 melhores de cada liga na temporada que acabou
            campeonato.iniciar_copa(copa.classificados_pela_tabela(clubes_finais))

            # o técnico mantém tática, formação e XI — menos quem saiu do
            # clube. Com planos de jogo (v1.2), a temporada começa no padrão.
            alvo = next(c for c in campeonato.clubes if c.nome == clube_usuario)
            elenco = {j.nome for j in alvo.jogadores}
            padrao = plano_service.padrao(conn, simulacao_id)
            if padrao:
                tatica, formacao, xi = padrao["tatica"], padrao["formacao"], padrao["xi"]
            else:
                tatica = sim["tatica"] or "equilibrado"
                formacao = sim["formacao"]
                xi = json.loads(sim["xi_preferido"]) if sim["xi_preferido"] else []
            xi = [n for n in xi if n in elenco] or None
            simulacao_service._configurar_clube(alvo, tatica, formacao, xi)

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
                ligas=(ligas_do_save(sim) if ligas_do_save(sim) != LIGA_PADRAO
                       else None),
                # a meta nasce do elenco depois da virada (base, saídas...)
                **simulacao_service.meta_inicial(campeonato, clube_usuario),
            )
            mapa = clube_repo.inserir(conn, nova_id, cru["clubes"])
            jogador_repo.inserir(conn, nova_id, mapa, cru["jogadores"])
            movimento_repo.inserir(conn, nova_id, movimentos)
            # caixa de entrada (v1.3): a meta nova e o que mudou no elenco
            meta = simulacao_service.meta_inicial(campeonato, clube_usuario)
            mensagem_repo.inserir(conn, nova_id, None, [
                caixa.meta_da_temporada(
                    clube_usuario, meta["meta_posicao"], meta["ranking_forca"],
                ),
                *caixa.virada(clube_usuario, movimentos, [
                    (j.nome, j.funcao) for j in alvo.jogadores if j.contrato_anos <= 1
                ], idolos),
                caixa.obras_na_liga([
                    (c.nome, estadio.OBRAS[t]["lugares"]) for c, t in obras
                    if c.liga == alvo.liga
                ]),
                copa_service.mensagem_de_inicio(campeonato, clube_usuario),
            ])
            # os planos de jogo seguem para a temporada nova (v1.2)
            plano_service.copiar(conn, simulacao_id, nova_id, alvo)

        return {
            "simulacao_id": nova_id,
            "carreira_id": carreira_id,
            "temporada": temporada,
        }
    finally:
        conn.close()


def detalhe_carreira(carreira_id):
    """A carreira: as temporadas (campeão, vice, artilheiro, MVP e a posição
    do técnico), os títulos por clube, os líderes históricos e o Hall da
    Fama. Tudo calculado das tabelas de cada temporada. None se não existe."""

    conn = conectar()
    try:
        carreira = carreira_repo.buscar(conn, carreira_id)
        if carreira is None:
            return None
        clube_usuario = carreira["clube_usuario"]

        temporadas, concluidas, aposentados = [], [], []
        for t in carreira_repo.listar_temporadas(conn, carreira_id):
            linha = {
                "simulacao_id": t["id"],
                "temporada": t["temporada"],
                "seed": t["seed"],
                "campeao": None,
                "vice": None,
                "artilheiro": None,
                "mvp": None,
                "posicao_usuario": None,
                "campeao_copa": None,
                "copa_usuario": None,
                "estado": t["estado"],
                "rodada_atual": t["rodada_atual"],
            }
            # quem se aposentou na virada para esta temporada jogou a anterior
            aposentados += [
                {**dict(m), "ultima_temporada": t["temporada"] - 1}
                for m in movimento_repo.listar_por_simulacao(conn, t["id"])
                if m["tipo"] == "aposentou"
            ]
            if t["estado"] == "concluida":
                jogadores = [
                    dict(r) for r in jogador_repo.listar_por_simulacao(conn, t["id"])
                ]
                clubes = [
                    dict(r) for r in clube_repo.listar_por_simulacao(conn, t["id"])
                ]
                # com duas ligas (v1.6), campeão, vice, artilheiro e MVP são
                # da liga do técnico; o título de jogador vale nas duas
                liga = next(
                    (c["liga"] for c in clubes if c["nome"] == clube_usuario), None
                )
                da_liga = [c for c in clubes if c["liga"] == liga] or clubes
                nomes = {c["nome"] for c in da_liga}
                resumo = historico.resumo_temporada(
                    da_liga, [j for j in jogadores if j["clube"] in nomes], clube_usuario,
                )
                resumo["campeoes"] = [c["nome"] for c in clubes if c["posicao_final"] == 1]
                dados_copa = json.loads(t["copa_json"]) if t["copa_json"] else None
                resumo["campeao_copa"] = copa.campeao_de(dados_copa)
                linha.update({k: v for k, v in resumo.items() if k != "campeoes"})
                linha["copa_usuario"] = copa.ate_onde(dados_copa, clube_usuario)
                concluidas.append({
                    "temporada": t["temporada"],
                    "jogadores": jogadores,
                    "resumo": resumo,
                })
            temporadas.append(linha)

        totais = historico.totais_por_jogador(concluidas)
        return {
            "id": carreira["id"],
            "clube_usuario": clube_usuario,
            "seed": carreira["seed"],
            "criada_em": carreira["criada_em"],
            "temporadas": temporadas,
            "titulos": historico.titulos_por_clube(
                [(t["temporada"], t["resumo"]) for t in concluidas]
            ),
            "titulos_copa": historico.titulos_por_clube(
                [(t["temporada"], t["resumo"]) for t in concluidas], "campeao_copa",
            ),
            "lideres": historico.lideres(totais),
            "hall_da_fama": historico.hall_da_fama(totais, aposentados),
        }
    finally:
        conn.close()
