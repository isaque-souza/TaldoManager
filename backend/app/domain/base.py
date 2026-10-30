"""Jovens da base (v0.8): na virada, cada clube sobe jovens das categorias de
base para repor quem saiu.

Clube grande tem base melhor: o overall do jovem parte da média do elenco.
A posição (específica, v1.3) é a mais carente do elenco, comparando com a
composição da seed, então nenhum clube fica sem goleiro.

O clube do técnico (v2.0, passo 4) tem uma base de verdade, separada do
elenco: os jovens chegam nas peneiras que ele faz (uma a cada 90 dias),
crescem um pouco a cada rodada jogada e só sobem quando ele os promove — ver a
segunda metade do módulo. Na virada, o clube dele só ganha jovens gerados
se o elenco cair abaixo do mínimo (`quantos_sobem`).
"""

import random
from dataclasses import dataclass
from datetime import timedelta
from itertools import product

from app.domain import mercado, posicoes
from app.domain.evolucao import revisar_potencial
from app.domain.jogador import Jogador
from app.domain.nomes import NOMES, SOBRENOMES

TAMANHO_ALVO = 23             # tamanho dos elencos da seed (v1.6)
MINIMO_POR_TEMPORADA = 1      # todo clube revela pelo menos um jovem
# o elenco de 23 da seed (scripts/ampliar_elencos.py): cobre o que a formação
# mais exigente pede de cada posição (posicoes.MINIMO_POR_POSICAO) e tem 3
# goleiros, para o clube poder vender um sem cair abaixo de
# mercado.GOLEIROS_MIN
COMPOSICAO_IDEAL = {
    "Goleiro": 3, "Zagueiro": 4, "Lateral": 3, "Volante": 2,
    "Meia central": 3, "Meia-atacante": 2, "Ponta": 3,
    "Segundo atacante": 1, "Centroavante": 2,
}

IDADE_MIN, IDADE_MAX = 16, 18
# jovem ≈ média do elenco − 10. Com −15 a liga entrava numa espiral (o jovem
# nasce pior, a média cai, o próximo nasce pior ainda: 78,6 → 75,8 em 8
# temporadas); com −10 o overall médio fica estável (~78,4 em 10 temporadas)
DESCONTO_OVERALL = 10
VARIACAO_OVERALL = 4
MARGEM_POTENCIAL = (8, 22)    # às vezes sai uma joia
OVERALL_MIN = 40


def quantos_sobem(clube, do_tecnico=False):
    """Completa o elenco até TAMANHO_ALVO, com pelo menos um por temporada,
    sem passar de ELENCO_MAX. O clube do técnico (v2.0) promove os da base
    ele mesmo: só ganha jovens para não ficar abaixo de ELENCO_MIN."""
    if do_tecnico:
        return max(0, mercado.ELENCO_MIN - len(clube.jogadores))
    vagas = mercado.ELENCO_MAX - len(clube.jogadores)
    return max(0, min(vagas, max(MINIMO_POR_TEMPORADA,
                                 TAMANHO_ALVO - len(clube.jogadores))))


def posicao_carente(clube, rng):
    """A posição com o maior déficit em relação à composição ideal (empate
    decidido na sorte)."""
    deficit = {
        pos: ideal - sum(1 for j in clube.jogadores if j.funcao == pos)
        for pos, ideal in COMPOSICAO_IDEAL.items()
    }
    maior = max(deficit.values())
    return rng.choice([pos for pos, d in deficit.items() if d == maior])


def gerar_nome(proibidos, rng, nomes=NOMES, sobrenomes=SOBRENOMES):
    """Nome que ainda não existe (`proibidos` é atualizado). Sorteia; se a
    sorte não acha, percorre as combinações; esgotadas, numera ("Jr.", "II").
    `nomes` e `sobrenomes`: as listas (as de uma região, v2.0).
    """
    for _ in range(50):
        nome = f"{rng.choice(nomes)} {rng.choice(sobrenomes)}"
        if nome not in proibidos:
            proibidos.add(nome)
            return nome
    for sufixo in ("", " Jr.", " II", " III", " IV"):
        for n, s in product(nomes, sobrenomes):
            nome = f"{n} {s}{sufixo}"
            if nome not in proibidos:
                proibidos.add(nome)
                return nome
    raise RuntimeError("Acabaram os nomes")


def gerar_jovem(clube, proibidos, rng):
    """Um jovem da base para o `clube`, já com contrato (3 temporadas, salário
    de mercado, sem multa — o padrão do `Jogador`)."""
    media = sum(j.overall for j in clube.jogadores) / len(clube.jogadores)
    overall = round(media) - DESCONTO_OVERALL + rng.randint(
        -VARIACAO_OVERALL, VARIACAO_OVERALL
    )
    overall = max(OVERALL_MIN, overall)
    potencial = min(99, overall + rng.randint(*MARGEM_POTENCIAL))
    funcao = posicao_carente(clube, rng)
    jovem = Jogador(
        gerar_nome(proibidos, rng),
        rng.randint(IDADE_MIN, IDADE_MAX),
        posicoes.SETOR[funcao],
        overall,
        potencial=potencial,
        contrato_anos=mercado.CONTRATO_PADRAO_ANOS,
        funcao=funcao,
    )
    jovem.formador = clube.nome   # cria da casa (v1.9)
    return jovem


def subir_jovens(campeonato, nomes_usados, rng, clube_usuario=None):
    """Cada clube sobe seus jovens (ver `quantos_sobem`). `nomes_usados`: os
    nomes que não podem se repetir (seed + quem já passou pela carreira).
    Devolve os movimentos (`subiu_da_base`)."""

    proibidos = set(nomes_usados) | {
        j.nome for c in campeonato.clubes for j in c.jogadores
    }
    movimentos = []
    for clube in campeonato.clubes:
        for _ in range(quantos_sobem(clube, clube.nome == clube_usuario)):
            jovem = gerar_jovem(clube, proibidos, rng)
            clube.contratar_jogador(jovem)
            movimentos.append({
                "tipo": "subiu_da_base",
                "jogador": jovem.nome,
                "clube": clube.nome,
                "posicao": jovem.posicao,
                "idade": jovem.idade,
                "overall": jovem.overall,
                "detalhe": f"potencial {jovem.potencial}",
            })
    return movimentos


# ---------------------------------------------------------------------------
# a base do técnico (v2.0, passo 4)
# ---------------------------------------------------------------------------

VAGAS = 15
IDADE_LIMITE = 20             # quem chega a essa idade na base vai embora
IDADE_PENEIRA = (15, 17)
IDADE_INICIAL = (15, 18)      # a base com que um jogo novo começa
JOVENS_INICIAIS = 4
INTERVALO_PENEIRA = timedelta(days=90)   # uma peneira a cada 3 meses

# nível: (desconto no overall, margem do potencial, ritmo, custo por
# temporada, jovens por peneira). Ritmo 1 = cresce na temporada como um
# jovem titular (a fração da margem de `evolucao`); o 0,6 do nível 1 é o de
# quem quase não joga. A margem para de subir no nível 3 (v2.0, equilíbrio):
# com 26 e 28 nos níveis 4 e 5, 97% dos jovens do nível 5 chegavam aos 19
# perto do XI e 80% com potencial de titular até do clube mais forte; com
# 24, ~62% (o nível 5 segue à frente pelo ritmo, pelo desconto e pela
# quantidade)
NIVEIS = {
    1: (14, (8, 20), 0.6, 0, (2, 3)),
    2: (13, (9, 22), 0.8, 500_000, (2, 4)),
    3: (12, (10, 24), 1.0, 1_000_000, (3, 4)),
    4: (11, (10, 24), 1.15, 2_000_000, (3, 5)),
    5: (10, (10, 24), 1.3, 4_000_000, (4, 6)),
}
NIVEL_INICIAL = 1
CRESCIMENTO_TEMPORADA = 0.35  # a fração de `evolucao` até os 20 anos
PARTIDAS_NA_BASE = 10         # na revisão do potencial: treina e joga, sem banco


class NivelInvalido(ValueError):
    """Nível de base que não existe."""


@dataclass
class Jovem:
    """Um jovem da base do técnico. O overall é fracionário: cresce um
    pouco a cada rodada e a tela mostra o inteiro."""
    nome: str
    idade: int
    funcao: str
    overall: float
    potencial: int
    id: int | None = None
    pais: str | None = None   # só os que vêm dos olheiros da base


def validar(nivel):
    if nivel not in NIVEIS:
        raise NivelInvalido(f"A base vai do nível 1 ao {max(NIVEIS)}")
    return nivel


def custo_temporada(nivel):
    return NIVEIS[nivel][3]


def custo_da_troca(de, para, rodadas_jogadas, total_rodadas):
    """Como no olheiro: subir paga a diferença pelo resto da temporada,
    descer é de graça."""
    if para <= de:
        return 0
    restantes = max(0, total_rodadas - rodadas_jogadas)
    return round((custo_temporada(para) - custo_temporada(de)) * restantes / total_rodadas)


def motivo_troca_bloqueada(clube, para, custo):
    if para == clube.nivel_base:
        return f"A base já é de nível {para}"
    if custo > clube.dinheiro:
        return "Sem caixa para pagar a base até o fim da temporada"
    return None


def resumo_niveis(clube, rodadas_jogadas, total_rodadas):
    niveis = []
    for nivel, (_, margem, ritmo, custo, por_peneira) in NIVEIS.items():
        agora = custo_da_troca(clube.nivel_base, nivel, rodadas_jogadas, total_rodadas)
        niveis.append({
            "nivel": nivel,
            "ritmo": ritmo,
            "margem_max": margem[1],
            "por_peneira": list(por_peneira),
            "custo_temporada": custo,
            "custo_agora": agora,
            "bloqueio": motivo_troca_bloqueada(clube, nivel, agora),
        })
    return niveis


def peneira_liberada_em(ultima):
    """O dia em que a próxima peneira fica disponível; None = já está
    (nenhuma feita nesta temporada)."""
    return None if ultima is None else ultima + INTERVALO_PENEIRA


def motivo_peneira_bloqueada(ultima, hoje, ocupadas):
    liberada = peneira_liberada_em(ultima)
    if liberada and hoje < liberada:
        return f"A próxima peneira só em {(liberada - hoje).days} dias"
    if ocupadas >= VAGAS:
        return f"A base está cheia ({VAGAS} jovens): promova ou dispense alguém"
    return None


def rng_da_peneira(seed, simulacao_id, momento):
    """Sorteio próprio da base: não mexe na sequência das partidas e dá o
    mesmo resultado se o save for recarregado. `momento`: o que distingue
    um sorteio do outro (a temporada e o dia da peneira, a virada...)."""
    origem = seed if seed is not None else f"s{simulacao_id}"
    return random.Random(f"base:{origem}:{momento}")


def _funcao(rng):
    """Uma posição na proporção do elenco ideal (3 goleiros em 23...)."""
    funcoes = list(COMPOSICAO_IDEAL)
    return rng.choices(funcoes, weights=[COMPOSICAO_IDEAL[f] for f in funcoes])[0]


def gerar_da_peneira(media_elenco, nivel, proibidos, rng, idades=IDADE_PENEIRA):
    """Um jovem que chega à base do técnico (`proibidos` é atualizado)."""
    desconto, margem = NIVEIS[nivel][:2]
    overall = max(OVERALL_MIN, round(media_elenco) - desconto
                  + rng.randint(-VARIACAO_OVERALL, VARIACAO_OVERALL))
    return Jovem(
        nome=gerar_nome(proibidos, rng),
        idade=rng.randint(*idades),
        funcao=_funcao(rng),
        overall=float(overall),
        potencial=min(99, overall + rng.randint(*margem)),
    )


def quantos_na_peneira(ocupadas, nivel, rng):
    """(quantos ficam, quantos não cabem na base). O nível diz quantos a
    peneira acha."""
    chegam = rng.randint(*NIVEIS[nivel][4])
    cabem = max(0, VAGAS - ocupadas)
    return min(chegam, cabem), max(0, chegam - cabem)


def crescer(jovem, nivel, total_rodadas):
    """Uma rodada de treino: o jovem ganha uma fração da margem até o
    potencial; somadas as rodadas da temporada, dá a fração do nível."""
    fracao = min(0.95, CRESCIMENTO_TEMPORADA * NIVEIS[nivel][2])
    por_rodada = 1 - (1 - fracao) ** (1 / total_rodadas)
    jovem.overall = min(
        float(jovem.potencial),
        jovem.overall + (jovem.potencial - jovem.overall) * por_rodada,
    )
    return jovem


def envelhecer(jovem, rng):
    """Na virada: um ano a mais e o potencial revisto."""
    jovem.idade += 1
    jovem.potencial = revisar_potencial(
        jovem.idade, int(jovem.overall), jovem.potencial, PARTIDAS_NA_BASE, rng,
    )
    jovem.overall = min(jovem.overall, float(jovem.potencial))
    return jovem


def ultimo_ano(jovem):
    """Faz IDADE_LIMITE na virada: promova antes ou ele vai embora."""
    return jovem.idade + 1 >= IDADE_LIMITE


def motivo_promocao_bloqueada(clube):
    if len(clube.jogadores) >= mercado.ELENCO_MAX:
        return f"O elenco já tem {mercado.ELENCO_MAX} jogadores"
    return None


def promover(jovem, clube, proibidos, rng):
    """O jovem vira jogador do elenco, com o contrato padrão dos jovens
    (3 temporadas, salário de mercado, sem multa). Se o nome dele apareceu
    no futebol nesse meio-tempo, ganha outro (o motor separa por nome)."""
    nome = jovem.nome if jovem.nome not in proibidos else gerar_nome(proibidos, rng)
    jogador = Jogador(
        nome, jovem.idade, posicoes.SETOR[jovem.funcao], int(jovem.overall),
        potencial=jovem.potencial, contrato_anos=mercado.CONTRATO_PADRAO_ANOS,
        funcao=jovem.funcao,
    )
    jogador.formador = clube.nome   # cria da casa (v1.9)
    clube.contratar_jogador(jogador)
    return jogador
