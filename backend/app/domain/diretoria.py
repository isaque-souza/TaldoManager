"""Diretoria: o quanto se espera de cada clube (v1.0).

A expectativa nasce da força do elenco comparada com a liga. Por
enquanto só o ranking de força (cards de "Novo jogo"); a meta da
temporada e a demissão vêm em cima dele.
"""

TAMANHO_XI = 11


def forca_do_elenco(clube):
    """Média de overall dos 11 melhores do elenco (0 sem jogadores).

    Usa os 11 melhores, e não o elenco todo: um reserva fraco a mais
    não deixa o clube "pior" — quem decide a força é o time titular.
    """
    melhores = sorted((j.overall for j in clube.jogadores), reverse=True)[:TAMANHO_XI]
    if not melhores:
        return 0
    return round(sum(melhores) / len(melhores), 1)


def ranking_de_forca(clubes):
    """{nome do clube: posição no ranking de força}, 1 = mais forte.

    Empate na força desempata pelo nome, para o ranking ser estável.
    """
    ordem = sorted(clubes, key=lambda c: (-forca_do_elenco(c), c.nome))
    return {c.nome: pos for pos, c in enumerate(ordem, start=1)}
