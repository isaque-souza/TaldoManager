"""Relatório pós-jogo (v2.2): leituras do jogo que acabou de acontecer.

Tudo aqui é cálculo sobre o que o motor já produziu (placar, lances,
notas, força dos elencos): nada sorteia, nada grava. O serviço
(`app.services.pos_jogo_service`) junta os dados do banco e chama estas
funções.
"""

# A expectativa vem da força dos elencos (`diretoria.forca_do_elenco`) e do
# mando. Calibrado em 12 temporadas no automático: jogar em casa vale uns 3
# pontos de força (com a mesma força, o mandante vence 46% e o visitante
# 30%), então o mando soma metade disso para um lado e tira do outro.
MANDO = 1.5
# a partir de quanto de vantagem (já com o mando) o time é o favorito: com 2
# pontos ele vence mais da metade dos jogos
FAVORITO = 2.0

RESULTADO_PONTOS = {"vitoria": 1, "empate": 0, "derrota": -1}
EXPECTATIVA_PONTOS = {"favorito": 1, "equilibrado": 0, "azarao": -1}

EXPECTATIVA_TEXTO = {
    "favorito": "Favorito",
    "equilibrado": "Jogo equilibrado",
    "azarao": "Azarão",
}

# resultado − expectativa: de −2 (o favorito perdeu) a +2 (o azarão venceu)
DESEMPENHO = {
    2: ("muito_acima", "Zebra a favor: venceu sendo o azarão"),
    1: ("acima", "Acima do esperado"),
    0: ("esperado", "Dentro do esperado"),
    -1: ("abaixo", "Abaixo do esperado"),
    -2: ("muito_abaixo", "Zebra contra: perdeu sendo o favorito"),
}

TIPOS_GOL = ("gol", "penalti")


def resultado(gols_pro, gols_contra):
    """'vitoria', 'empate' ou 'derrota' no tempo normal (o pênalti da copa
    decide a vaga, não o resultado do jogo)."""
    if gols_pro > gols_contra:
        return "vitoria"
    if gols_pro < gols_contra:
        return "derrota"
    return "empate"


def expectativa(forca_eu, forca_rival, mando):
    """{nivel, texto, vantagem}: quem era o favorito antes da bola rolar.
    `mando`: 'casa' ou 'fora'. `vantagem` é a diferença de força já com o
    mando (positiva: a favor)."""
    vantagem = forca_eu - forca_rival + (MANDO if mando == "casa" else -MANDO)
    if vantagem >= FAVORITO:
        nivel = "favorito"
    elif vantagem <= -FAVORITO:
        nivel = "azarao"
    else:
        nivel = "equilibrado"
    return {"nivel": nivel, "texto": EXPECTATIVA_TEXTO[nivel], "vantagem": round(vantagem, 1)}


def desempenho(res, nivel):
    """{nivel, texto}: o resultado comparado com a expectativa."""
    delta = RESULTADO_PONTOS[res] - EXPECTATIVA_PONTOS[nivel]
    chave, texto = DESEMPENHO[delta]
    return {"nivel": chave, "texto": texto}


def momento_decisivo(eventos, gols_mandante, gols_visitante, mandante):
    """O lance que decidiu o placar, ou None. `eventos` em ordem
    cronológica: dicts com minuto, tipo, jogador e clube.

    Com vencedor, é o gol que o pôs à frente de vez (o gol nº perdedor + 1
    dele). No empate com gols, o último gol (o do empate). No 0 x 0, o
    pênalti desperdiçado ou a expulsão, se houve.
    """
    gols = [e for e in eventos if e["tipo"] in TIPOS_GOL]
    if gols_mandante != gols_visitante:
        vencedor_e_mandante = gols_mandante > gols_visitante
        do_perdedor = min(gols_mandante, gols_visitante)
        dele = [
            e for e in gols
            if (e["clube"] == mandante) == vencedor_e_mandante
        ]
        if len(dele) > do_perdedor:
            return {**_lance(dele[do_perdedor]), "tipo_momento": "gol_da_vitoria"}
        return None
    if gols:
        return {**_lance(gols[-1]), "tipo_momento": "gol_do_empate"}
    for tipo, momento in (("penalti_perdido", "penalti_perdido"),
                          ("penalti_defendido", "penalti_defendido"),
                          ("expulsao", "expulsao")):
        lance = next((e for e in eventos if e["tipo"] == tipo), None)
        if lance:
            return {**_lance(lance), "tipo_momento": momento}
    return None


def _lance(e):
    return {k: e.get(k) for k in ("minuto", "tipo", "jogador", "clube")}


def destaques(atuacoes, clube):
    """{melhor_em_campo, melhor_do_time, pior_do_time} a partir das notas
    do motor. `atuacoes`: dicts com jogador, clube, titular, gols,
    assistencias e nota. O pior é entre os titulares (quem entrou no fim
    mal pegou na bola). Nota igual desempata por gols + assistências."""
    def chave(a):
        return (a["nota"], a["gols"] + a["assistencias"])

    if not atuacoes:
        return {"melhor_em_campo": None, "melhor_do_time": None, "pior_do_time": None}
    do_time = [a for a in atuacoes if a["clube"] == clube]
    titulares = [a for a in do_time if a["titular"]] or do_time
    return {
        "melhor_em_campo": max(atuacoes, key=chave),
        "melhor_do_time": max(do_time, key=chave) if do_time else None,
        "pior_do_time": min(titulares, key=chave) if titulares else None,
    }


def tabela(clubes, partidas):
    """Posição de cada clube a partir das partidas: {nome: posição}.
    `clubes` na ordem de desempate final (a do motor); `partidas` com
    mandante, visitante e os gols. Mesmo critério de
    `Campeonato.classificacao`: pontos, saldo, gols marcados."""
    linha = {c: {"pontos": 0, "saldo": 0, "gols": 0} for c in clubes}
    for p in partidas:
        m, v = p["mandante"], p["visitante"]
        gm, gv = p["gols_mandante"], p["gols_visitante"]
        if m not in linha or v not in linha:
            continue
        linha[m]["gols"] += gm
        linha[v]["gols"] += gv
        linha[m]["saldo"] += gm - gv
        linha[v]["saldo"] += gv - gm
        if gm > gv:
            linha[m]["pontos"] += 3
        elif gm < gv:
            linha[v]["pontos"] += 3
        else:
            linha[m]["pontos"] += 1
            linha[v]["pontos"] += 1
    ordem = sorted(
        clubes,
        key=lambda c: (linha[c]["pontos"], linha[c]["saldo"], linha[c]["gols"]),
        reverse=True,
    )
    return {c: pos for pos, c in enumerate(ordem, start=1)}
