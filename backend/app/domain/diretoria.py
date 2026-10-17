"""Diretoria: o quanto se espera de cada clube (v1.0).

A expectativa nasce da força do elenco comparada com a liga: o ranking
de força define a meta da temporada (a posição mínima no fim), e a
posição na tabela diz se o técnico está no caminho. No fim de cada
temporada a diretoria avalia o cargo: longe da meta duas vezes seguidas,
ou muito abaixo numa só, é demissão — e fim de carreira.
"""

# o melhor XI no 4-3-3 (a formação padrão), como o motor escala
VAGAS_XI = {"Goleiro": 1, "Defesa": 4, "Meio-Campo": 3, "Atacante": 3}

# (pior ranking de força da faixa, meta = posição mínima, descrição).
# Calibrado em 60 temporadas no automático: a maioria das faixas bate a
# meta em 60–75% das vezes sem técnico — jogar bem faz a diferença.
FAIXAS_META = (
    (1, 1, "Ser campeão"),
    (4, 4, "Terminar no G-4"),
    (8, 8, "Terminar no top 8"),
    (14, 12, "Meio de tabela (até 12º)"),
    (18, 16, "Ficar fora do Z-4"),
    (20, 18, "Fugir das 2 últimas"),
)

# até quantas posições abaixo da meta ainda é "perto" (em risco)
MARGEM_PERTO = 3

# terminar tantas posições (ou mais) abaixo da meta demite numa temporada só
MUITO_ABAIXO = 8

TOTAL_CLUBES = 20


def forca_do_elenco(clube):
    """Média de overall do melhor XI no 4-3-3 (0 sem jogadores).

    Respeita as posições, como o motor ao escalar: 11 craques que são
    todos meias não fazem um time forte. Se faltar gente numa posição,
    usa quem tem.
    """
    xi = []
    for posicao, vagas in VAGAS_XI.items():
        da_posicao = sorted(
            (j.overall for j in clube.jogadores if j.posicao == posicao),
            reverse=True,
        )
        xi += da_posicao[:vagas]
    if not xi:
        return 0
    return round(sum(xi) / len(xi), 1)


def ranking_de_forca(clubes):
    """{nome do clube: posição no ranking de força}, 1 = mais forte.

    Empate na força desempata pelo nome, para o ranking ser estável.
    """
    ordem = sorted(clubes, key=lambda c: (-forca_do_elenco(c), c.nome))
    return {c.nome: pos for pos, c in enumerate(ordem, start=1)}


def meta_da_temporada(ranking):
    """Posição mínima que a diretoria cobra de quem é o `ranking`º em força."""
    for pior_ranking, meta, _ in FAIXAS_META:
        if ranking <= pior_ranking:
            return meta
    return FAIXAS_META[-1][1]   # liga maior que 20: a faixa mais baixa


def descricao_meta(meta):
    """Texto da meta ("Terminar no G-4") a partir da posição mínima."""
    for _, posicao, descricao in FAIXAS_META:
        if posicao == meta:
            return descricao
    return f"Terminar até o {meta}º lugar"


def situacao(posicao, meta, total=TOTAL_CLUBES):
    """'batida' (dentro da meta), 'perto' (até MARGEM_PERTO abaixo) ou 'longe'.

    Terminar em último é sempre 'longe': sem isso, quem tem meta "até 18º"
    nunca ficaria longe (18 + 3 passa do 20º). Durante a temporada vale a
    posição atual; no fim, a final.
    """
    if posicao <= meta:
        return "batida"
    if posicao <= meta + MARGEM_PERTO and posicao < total:
        return "perto"
    return "longe"


def avaliar_cargo(atual, anterior=None, total=TOTAL_CLUBES):
    """O cargo do técnico: {"estado": mantido | ameacado | demitido, "motivo"}.

    `atual` e `anterior` são (posição final, meta) de uma temporada
    concluída, ou None (sem meta, em andamento, ou não existe). Com
    `atual` None (temporada em andamento), só avisa a ameaça herdada.
    """
    def longe(t):
        return t is not None and situacao(t[0], t[1], total) == "longe"

    if atual is None:
        if longe(anterior):
            return {
                "estado": "ameacado",
                "motivo": "Longe da meta na temporada passada: "
                          "outra temporada assim e você está fora.",
            }
        return {"estado": "mantido", "motivo": None}

    posicao, meta = atual
    if posicao - meta >= MUITO_ABAIXO:
        return {
            "estado": "demitido",
            "motivo": f"Terminou em {posicao}º, {posicao - meta} posições "
                      f"abaixo da meta ({meta}º).",
        }
    if longe(atual) and longe(anterior):
        return {
            "estado": "demitido",
            "motivo": "Longe da meta em duas temporadas seguidas.",
        }
    if longe(atual):
        return {
            "estado": "ameacado",
            "motivo": "Longe da meta: outra temporada assim e você está fora.",
        }
    return {"estado": "mantido", "motivo": None}


def resumo_carreira(temporadas, total=TOTAL_CLUBES):
    """Balanço do técnico para a tela de fim de carreira.

    temporadas: [{"posicao", "meta", "campeao"}] das temporadas concluídas
    (meta None = save antigo, não entra na conta de metas).
    """
    com_meta = [t for t in temporadas if t["meta"] is not None]
    return {
        "temporadas": len(temporadas),
        "titulos": sum(t["campeao"] for t in temporadas),
        "metas_batidas": sum(
            situacao(t["posicao"], t["meta"], total) == "batida" for t in com_meta
        ),
        "metas_avaliadas": len(com_meta),
        "melhor_posicao": min((t["posicao"] for t in temporadas), default=None),
    }
