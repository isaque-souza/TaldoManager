"""Temporada simulada rodada a rodada.

Ao contrário de `simulacao_service`, que roda as 38 rodadas de uma vez e grava
só o resultado final, aqui a temporada nasce "em andamento": cada chamada de
`avancar` joga uma rodada, grava as partidas dela e re-grava as stats
acumuladas dos clubes/jogadores, até a 38ª rodada, quando o save vira uma
simulação concluída normal (com campeão).

O estado vivo entre rodadas (energia, corrente do RNG, ...) fica num blob JSON
em `simulacao.estado_json` — ver `app.domain.temporada`.
"""

import io
import json
import random
from contextlib import redirect_stdout
from datetime import datetime, timezone

from app.db.conexao import conectar
from app.domain.temporada import restaurar_estado, snapshot_estado
from app.repositories import atuacao_repository as atuacao_repo
from app.repositories import clube_repository as clube_repo
from app.repositories import jogador_repository as jogador_repo
from app.repositories import lance_repository as lance_repo
from app.repositories import partida_repository as partida_repo
from app.repositories import simulacao_repository as simulacao_repo
from app.services import simulacao_service
from scripts.data_loader import carregar_campeonato


class TemporadaConcluida(Exception):
    """Tentou avançar uma temporada que já terminou."""


class PartidaEmAndamento(Exception):
    """Mexer no elenco com a partida do técnico sendo transmitida (v1.2):
    a re-simulação dela depende do elenco de quando a bola rolou."""


# ---------------------------------------------------------------------------
# transmissão em curso (simulação interativa, v1.2 — ver transmissao_service)
# ---------------------------------------------------------------------------

def transmissao_ativa(sim):
    """Há uma partida do técnico sendo transmitida nesta rodada?"""
    if not sim["ao_vivo_json"]:
        return False
    return json.loads(sim["ao_vivo_json"])["rodada"] == sim["rodada_atual"]


def decisoes_ao_vivo(sim):
    """As decisões do técnico na transmissão em curso ([] se não há)."""
    if not transmissao_ativa(sim):
        return []
    return json.loads(sim["ao_vivo_json"])["decisoes"]


def exigir_sem_transmissao(sim):
    if transmissao_ativa(sim):
        raise PartidaEmAndamento(
            "A partida já começou: o elenco fica travado até o apito final"
        )


def _achar_clube(campeonato, nome):
    clube = next((c for c in campeonato.clubes if c.nome == nome), None)
    if clube is None:
        raise ValueError(f"Clube desconhecido: {nome!r}")
    return clube


def _confronto_do_clube(rodada, nome):
    """(adversário, mando) do clube `nome` numa rodada do calendário, ou
    (None, None) se ele folga."""
    for mandante, visitante in rodada:
        if mandante.nome == nome:
            return visitante.nome, "casa"
        if visitante.nome == nome:
            return mandante.nome, "fora"
    return None, None


# ---------------------------------------------------------------------------
# iniciar
# ---------------------------------------------------------------------------

def iniciar(seed=None, clube_usuario=None, tatica="equilibrado",
            formacao=None, xi_preferido=None):
    """Cria uma temporada em andamento, parada antes da rodada 1. Devolve o id."""

    if not clube_usuario:
        raise ValueError("Simular rodada a rodada exige um clube dirigido")

    if seed is not None:
        random.seed(seed)
    else:
        random.seed()

    campeonato = carregar_campeonato()
    alvo = _achar_clube(campeonato, clube_usuario)
    simulacao_service._configurar_clube(alvo, tatica, formacao, xi_preferido)

    xi_ef = list(dict.fromkeys(xi_preferido)) if xi_preferido else None
    cru = simulacao_service._serializar(
        campeonato, seed, clube_usuario, tatica, formacao, xi_ef
    )

    conn = conectar()
    try:
        with conn:
            sim_id = simulacao_repo.criar(
                conn,
                seed=seed,
                campeao="",
                rodadas=len(campeonato.calendario),
                criada_em=datetime.now(timezone.utc).isoformat(),
                clube_usuario=clube_usuario,
                tatica=tatica,
                formacao=formacao,
                xi_preferido=(
                    json.dumps(xi_ef, ensure_ascii=False) if xi_ef else None
                ),
                estado="em_andamento",
                rodada_atual=1,
                estado_json=json.dumps(snapshot_estado(campeonato)),
                **simulacao_service.meta_inicial(campeonato, clube_usuario),
            )
            mapa = clube_repo.inserir(conn, sim_id, cru["clubes"])
            jogador_repo.inserir(conn, sim_id, mapa, cru["jogadores"])
        return sim_id
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# preview da próxima rodada
# ---------------------------------------------------------------------------

def proxima_rodada(simulacao_id):
    """Confrontos da próxima rodada e a situação do elenco dirigido. None se a
    simulação não existe."""

    conn = conectar()
    try:
        sim = simulacao_repo.buscar(conn, simulacao_id)
        if sim is None:
            return None

        total = sim["rodadas"]
        if sim["estado"] != "em_andamento":
            return {
                "concluida": True,
                "rodada": None,
                "total_rodadas": total,
                "clube_usuario": sim["clube_usuario"],
                "adversario": None,
                "mando": None,
                "tatica": sim["tatica"],
                "formacao": sim["formacao"],
                "xi_preferido": None,
                "formacoes": [],
                "confrontos": [],
                "elenco": [],
                "transmissao_ativa": False,
            }

        estado_rng = random.getstate()
        try:
            campeonato = carregar_campeonato()
            restaurar_estado(campeonato, json.loads(sim["estado_json"]))
        finally:
            random.setstate(estado_rng)

        r = campeonato.rodada
        rodada = campeonato.calendario[r - 1]
        alvo = _achar_clube(campeonato, sim["clube_usuario"])
        adversario, mando = _confronto_do_clube(rodada, alvo.nome)

        return {
            "concluida": False,
            "rodada": r,
            "total_rodadas": total,
            "clube_usuario": alvo.nome,
            "adversario": adversario,
            "mando": mando,
            "tatica": alvo.tatica,
            "formacao": alvo.formacao,
            "xi_preferido": sorted(j.nome for j in alvo.xi_preferido) or None,
            "formacoes": list(alvo.FORMACOES),
            # a partida já começou (v1.2): a tela retoma a transmissão
            "transmissao_ativa": transmissao_ativa(sim),
            "confrontos": [
                {"mandante": m.nome, "visitante": v.nome} for m, v in rodada
            ],
            "elenco": [
                {
                    "nome": j.nome,
                    "posicao": j.posicao,
                    "overall": j.overall,
                    "energia": j.energia,
                    "condicao": j.condicao,
                    "suspenso": j.suspenso,
                    "jogos_suspensao": j.jogos_suspensao,
                    "amarelos_ciclo": j.amarelos_ciclo,
                    "lesionado": j.lesionado,
                    "rodadas_lesao": j.rodadas_lesao,
                }
                for j in alvo.jogadores
            ],
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# pré-jogo (v1.1): as duas escalações como vão entrar em campo
# ---------------------------------------------------------------------------

# overall a partir do qual o jogador ganha a estrela de craque no pré-jogo
CRAQUE = 88


def _jogador_pre_jogo(j, linha=None):
    dados = {
        "nome": j.nome,
        "numero": j.numero,
        "posicao": j.posicao,
        "overall": j.overall,
        "energia": round(j.energia),
        "condicao": j.condicao,
        "pendurado": j.amarelos_ciclo == 4,
        "craque": j.overall >= CRAQUE,
    }
    if linha is not None:
        dados["linha"] = linha
    return dados


def _escalacao(clube):
    """XI e banco exatamente como o motor escala no apito
    (Clube.escalar_time é determinístico). Cada titular vem com a `linha`
    do campo onde a formação o coloca: 0 goleiro, 1 defesa, 2 meio,
    3 ataque — um improvisado fica na linha da vaga, não na posição dele."""
    clube.escalar_time()
    n_def, n_mei, n_ata = clube.FORMACOES.get(clube.formacao, (4, 3, 3))
    linhas = [0] + [1] * n_def + [2] * n_mei + [3] * n_ata
    return {
        "clube": clube.nome,
        "formacao": clube.formacao,
        "tatica": clube.tatica,
        "titulares": [
            _jogador_pre_jogo(j, linha)
            for j, linha in zip(clube.titulares, linhas)
        ],
        "banco": [_jogador_pre_jogo(j) for j in clube.reservas],
    }


def pre_jogo(simulacao_id):
    """As duas escalações da partida do técnico na próxima rodada, com a
    decisão salva (tática, formação, XI). Só leitura: nada é gravado e o
    gerador aleatório volta ao estado de antes. None se a simulação não
    existe; `TemporadaConcluida` se já terminou; `adversario` None na folga."""

    conn = conectar()
    try:
        sim = simulacao_repo.buscar(conn, simulacao_id)
    finally:
        conn.close()
    if sim is None:
        return None
    if sim["estado"] != "em_andamento":
        raise TemporadaConcluida("Esta temporada já foi concluída")

    estado_rng = random.getstate()
    try:
        campeonato = carregar_campeonato()
        restaurar_estado(campeonato, json.loads(sim["estado_json"]))
    finally:
        random.setstate(estado_rng)

    r = campeonato.rodada
    alvo = _achar_clube(campeonato, sim["clube_usuario"])
    adversario, mando = _confronto_do_clube(campeonato.calendario[r - 1], alvo.nome)

    base = {
        "rodada": r,
        "total_rodadas": len(campeonato.calendario),
        "clube_usuario": alvo.nome,
        "adversario": adversario,
        "mando": mando,
    }
    if adversario is None:
        return {**base, "mandante": None, "visitante": None}

    rival = _achar_clube(campeonato, adversario)
    mandante, visitante = (alvo, rival) if mando == "casa" else (rival, alvo)
    return {**base, "mandante": _escalacao(mandante), "visitante": _escalacao(visitante)}


# ---------------------------------------------------------------------------
# avançar uma rodada
# ---------------------------------------------------------------------------

def avancar(simulacao_id, tatica=None, formacao=None, xi_preferido=None):
    """Joga a próxima rodada. Devolve `{rodada_jogada, concluida, ...visão}`.
    None se a simulação não existe; `TemporadaConcluida` se já terminou."""

    conn = conectar()
    try:
        sim = simulacao_repo.buscar(conn, simulacao_id)
        if sim is None:
            return None
        if sim["estado"] != "em_andamento":
            raise TemporadaConcluida(
                "Esta temporada já foi concluída"
            )

        seed = sim["seed"]
        clube_usuario = sim["clube_usuario"]

        # partida transmitida (v1.2): a escalação é a do apito inicial (já
        # gravada) e as mudanças do técnico durante o jogo entram aqui
        ao_vivo = transmissao_ativa(sim)
        decisoes = decisoes_ao_vivo(sim)
        if ao_vivo:
            tatica = formacao = xi_preferido = None

        campeonato = carregar_campeonato()
        restaurar_estado(campeonato, json.loads(sim["estado_json"]))

        alvo = _achar_clube(campeonato, clube_usuario)
        nova_tatica = tatica or alvo.tatica
        nova_formacao = formacao or alvo.formacao
        # xi None = mantém o salvo; [] = todos no automático
        simulacao_service._configurar_clube(
            alvo, nova_tatica, nova_formacao, xi_preferido
        )
        if xi_preferido is not None:
            xi_ef = list(dict.fromkeys(xi_preferido)) or None
        else:
            xi_ef = sorted(j.nome for j in alvo.xi_preferido) or None

        rodada_jogada = campeonato.rodada
        with redirect_stdout(io.StringIO()):
            campeonato.jogar_rodada(clube_usuario, decisoes)

        novas = [
            p for p in campeonato.partidas_jogadas
            if p["rodada"] == rodada_jogada
        ]

        cru = simulacao_service._serializar(
            campeonato, seed, clube_usuario,
            nova_tatica, nova_formacao, xi_ef,
        )

        concluida = campeonato.rodada > len(campeonato.calendario)
        xi_json = (
            json.dumps(xi_ef, ensure_ascii=False) if xi_ef else None
        )

        with conn:
            mapa = clube_repo.atualizar(conn, simulacao_id, cru["clubes"])
            mapa_jog = jogador_repo.atualizar(
                conn, simulacao_id, mapa, cru["jogadores"]
            )
            partida_ids = partida_repo.inserir(conn, simulacao_id, mapa, novas)
            lance_repo.inserir(conn, partida_ids, mapa, mapa_jog, novas)
            atuacao_repo.inserir(conn, partida_ids, mapa, mapa_jog, novas)
            if ao_vivo:
                simulacao_repo.definir_ao_vivo(conn, simulacao_id, None)

            if concluida:
                simulacao_repo.atualizar_estado(
                    conn, simulacao_id,
                    estado="concluida",
                    rodada_atual=None,
                    estado_json=None,
                    campeao=campeonato.classificacao()[0].nome,
                    tatica=nova_tatica,
                    formacao=nova_formacao,
                    xi_preferido=xi_json,
                )
            else:
                simulacao_repo.atualizar_estado(
                    conn, simulacao_id,
                    estado="em_andamento",
                    rodada_atual=campeonato.rodada,
                    estado_json=json.dumps(snapshot_estado(campeonato)),
                    campeao="",
                    tatica=nova_tatica,
                    formacao=nova_formacao,
                    xi_preferido=xi_json,
                )

        visao = simulacao_service._montar_visao(
            simulacao_service._cru_do_banco(conn, simulacao_id)
        )
        return {
            "rodada_jogada": rodada_jogada,
            "concluida": concluida,
            "resultados": [
                {
                    "partida_id": pid,
                    "mandante": p["mandante"],
                    "visitante": p["visitante"],
                    "gols_mandante": p["gols_mandante"],
                    "gols_visitante": p["gols_visitante"],
                }
                for pid, p in zip(partida_ids, novas)
            ],
            **visao,
        }
    finally:
        conn.close()
