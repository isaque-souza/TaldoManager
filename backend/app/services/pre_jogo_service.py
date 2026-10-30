"""O que cerca o próximo jogo do técnico, para a tela de pré-jogo (v2.3):
forma recente, desfalques, estádio e público.

Só lê: a forma vem das partidas da liga e dos jogos da copa já gravados; os
desfalques, o estádio e o público, do campeonato restaurado do save (que
`temporada_service.pre_jogo` já montou). O público é o mesmo cálculo que o
motor faz no apito (`estadio.publico`, sem nada de sorteio), então a
previsão é o público que vai estar lá, se o técnico não mexer no ingresso.
"""

from app.domain import copa, estadio
from app.repositories import clube_repository as clube_repo
from app.repositories import partida_repository as partida_repo
from app.services import copa_service

ULTIMOS = 5


def contexto(conn, sim, mandante, visitante):
    """{contexto_mandante, contexto_visitante, estadio} do jogo entre
    os clubes (objetos do motor) `mandante` e `visitante`."""
    clubes = {c["nome"]: c for c in clube_repo.listar_por_simulacao(conn, sim["id"])}
    partidas = partida_repo.listar_por_simulacao(conn, sim["id"])
    dados_copa = copa_service.estado_da_copa(sim)
    return {
        "contexto_mandante": _do_clube(mandante, clubes, partidas, dados_copa),
        "contexto_visitante": _do_clube(visitante, clubes, partidas, dados_copa),
        "estadio": _estadio(mandante, visitante),
    }


def _do_clube(clube, clubes, partidas, dados_copa):
    linha = clubes.get(clube.nome)
    jogou = bool(linha and linha["jogos"])
    return {
        "clube": clube.nome,
        "posicao": linha["posicao_final"] if jogou else None,
        "pontos": linha["pontos"] if linha else 0,
        "total_clubes": sum(1 for c in clubes.values() if linha and c["liga"] == linha["liga"]),
        "forma": ultimos_jogos(clube.nome, partidas, dados_copa),
        "desfalques": desfalques(clube),
    }


def ultimos_jogos(nome, partidas, dados_copa, n=ULTIMOS):
    """Os `n` jogos mais recentes do clube (liga e copa), do mais antigo
    para o mais novo. O jogo da copa vem depois da rodada `copa.DATAS[fase]`
    da liga (é no meio da semana seguinte)."""
    jogos = []
    for p in partidas:
        if nome not in (p["mandante_nome"], p["visitante_nome"]):
            continue
        jogos.append(((p["rodada"], 0), _jogo(
            nome, p["mandante_nome"], p["visitante_nome"],
            p["gols_mandante"], p["gols_visitante"],
            competicao="liga", rodada=p["rodada"],
        )))
    for fase in copa.FASES:
        for j in (dados_copa or {}).get("fases", {}).get(fase) or []:
            if nome not in (j["mandante"], j["visitante"]) or not j["vencedor"]:
                continue
            jogos.append(((copa.DATAS[fase], 1), _jogo(
                nome, j["mandante"], j["visitante"],
                j["gols_mandante"], j["gols_visitante"],
                competicao="copa", rodada=copa.DATAS[fase],
                fase=copa_service.NOMES[fase],
                penaltis=j["penaltis"], vencedor=j["vencedor"],
            )))
    jogos.sort(key=lambda par: par[0])
    return [j for _, j in jogos[-n:]]


def _jogo(nome, mandante, visitante, gm, gv, competicao, rodada,
          fase=None, penaltis=None, vencedor=None):
    em_casa = mandante == nome
    pro, contra = (gm, gv) if em_casa else (gv, gm)
    resultado = "V" if pro > contra else "D" if pro < contra else "E"
    jogo = {
        "competicao": competicao,
        "rodada": rodada,
        "fase": fase,
        "adversario": visitante if em_casa else mandante,
        "mando": "casa" if em_casa else "fora",
        "gols_pro": pro,
        "gols_contra": contra,
        "resultado": resultado,
        "penaltis": None,
    }
    if penaltis:
        pm, pv = penaltis
        jogo["penaltis"] = {
            "pro": pm if em_casa else pv,
            "contra": pv if em_casa else pm,
            "classificou": vencedor == nome,
        }
    return jogo


def desfalques(clube):
    """Quem está fora do jogo por lesão ou suspensão, os melhores primeiro.
    `jogos`: quantos ainda vai perder (contando este)."""
    fora = []
    for j in clube.jogadores:
        if j.lesionado:
            motivo, jogos = "lesao", j.rodadas_lesao
        elif j.suspenso:
            motivo, jogos = "suspensao", j.jogos_suspensao
        else:
            continue
        fora.append({
            "nome": j.nome,
            "numero": j.numero,
            "posicao": j.posicao,
            "funcao": j.funcao,
            "overall": j.overall,
            "motivo": motivo,
            "jogos": jogos,
        })
    fora.sort(key=lambda d: -d["overall"])
    return fora


def _estadio(mandante, visitante):
    """O estádio do mandante e o público previsto. None se o clube não tem
    estádio registrado (clubes montados à mão)."""
    if mandante.capacidade <= 0:
        return None
    publico = estadio.publico(mandante, visitante)
    return {
        "clube": mandante.nome,
        "capacidade": mandante.capacidade,
        "publico_previsto": publico,
        "ocupacao": round(estadio.ocupacao(publico, mandante.capacidade), 3),
        "lotado": publico >= mandante.capacidade,
        "classico": (visitante.nome in mandante.rivais
                     or mandante.nome in visitante.rivais),
        "ingresso": estadio.FAIXAS[mandante.ingresso]["nome"],
    }

