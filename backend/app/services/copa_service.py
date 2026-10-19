"""Copa entre as ligas (v1.6): a visão para a tela. As regras ficam em
`app.domain.copa`; aqui é só ler o estado dela (no snapshot, durante a
temporada; em `simulacao.copa_json`, depois) e contar onde o clube do
técnico está. Nada é restaurado nem regravado.
"""

import json

from app.db.conexao import conectar
from app.domain import caixa, copa
from app.repositories import clube_repository as clube_repo
from app.repositories import simulacao_repository as simulacao_repo

NOMES = {
    "oitavas": "Oitavas de final",
    "quartas": "Quartas de final",
    "semi": "Semifinal",
    "final": "Final",
}


def estado_da_copa(sim):
    """O dict da copa (`Copa.para_dict`) de uma simulação, ou None."""
    if sim["estado_json"]:
        return json.loads(sim["estado_json"]).get("copa")
    if sim["copa_json"]:
        return json.loads(sim["copa_json"])
    return None


def ver(simulacao_id):
    """{"copa": visão} — com None quando o save não tem copa; None se a
    simulação não existe."""
    conn = conectar()
    try:
        sim = simulacao_repo.buscar(conn, simulacao_id)
        if sim is None:
            return None
        dados = estado_da_copa(sim)
        if dados is None:
            return {"copa": None}
        liga = {
            r["nome"]: r["liga"]
            for r in clube_repo.listar_por_simulacao(conn, simulacao_id)
        }
        return {"copa": visao(dados, sim["clube_usuario"], liga)}
    finally:
        conn.close()


def visao(dados, clube_usuario, liga_de):
    """A copa como a tela mostra: as quatro fases (as que ainda não têm
    confronto vêm com `jogos` vazio), o campeão, a próxima data e a
    situação do clube do técnico."""
    fases = []
    for fase in copa.FASES:
        jogos = [_jogo(j, liga_de) for j in dados["fases"].get(fase, [])]
        fases.append({
            "fase": fase,
            "nome": NOMES[fase],
            "depois_da_rodada": copa.DATAS[fase],
            "premio": copa.PREMIOS[fase],
            "jogos": jogos,
            "jogada": bool(jogos) and all(j["vencedor"] for j in jogos),
        })
    proxima = next((f for f in fases if not f["jogada"]), None)
    final = dados["fases"].get("final")
    return {
        "fases": fases,
        "campeao": final[0]["vencedor"] if final and final[0]["vencedor"] else None,
        "proxima": (
            {"fase": proxima["fase"], "nome": proxima["nome"],
             "depois_da_rodada": proxima["depois_da_rodada"]}
            if proxima else None
        ),
        "seu_clube": situacao(dados, clube_usuario),
    }


def _jogo(j, liga_de):
    return {
        **j,
        "liga_mandante": liga_de.get(j["mandante"]),
        "liga_visitante": liga_de.get(j["visitante"]),
    }


def situacao(dados, clube):
    """Onde o clube do técnico está: `fora` (não se classificou),
    `vivo` (com o próximo jogo), `eliminado` (e em que fase) ou `campeao`."""
    classificado = any(clube in nomes for nomes in dados["classificados"].values())
    if not classificado:
        return {"estado": "fora", "fase": None, "jogo": None}

    for fase in copa.FASES:
        jogo = next(
            (j for j in dados["fases"].get(fase, [])
             if clube in (j["mandante"], j["visitante"])),
            None,
        )
        if jogo is None:
            # a fase ainda não foi montada: ele passou da anterior
            return {"estado": "vivo", "fase": fase, "jogo": None}
        if jogo["vencedor"] is None:
            return {"estado": "vivo", "fase": fase, "jogo": _do_ponto_de_vista(jogo, clube)}
        if jogo["vencedor"] != clube:
            return {"estado": "eliminado", "fase": fase, "jogo": _do_ponto_de_vista(jogo, clube)}
    return {"estado": "campeao", "fase": "final", "jogo": None}


def _do_ponto_de_vista(jogo, clube):
    em_casa = jogo["mandante"] == clube
    return {
        "adversario": jogo["visitante"] if em_casa else jogo["mandante"],
        "mando": "casa" if em_casa else "fora",
    }


def jogos_da_rodada(dados, rodada, liga_de):
    """A fase jogada depois desta rodada da liga (para o resultado da
    rodada): {fase, nome, jogos} ou None."""
    fase = next((f for f, r in copa.DATAS.items() if r == rodada), None)
    if fase is None or not dados or not dados["fases"].get(fase):
        return None
    return {
        "fase": fase,
        "nome": NOMES[fase],
        "jogos": [_jogo(j, liga_de) for j in dados["fases"][fase]],
    }


# --- caixa de entrada --------------------------------------------------------

def mensagem_de_inicio(campeonato, clube):
    """A mensagem do começo da temporada: entramos na copa ou não. None se
    o save não tem copa."""
    if campeonato.copa is None:
        return None
    sit = situacao(campeonato.copa.para_dict(), clube)
    rodada = copa.DATAS[sit["fase"] or "oitavas"]
    return caixa.copa_classificacao(sit, rodada, sum(copa.PREMIOS.values()))


def mensagem_da_rodada(campeonato, rodada, clube):
    """Depois de uma rodada com copa: o resultado do jogo do técnico nela.
    None se não teve copa ou ele não jogou."""
    if campeonato.copa is None:
        return None
    fase = campeonato.copa.fase_da_rodada(rodada)
    dados = campeonato.copa.para_dict()
    jogo = next(
        (j for j in dados["fases"].get(fase) or []
         if clube in (j["mandante"], j["visitante"])),
        None,
    )
    if jogo is None or jogo["vencedor"] is None:
        return None
    proxima = None
    sit = situacao(dados, clube)
    if sit["estado"] == "vivo" and sit["jogo"]:
        proxima = (sit["fase"], copa.DATAS[sit["fase"]],
                   sit["jogo"]["adversario"], sit["jogo"]["mando"])
    return caixa.copa_resultado(fase, jogo, clube, copa.PREMIOS[fase], proxima)
