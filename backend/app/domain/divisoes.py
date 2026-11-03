"""Divisões (v2.5): cada país tem a Série A e a Série B; na virada os
`SOBEM` melhores da B trocam de lugar com os `SOBEM` piores da A.

A liga é um atributo do clube (`Clube.liga`); aqui fica só quem é A e quem
é B de cada país. Liga fora de `DIVISOES` é uma Série A sem B (sem
acesso nem rebaixamento).
"""

SOBEM = 4      # sobem 4 da B e caem 4 da A

# liga -> (país, divisão)
DIVISOES = {
    "taldo": ("taldo", 1),
    "premier": ("inglaterra", 1),
    "laliga": ("espanha", 1),
    "brasileirao": ("brasil", 1),
    "taldo_b": ("taldo", 2),
    "championship": ("inglaterra", 2),
    "segunda": ("espanha", 2),
    "brasileirao_b": ("brasil", 2),
}


def pais(liga):
    return DIVISOES.get(liga, (liga, 1))[0]


def divisao(liga):
    return DIVISOES.get(liga, (liga, 1))[1]


def eh_primeira(liga):
    return divisao(liga) == 1


def da_divisao(liga, numero):
    """A liga do mesmo país na divisão `numero`, ou None."""
    return next(
        (l for l, (p, d) in DIVISOES.items() if p == pais(liga) and d == numero),
        None,
    )


def primeiras(ligas):
    """Só as Séries A, na ordem."""
    return [l for l in ligas if eh_primeira(l)]


def ordenar(ligas):
    """As ligas na ordem das tabelas: as A, depois as B; dentro da divisão,
    a ordem de `DIVISOES` (as desconhecidas no fim, na ordem dada)."""
    ordem = list(DIVISOES)
    lista = list(dict.fromkeys(ligas))
    return sorted(lista, key=lambda l: (
        divisao(l), ordem.index(l) if l in ordem else len(ordem) + lista.index(l),
    ))


def com_as_series_b(ligas):
    """As `ligas` mais a Série B de cada país que ainda não a tem (um save
    de antes da v2.5 ganha a B na virada). A ordem: as A, depois as B."""
    todas = list(dict.fromkeys(ligas))
    for liga in list(todas):
        b = da_divisao(liga, 2)
        if b and b not in todas:
            todas.append(b)
    return ordenar(todas)


def do_save_na_virada(ligas, todas):
    """As ligas que um save joga depois da virada (v2.5): o que já tem
    Premier (o mundo da v1.6) ganha todas as `todas`; o que só tem a Taldo
    ganha a Série B dela. Na ordem das tabelas."""
    if len(primeiras(set(ligas))) > 1:
        return ordenar(list(ligas) + list(todas))
    return com_as_series_b(ligas)


def acesso_e_rebaixamento(clubes_finais):
    """{nome do clube: liga nova} de quem sobe ou cai, pela tabela da
    temporada que acabou. `clubes_finais`: dicts com `nome`, `liga` e
    `posicao_final` (as linhas da tabela `clube`). Só troca quando o país
    jogou as duas divisões."""
    por_liga = {}
    for c in clubes_finais:
        por_liga.setdefault(c["liga"], []).append(c)
    movimentos = {}
    for liga, clubes in por_liga.items():
        if divisao(liga) != 2:
            continue
        a = da_divisao(liga, 1)
        if a not in por_liga:
            continue
        b_tabela = sorted(clubes, key=lambda c: c["posicao_final"])
        a_tabela = sorted(por_liga[a], key=lambda c: c["posicao_final"])
        for c in b_tabela[:SOBEM]:
            movimentos[c["nome"]] = a
        for c in a_tabela[-SOBEM:]:
            movimentos[c["nome"]] = liga
    return movimentos
