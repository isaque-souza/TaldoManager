"""Olheiro profissional (v2.0, passo 1).

O técnico não vê o potencial exato dos jogadores dos outros clubes (nem dos
livres): vê a estimativa do olheiro, uma faixa. Quanto maior o nível do
olheiro, mais estreita a faixa — e mais caro ele é. Os jogadores do próprio
clube (inclusive os que vieram emprestados) seguem com o potencial exato, e
o veterano (`evolucao.IDADE_DECLINIO`+) também: todo mundo sabe que ele não
cresce mais.

A faixa sempre contém o potencial verdadeiro, mas não necessariamente no
meio: o deslocamento vem do nome do jogador (crc32), então recarregar não a
muda e subir de nível só a encolhe em volta do valor certo. Nada de
`random`: não mexe na sequência das partidas.

O valor de mercado continua usando o potencial verdadeiro: preço alto ainda
"denuncia" um jovem bom, como no futebol de verdade.

O olheiro tem contrato até o fim da temporada: subir de nível paga na hora
a diferença, proporcional às rodadas que faltam (`custo_da_troca`); descer
não devolve nada. Na virada ele renova pela temporada cheia. Assim não dá
para contratar o melhor só para olhar o mercado e dispensar antes de pagar.
"""

import zlib

from app.domain.evolucao import IDADE_DECLINIO

# nível: (meia largura da faixa, custo por temporada)
NIVEIS = {
    1: (7, 0),
    2: (5, 500_000),
    3: (4, 1_000_000),
    4: (2, 2_000_000),
    5: (1, 4_000_000),
}
NIVEL_INICIAL = 1
POTENCIAL_MAX = 99


class NivelInvalido(ValueError):
    """Nível de olheiro que não existe."""


def validar(nivel):
    if nivel not in NIVEIS:
        raise NivelInvalido(f"O olheiro vai do nível 1 ao {max(NIVEIS)}")
    return nivel


def custo_temporada(nivel):
    return NIVEIS[nivel][1]


def custo_da_troca(de, para, rodadas_jogadas, total_rodadas):
    """Quanto o clube paga agora para trocar o olheiro de nível `de` pelo de
    `para`: a diferença pelo resto da temporada (descer é de graça)."""
    if para <= de:
        return 0
    restantes = max(0, total_rodadas - rodadas_jogadas)
    return round((custo_temporada(para) - custo_temporada(de)) * restantes / total_rodadas)


def motivo_troca_bloqueada(clube, para, custo):
    if para == clube.nivel_olheiro:
        return f"O olheiro já é de nível {para}"
    if custo > clube.dinheiro:
        return "Sem caixa para pagar o olheiro até o fim da temporada"
    return None


def resumo(clube, rodadas_jogadas, total_rodadas):
    """O olheiro do clube e quanto custa trocar por cada nível agora."""
    niveis = []
    for nivel, (meia, custo) in NIVEIS.items():
        agora = custo_da_troca(clube.nivel_olheiro, nivel, rodadas_jogadas, total_rodadas)
        niveis.append({
            "nivel": nivel,
            "faixa": meia,
            "custo_temporada": custo,
            "custo_agora": agora,
            "bloqueio": motivo_troca_bloqueada(clube, nivel, agora),
        })
    return {
        "nivel": clube.nivel_olheiro,
        "caixa": clube.dinheiro,
        "gasto_temporada": clube.despesa_olheiros,
        "niveis": niveis,
    }


def _fracao(nome):
    """Onde o valor verdadeiro cai dentro da faixa: 0 = no começo, 1 = no fim."""
    return zlib.crc32(f"olheiro:{nome}".encode()) / 0xFFFFFFFF


def faixa(jogador, nivel):
    """(mínimo, máximo) do potencial que o olheiro de `nivel` estima, ou
    None se ele o conhece com certeza (o veterano)."""
    if jogador.idade >= IDADE_DECLINIO:
        return None
    meia = NIVEIS[nivel][0]
    abaixo = round(_fracao(jogador.nome) * 2 * meia)
    minimo = max(jogador.overall, jogador.potencial - abaixo)
    maximo = min(POTENCIAL_MAX, jogador.potencial + 2 * meia - abaixo)
    return minimo, maximo


def estimativa(jogador, nivel):
    """O que a tela mostra de um jogador que não é do clube: `potencial` (o
    meio da faixa, para ordenar e filtrar) e `potencial_faixa` (None =
    exato)."""
    f = faixa(jogador, nivel)
    if f is None:
        return {"potencial": jogador.potencial, "potencial_faixa": None}
    return {"potencial": round(sum(f) / 2), "potencial_faixa": list(f)}
