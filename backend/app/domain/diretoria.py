"""Diretoria: o quanto se espera de cada clube (v1.0).

A expectativa nasce da força do elenco comparada com a liga: o ranking
de força define a meta da temporada (a posição mínima no fim), e a
posição na tabela diz se o técnico está no caminho.
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


def situacao(posicao, meta):
    """'batida' (dentro da meta), 'perto' (até MARGEM_PERTO abaixo) ou 'longe'.

    Durante a temporada vale a posição atual; no fim, a final.
    """
    if posicao <= meta:
        return "batida"
    if posicao <= meta + MARGEM_PERTO:
        return "perto"
    return "longe"
