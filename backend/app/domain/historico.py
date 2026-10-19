"""Histórico da carreira (v0.8): campeões, recordes e Hall da Fama.

Nada aqui é guardado: tudo é calculado das tabelas `clube`/`jogador` de cada
temporada e dos aposentados em `movimento_virada`. Assim não há dado
duplicado que possa ficar desatualizado (o mesmo princípio do valor de
mercado). Só contam temporadas concluídas.

Os jogadores são somados pelo nome: os nomes nunca se repetem na carreira
(ver `base.gerar_nome`), então o nome identifica o jogador entre temporadas,
mesmo quando ele troca de clube.
"""

# pontos de lenda (Hall da Fama)
PONTOS_TITULO = 2
PONTOS_COPA = 1              # copa entre as ligas (v1.6): metade da liga
PONTOS_PREMIO = 3            # artilheiro ou MVP de uma temporada
GOLS_POR_PONTO = 25
PICO_LENDA = 90              # pico de overall que vale pontos
PONTOS_PICO = 2
PONTOS_HALL = 5              # mínimo para entrar
# o título só conta para quem jogou: senão o reserva que nunca entrou em
# campo vira lenda só por estar no elenco campeão (o mesmo corte de "banco"
# da evolução)
PARTIDAS_TITULO = 10

LIMITE_LIDERES = 10


def chave_mvp(j):
    """Critério do MVP da temporada (o mesmo da visão da temporada)."""
    return (
        j["melhor_em_campo"],
        j["nota_media"],
        j["gols"] + j["assistencias"],
        j["hat_tricks"],
    )


def chave_artilheiro(j):
    return (j["gols"], j["assistencias"])


def _destaque(j, valor):
    return {"nome": j["nome"], "clube": j["clube"], "valor": valor}


def resumo_temporada(clubes, jogadores, clube_usuario=None):
    """Campeão, vice, artilheiro, MVP e a posição do clube do técnico de uma
    temporada concluída. `clubes`/`jogadores` no formato das tabelas
    (jogador com o nome do `clube`)."""

    ordem = sorted(clubes, key=lambda c: c["posicao_final"])
    artilheiro = max(jogadores, key=chave_artilheiro, default=None)
    mvp = max(jogadores, key=chave_mvp, default=None)
    posicao_usuario = next(
        (c["posicao_final"] for c in ordem if c["nome"] == clube_usuario), None
    )
    return {
        "campeao": ordem[0]["nome"] if ordem else None,
        "vice": ordem[1]["nome"] if len(ordem) > 1 else None,
        "artilheiro": (
            _destaque(artilheiro, artilheiro["gols"])
            if artilheiro and artilheiro["gols"] > 0 else None
        ),
        "mvp": (
            _destaque(mvp, mvp["melhor_em_campo"])
            if mvp and mvp["melhor_em_campo"] > 0 else None
        ),
        "posicao_usuario": posicao_usuario,
        # com duas ligas (v1.6), os campeões de todas: o título de jogador
        # vale em qualquer uma (quem chama completa; uma liga só = este)
        "campeoes": [ordem[0]["nome"]] if ordem else [],
        "campeao_copa": None,
    }


def totais_por_jogador(temporadas):
    """Soma a carreira de cada jogador. `temporadas`: lista de
    `{"jogadores": [...], "resumo": resumo_temporada(...)}`, em ordem.
    O `clube` de cada um é o da última temporada jogada."""

    totais = {}
    for t in temporadas:
        resumo = t["resumo"]
        premiados = {
            "artilharias": resumo["artilheiro"],
            "mvps": resumo["mvp"],
        }
        for j in t["jogadores"]:
            r = totais.setdefault(j["nome"], {
                "nome": j["nome"],
                "posicao": j["posicao"],
                "clube": j["clube"],
                "temporadas": 0,
                "partidas": 0,
                "gols": 0,
                "assistencias": 0,
                "titulos": 0,
                "copas": 0,
                "artilharias": 0,
                "mvps": 0,
                "pico_overall": 0,
            })
            r["clube"] = j["clube"]
            r["temporadas"] += 1
            r["partidas"] += j["partidas"]
            r["gols"] += j["gols"]
            r["assistencias"] += j["assistencias"]
            r["pico_overall"] = max(r["pico_overall"], j["overall"])
            # campeão = jogou pelo elenco campeão (estava nele ao fim da
            # temporada, com PARTIDAS_TITULO jogos ou mais)
            if j["partidas"] >= PARTIDAS_TITULO:
                if j["clube"] in resumo.get("campeoes", [resumo["campeao"]]):
                    r["titulos"] += 1
                if j["clube"] == resumo.get("campeao_copa"):
                    r["copas"] += 1
            for campo, premiado in premiados.items():
                if premiado and premiado["nome"] == j["nome"]:
                    r[campo] += 1
    return totais


def titulos_por_clube(resumos, chave="campeao"):
    """`resumos`: `(temporada, resumo)` em ordem. Mais títulos primeiro;
    empate: quem ganhou primeiro. `chave`: "campeao" (a liga) ou
    "campeao_copa"."""

    por_clube = {}
    for temporada, resumo in resumos:
        if resumo.get(chave):
            por_clube.setdefault(resumo[chave], []).append(temporada)
    ordem = sorted(por_clube.items(), key=lambda kv: (-len(kv[1]), kv[1][0]))
    return [
        {"clube": clube, "titulos": len(anos), "temporadas": anos}
        for clube, anos in ordem
    ]


def lideres(totais, limite=LIMITE_LIDERES):
    """Os líderes históricos da carreira em gols, assistências, partidas e
    prêmios (artilharias + MVPs)."""

    jogadores = list(totais.values())

    def top(chave):
        itens = [j for j in jogadores if chave(j)[0] > 0]
        return sorted(itens, key=chave, reverse=True)[:limite]

    return {
        "gols": top(lambda j: (j["gols"], j["assistencias"])),
        "assistencias": top(lambda j: (j["assistencias"], j["gols"])),
        "partidas": top(lambda j: (j["partidas"], j["gols"])),
        "premios": top(lambda j: (j["artilharias"] + j["mvps"], j["titulos"])),
    }


def pontos_de_lenda(total):
    pontos = PONTOS_TITULO * total["titulos"]
    pontos += PONTOS_COPA * total.get("copas", 0)
    pontos += PONTOS_PREMIO * (total["artilharias"] + total["mvps"])
    pontos += total["gols"] // GOLS_POR_PONTO
    if total["pico_overall"] >= PICO_LENDA:
        pontos += PONTOS_PICO
    return pontos


def motivo(total):
    """O porquê da lenda, em texto: "3× campeão · artilheiro 2× · 61 gols ·
    pico 93"."""

    partes = []
    if total["titulos"]:
        partes.append(f"{total['titulos']}× campeão")
    if total.get("copas"):
        partes.append(f"copa {total['copas']}×")
    if total["artilharias"]:
        partes.append(f"artilheiro {total['artilharias']}×")
    if total["mvps"]:
        partes.append(f"MVP {total['mvps']}×")
    if total["gols"]:
        partes.append(f"{total['gols']} gol{'s' if total['gols'] > 1 else ''}")
    partes.append(f"pico {total['pico_overall']}")
    return " · ".join(partes)


def hall_da_fama(totais, aposentados):
    """Os aposentados com pelo menos PONTOS_HALL pontos de lenda, do maior
    para o menor. `aposentados`: movimentos `aposentou` com a
    `ultima_temporada` jogada."""

    lendas = []
    for mov in aposentados:
        total = totais.get(mov["jogador"])
        if total is None:
            continue
        # o overall da aposentadoria já é o pós-envelhecimento: só conta
        # se for maior (não costuma ser)
        total = {
            **total,
            "clube": mov["clube"],
            "pico_overall": max(total["pico_overall"], mov["overall"]),
        }
        pontos = pontos_de_lenda(total)
        if pontos < PONTOS_HALL:
            continue
        lendas.append({
            **total,
            "idade": mov["idade"],
            "ultima_temporada": mov["ultima_temporada"],
            "pontos": pontos,
            "motivo": motivo(total),
        })
    return sorted(lendas, key=lambda l: (l["pontos"], l["gols"]), reverse=True)
