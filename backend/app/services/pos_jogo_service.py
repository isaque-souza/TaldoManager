"""Relatório pós-jogo (v2.2): o último jogo do técnico, lido do que já foi
gravado.

Só lê: a rodada (ou o jogo da copa) já foi jogada e gravada por
`temporada_service.avancar`, com prêmio, bilheteria, tabela e caixa de
entrada. Abrir o relatório de novo, ou depois de recarregar o save, devolve
o mesmo relatório e não mexe em nada. As regras (resultado, destaques,
tabela) ficam em `app.domain.pos_jogo`.
"""

import json
import random

from app.db.conexao import conectar
from app.domain import calendario, copa, pos_jogo
from app.domain.temporada import restaurar_estado
from app.repositories import atuacao_repository as atuacao_repo
from app.repositories import clube_repository as clube_repo
from app.repositories import lance_repository as lance_repo
from app.repositories import mensagem_repository as mensagem_repo
from app.repositories import partida_repository as partida_repo
from app.repositories import simulacao_repository as simulacao_repo
from app.services import copa_service, simulacao_service
from scripts.data_loader import carregar_campeonato_do_save, rivais_do_seed


class SemJogo(Exception):
    """O técnico ainda não jogou nesta temporada."""


def ver(simulacao_id):
    """O relatório do último jogo do técnico. None se a simulação não
    existe; `SemJogo` se ele ainda não jogou (ou o save não tem clube)."""
    conn = conectar()
    try:
        sim = simulacao_repo.buscar(conn, simulacao_id)
        if sim is None:
            return None
        meu = sim["clube_usuario"]
        if not meu:
            raise SemJogo("Este save não tem clube dirigido")
        clubes = clube_repo.listar_por_simulacao(conn, simulacao_id)

        da_liga = _ultimo_da_liga(conn, simulacao_id, meu)
        da_copa = _ultimo_da_copa(sim, meu)
        # a fase da copa é jogada na quarta depois da rodada DATAS[fase]
        if da_copa and (da_liga is None or copa.DATAS[da_copa[0]] >= da_liga["rodada"]):
            relatorio = _da_copa(conn, sim, clubes, *da_copa)
        elif da_liga is not None:
            relatorio = _da_liga(conn, sim, clubes, da_liga)
        else:
            raise SemJogo("Nenhum jogo do técnico nesta temporada ainda")

        relatorio["proximo"] = _proximo(sim)
        relatorio["temporada_concluida"] = sim["estado"] == "concluida"
        relatorio["cargo"] = (
            simulacao_service.cargo_da_temporada(conn, sim)
            if sim["estado"] == "concluida" else None
        )
        return relatorio
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# qual foi o último jogo
# ---------------------------------------------------------------------------

def _ultimo_da_liga(conn, simulacao_id, meu):
    """A linha da partida mais recente do clube na liga, ou None."""
    jogos = [
        p for p in partida_repo.listar_por_simulacao(conn, simulacao_id)
        if meu in (p["mandante_nome"], p["visitante_nome"])
    ]
    return jogos[-1] if jogos else None


def _ultimo_da_copa(sim, meu):
    """(fase, jogo) do jogo mais recente do clube na copa já decidido, ou
    None."""
    dados = copa_service.estado_da_copa(sim)
    if not dados:
        return None
    ultimo = None
    for fase in copa.FASES:
        for j in dados["fases"].get(fase) or []:
            if meu in (j["mandante"], j["visitante"]) and j["vencedor"]:
                ultimo = (fase, j)
    return ultimo


# ---------------------------------------------------------------------------
# liga
# ---------------------------------------------------------------------------

def _da_liga(conn, sim, clubes, p):
    meu = sim["clube_usuario"]
    mandante, visitante = p["mandante_nome"], p["visitante_nome"]
    em_casa = mandante == meu
    rival = visitante if em_casa else mandante
    pro, contra = (
        (p["gols_mandante"], p["gols_visitante"]) if em_casa
        else (p["gols_visitante"], p["gols_mandante"])
    )
    res = pos_jogo.resultado(pro, contra)
    partidas = partida_repo.listar_por_simulacao(conn, sim["id"])

    eventos = [
        {"minuto": r["minuto"], "tipo": r["tipo"], "jogador": r["jogador_nome"],
         "clube": r["clube_nome"], "detalhe": r["detalhe"]}
        for r in lance_repo.listar_por_partida(conn, p["id"])
        if r["tipo"] != "chute_fora"
    ]
    atuacoes = [
        {"jogador": r["jogador_nome"], "jogador_id": r["jogador_id"],
         "clube": r["clube_nome"], "posicao": r["jogador_posicao"],
         "titular": bool(r["titular"]), "entrou_min": r["entrou_min"],
         "saiu_min": r["saiu_min"], "gols": r["gols"],
         "assistencias": r["assistencias"], "nota": r["nota"]}
        for r in atuacao_repo.listar_por_partida(conn, p["id"])
    ]
    estatisticas = {
        k: p[k] for k in (
            "posse_mandante", "finalizacoes_mandante", "finalizacoes_visitante",
            "finalizacoes_gol_mandante", "finalizacoes_gol_visitante",
            "escanteios_mandante", "escanteios_visitante", "acrescimos",
        )
    }

    return {
        "competicao": "liga",
        "liga": _liga_de(clubes, meu),
        "rodada": p["rodada"],
        "total_rodadas": sim["rodadas"],
        "copa": None,
        "data": calendario.data_da_rodada(sim["temporada"], p["rodada"]).isoformat(),
        "partida_id": p["id"],
        **_placar(meu, rival, em_casa, mandante, visitante, p["gols_mandante"],
                  p["gols_visitante"], res, p["publico"]),
        **_atmosfera(clubes, mandante, visitante, p["publico"]),
        "eventos": eventos,
        "estatisticas": estatisticas,
        "atuacoes": atuacoes,
        "destaques": pos_jogo.destaques(atuacoes, meu),
        "tabela": _impacto_na_tabela(sim, clubes, p, pro, contra, partidas),
        "outros_resultados": _outros_da_rodada(clubes, p, partidas),
        "mensagens": _mensagens_do_dia(
            conn, sim["id"], p["rodada"],
            calendario.data_da_rodada(sim["temporada"], p["rodada"]),
        ),
    }


def _impacto_na_tabela(sim, clubes, p, pro, contra, partidas):
    """A posição e os pontos do clube antes e depois desta rodada, mais a
    vizinhança dele na tabela (`vizinhos`: até VIZINHOS clubes em volta,
    com a posição de antes de cada um). O depois é a tabela gravada."""
    meu = sim["clube_usuario"]
    liga = _liga_de(clubes, meu)
    da_liga = [c for c in clubes if c["liga"] == liga]
    linha = next(c for c in da_liga if c["nome"] == meu)
    total = len(da_liga)

    # antes: a tabela refeita com as partidas das rodadas anteriores, na
    # ordem dos clubes do motor (o id) para o desempate final
    ordem = [c["nome"] for c in sorted(da_liga, key=lambda c: c["id"])]
    anteriores = [
        {"mandante": q["mandante_nome"], "visitante": q["visitante_nome"],
         "gols_mandante": q["gols_mandante"], "gols_visitante": q["gols_visitante"]}
        for q in partidas
        if q["rodada"] < p["rodada"]
    ]
    antes = pos_jogo.tabela(ordem, anteriores)
    ganhos = 3 if pro > contra else 1 if pro == contra else 0

    return {
        "posicao_antes": antes[meu],
        "posicao": linha["posicao_final"],
        "pontos_antes": linha["pontos"] - ganhos,
        "pontos": linha["pontos"],
        "pontos_ganhos": ganhos,
        "total_clubes": total,
        "vizinhos": _vizinhos(da_liga, linha["posicao_final"], antes),
    }


VIZINHOS = 5


def _vizinhos(da_liga, posicao, antes):
    """Os VIZINHOS clubes em volta de `posicao` na tabela atual (o clube no
    meio, quando dá), com a posição de antes da rodada."""
    na_ordem = sorted(da_liga, key=lambda c: c["posicao_final"])
    inicio = max(0, min(posicao - 1 - VIZINHOS // 2, len(na_ordem) - VIZINHOS))
    return [
        {"clube": c["nome"], "posicao": c["posicao_final"],
         "posicao_antes": antes.get(c["nome"], c["posicao_final"]),
         "pontos": c["pontos"], "jogos": c["jogos"],
         "saldo": c["gols_marcados"] - c["gols_sofridos"]}
        for c in na_ordem[inicio:inicio + VIZINHOS]
    ]


def _outros_da_rodada(clubes, p, partidas):
    """Os outros jogos da liga do técnico na mesma rodada."""
    liga = {c["nome"]: c["liga"] for c in clubes}
    minha = liga.get(p["mandante_nome"])
    return [
        {"partida_id": q["id"], "mandante": q["mandante_nome"],
         "visitante": q["visitante_nome"], "gols_mandante": q["gols_mandante"],
         "gols_visitante": q["gols_visitante"], "penaltis": None}
        for q in partidas
        if q["rodada"] == p["rodada"] and q["id"] != p["id"]
        and liga.get(q["mandante_nome"]) == minha
    ]


# ---------------------------------------------------------------------------
# copa
# ---------------------------------------------------------------------------

def _da_copa(conn, sim, clubes, fase, j):
    meu = sim["clube_usuario"]
    mandante, visitante = j["mandante"], j["visitante"]
    em_casa = mandante == meu
    rival = visitante if em_casa else mandante
    pro, contra = (
        (j["gols_mandante"], j["gols_visitante"]) if em_casa
        else (j["gols_visitante"], j["gols_mandante"])
    )
    res = pos_jogo.resultado(pro, contra)
    rodada = copa.DATAS[fase]

    # jogos de saves anteriores à v2.2 só guardam os gols
    eventos = j.get("eventos") or [{**g, "detalhe": None} for g in j["gols"]]
    atuacoes = j.get("atuacoes") or []
    venceu = j["vencedor"] == meu
    proxima_fase = (
        copa.FASES[copa.FASES.index(fase) + 1]
        if venceu and fase != copa.FASES[-1] else None
    )

    return {
        "competicao": "copa",
        "liga": _liga_de(clubes, meu),
        "rodada": rodada,
        "total_rodadas": sim["rodadas"],
        "copa": {
            "fase": fase,
            "nome": copa_service.NOMES[fase],
            "penaltis": _penaltis_do_ponto_de_vista(j, em_casa),
            "classificado": venceu,
            "campeao": venceu and fase == copa.FASES[-1],
            "proxima_fase": proxima_fase and {
                "fase": proxima_fase, "nome": copa_service.NOMES[proxima_fase],
            },
            "premio": copa.PREMIOS[fase] if venceu else 0,
        },
        "data": calendario.data_da_copa(sim["temporada"], rodada).isoformat(),
        "partida_id": None,
        **_placar(meu, rival, em_casa, mandante, visitante, j["gols_mandante"],
                  j["gols_visitante"], res, j["publico"]),
        **_atmosfera(clubes, mandante, visitante, j["publico"]),
        "eventos": eventos,
        "estatisticas": j.get("estatisticas"),
        "atuacoes": atuacoes,
        "destaques": pos_jogo.destaques(atuacoes, meu),
        # a copa não mexe na tabela da liga
        "tabela": None,
        "outros_resultados": [
            {"partida_id": None, "mandante": o["mandante"], "visitante": o["visitante"],
             "gols_mandante": o["gols_mandante"], "gols_visitante": o["gols_visitante"],
             "penaltis": o["penaltis"]}
            for o in copa_service.estado_da_copa(sim)["fases"].get(fase) or []
            if o["vencedor"] and meu not in (o["mandante"], o["visitante"])
        ],
        "mensagens": _mensagens_do_dia(
            conn, sim["id"], rodada, calendario.data_da_copa(sim["temporada"], rodada),
        ),
    }


def _penaltis_do_ponto_de_vista(j, em_casa):
    if not j["penaltis"]:
        return None
    pm, pv = j["penaltis"]
    return {"pro": pm if em_casa else pv, "contra": pv if em_casa else pm}


# ---------------------------------------------------------------------------
# partes comuns
# ---------------------------------------------------------------------------

def _liga_de(clubes, nome):
    return next((c["liga"] for c in clubes if c["nome"] == nome), "taldo")


def _placar(meu, rival, em_casa, mandante, visitante, gm, gv, res, publico):
    return {
        "clube": meu,
        "adversario": rival,
        "mando": "casa" if em_casa else "fora",
        "mandante": mandante,
        "visitante": visitante,
        "gols_mandante": gm,
        "gols_visitante": gv,
        "resultado": res,
        "publico": publico,
    }


def _atmosfera(clubes, mandante, visitante, publico):
    """Para o desenho do estádio (v2.4): a ocupação do jogo (None sem
    público ou sem estádio registrado) e se foi clássico."""
    casa = next((c for c in clubes if c["nome"] == mandante), None)
    capacidade = casa["capacidade"] if casa else 0
    rivais = rivais_do_seed()
    return {
        "ocupacao": (round(min(1, publico / capacidade), 3)
                     if publico and capacidade else None),
        "classico": (visitante in rivais.get(mandante, ())
                     or mandante in rivais.get(visitante, ())),
    }


def _mensagens_do_dia(conn, simulacao_id, rodada, dia):
    """O que a caixa de entrada recebeu com o jogo: as mensagens da rodada
    com a data dele (a da copa tem o mesmo número de rodada, na quarta)."""
    dia = dia.isoformat()
    return [
        {"id": m["id"], "setor": m["setor"], "assunto": m["assunto"], "corpo": m["corpo"]}
        for m in reversed(mensagem_repo.listar(conn, simulacao_id))
        if m["rodada"] == rodada and m["data"] == dia
    ]


def _proximo(sim):
    """O próximo compromisso: {adversario, mando, rodada, copa, data}, com
    adversario None na folga; None com a temporada encerrada."""
    if sim["estado"] != "em_andamento":
        return None
    # só leitura: o RNG global não pode andar (o motor depende dele)
    estado_rng = random.getstate()
    try:
        campeonato = carregar_campeonato_do_save(sim)
        restaurar_estado(campeonato, json.loads(sim["estado_json"]))
    finally:
        random.setstate(estado_rng)
    from app.services import temporada_service   # aqui: evita import circular
    adversario, mando, na_copa = temporada_service.proximo_confronto(
        sim, campeonato, sim["clube_usuario"]
    )
    return {
        "adversario": adversario,
        "mando": mando,
        "rodada": campeonato.rodada,
        "copa": na_copa,
        "data": calendario.data_do_jogo(
            sim["temporada"], campeonato.rodada, na_copa=bool(na_copa)
        ).isoformat(),
    }
