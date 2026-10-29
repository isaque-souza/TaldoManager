"""Relatório pós-jogo (v2.2): o último jogo do técnico, lido do que já foi
gravado.

Só lê: a rodada (ou o jogo da copa) já foi jogada e gravada por
`temporada_service.avancar`, com prêmio, bilheteria, tabela e caixa de
entrada. Abrir o relatório de novo, ou depois de recarregar o save, devolve
o mesmo relatório e não mexe em nada. As regras (expectativa, momento
decisivo, destaques) ficam em `app.domain.pos_jogo`.
"""

import json
import random
from types import SimpleNamespace

from app.db.conexao import conectar
from app.domain import calendario, copa, diretoria, pos_jogo
from app.domain.temporada import restaurar_estado
from app.repositories import atuacao_repository as atuacao_repo
from app.repositories import clube_repository as clube_repo
from app.repositories import jogador_repository as jogador_repo
from app.repositories import lance_repository as lance_repo
from app.repositories import mensagem_repository as mensagem_repo
from app.repositories import partida_repository as partida_repo
from app.repositories import simulacao_repository as simulacao_repo
from app.services import copa_service, simulacao_service
from scripts.data_loader import carregar_campeonato_do_save


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

    eventos = [
        {"minuto": r["minuto"], "tipo": r["tipo"], "jogador": r["jogador_nome"],
         "clube": r["clube_nome"], "detalhe": r["detalhe"]}
        for r in lance_repo.listar_por_partida(conn, p["id"])
        if r["tipo"] != "chute_fora"
    ]
    atuacoes = [
        {"jogador": r["jogador_nome"], "jogador_id": r["jogador_id"],
         "clube": r["clube_nome"], "posicao": r["jogador_posicao"],
         "titular": bool(r["titular"]), "gols": r["gols"],
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
        "eventos": eventos,
        "estatisticas": estatisticas,
        "atuacoes": atuacoes,
        **_analise(conn, sim, eventos, atuacoes, p["gols_mandante"],
                   p["gols_visitante"], mandante, meu, rival, em_casa, res),
        "tabela": _impacto_na_tabela(conn, sim, clubes, p, pro, contra),
        "mensagens": _mensagens_do_dia(
            conn, sim["id"], p["rodada"],
            calendario.data_da_rodada(sim["temporada"], p["rodada"]),
        ),
    }


def _impacto_na_tabela(conn, sim, clubes, p, pro, contra):
    """A posição e os pontos do clube antes e depois desta rodada, e a
    meta da diretoria nos dois momentos. O depois é a tabela gravada."""
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
        for q in partida_repo.listar_por_simulacao(conn, sim["id"])
        if q["rodada"] < p["rodada"]
    ]
    posicao_antes = pos_jogo.tabela(ordem, anteriores)[meu]
    ganhos = 3 if pro > contra else 1 if pro == contra else 0

    meta = sim["meta_posicao"]
    return {
        "posicao_antes": posicao_antes,
        "posicao": linha["posicao_final"],
        "pontos_antes": linha["pontos"] - ganhos,
        "pontos": linha["pontos"],
        "pontos_ganhos": ganhos,
        "total_clubes": total,
        "meta": None if meta is None else {
            "posicao": meta,
            "descricao": diretoria.descricao_meta(meta),
            "situacao_antes": diretoria.situacao(posicao_antes, meta, total),
            "situacao": diretoria.situacao(linha["posicao_final"], meta, total),
        },
    }


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
        "eventos": eventos,
        "estatisticas": j.get("estatisticas"),
        "atuacoes": atuacoes,
        **_analise(conn, sim, eventos, atuacoes, j["gols_mandante"],
                   j["gols_visitante"], mandante, meu, rival, em_casa, res),
        # a copa não mexe na tabela da liga
        "tabela": None,
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


def _analise(conn, sim, eventos, atuacoes, gm, gv, mandante, meu, rival, em_casa, res):
    """Expectativa × resultado, momento decisivo e destaques."""
    forca = _forcas(conn, sim["id"], (meu, rival))
    exp = pos_jogo.expectativa(forca[meu], forca[rival], "casa" if em_casa else "fora")
    return {
        "expectativa": {
            **exp,
            "forca": forca[meu],
            "forca_adversario": forca[rival],
            "desempenho": pos_jogo.desempenho(res, exp["nivel"]),
        },
        "momento_decisivo": pos_jogo.momento_decisivo(eventos, gm, gv, mandante),
        "destaques": pos_jogo.destaques(atuacoes, meu),
    }


def _forcas(conn, simulacao_id, nomes):
    """A força do elenco (`diretoria.forca_do_elenco`) de cada clube, com
    os elencos gravados. É a de agora: o jogo só muda a força se alguém
    trocou de clube depois dele (a janela da CPU)."""
    elencos = {n: [] for n in nomes}
    for j in jogador_repo.listar_por_simulacao(conn, simulacao_id, com_livres=False):
        if j["clube"] in elencos:
            elencos[j["clube"]].append(SimpleNamespace(posicao=j["posicao"], overall=j["overall"]))
    return {
        n: diretoria.forca_do_elenco(SimpleNamespace(jogadores=js))
        for n, js in elencos.items()
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
