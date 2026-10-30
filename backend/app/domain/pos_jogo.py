"""Relatório pós-jogo (v2.2): leituras do jogo que acabou de acontecer.

Tudo aqui é cálculo sobre o que o motor já produziu (placar, lances,
notas): nada sorteia, nada grava. O serviço
(`app.services.pos_jogo_service`) junta os dados do banco e chama estas
funções.
"""


def resultado(gols_pro, gols_contra):
    """'vitoria', 'empate' ou 'derrota' no tempo normal (o pênalti da copa
    decide a vaga, não o resultado do jogo)."""
    if gols_pro > gols_contra:
        return "vitoria"
    if gols_pro < gols_contra:
        return "derrota"
    return "empate"


def destaques(atuacoes, clube):
    """{melhor_em_campo, melhor_do_time} a partir das notas do motor.
    `atuacoes`: dicts com jogador, clube, titular, gols, assistencias e
    nota. Nota igual desempata por gols + assistências."""
    def chave(a):
        return (a["nota"], a["gols"] + a["assistencias"])

    if not atuacoes:
        return {"melhor_em_campo": None, "melhor_do_time": None}
    do_time = [a for a in atuacoes if a["clube"] == clube]
    return {
        "melhor_em_campo": max(atuacoes, key=chave),
        "melhor_do_time": max(do_time, key=chave) if do_time else None,
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
