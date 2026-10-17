"""Jovens da base (v0.8): na virada, cada clube sobe jovens das categorias de
base para repor quem saiu.

Clube grande tem base melhor: o overall do jovem parte da média do elenco.
A posição é a mais carente do elenco, comparando com a composição da seed,
então nenhum clube fica sem goleiro.
"""

from itertools import product

from app.domain import mercado
from app.domain.jogador import Jogador
from app.domain.nomes import NOMES, SOBRENOMES

TAMANHO_ALVO = 18             # tamanho dos elencos da seed
MINIMO_POR_TEMPORADA = 1      # todo clube revela pelo menos um jovem
COMPOSICAO_IDEAL = {"Goleiro": 2, "Defesa": 6, "Meio-Campo": 5, "Atacante": 5}

IDADE_MIN, IDADE_MAX = 16, 18
# jovem ≈ média do elenco − 10. Com −15 a liga entrava numa espiral (o jovem
# nasce pior, a média cai, o próximo nasce pior ainda: 78,6 → 75,8 em 8
# temporadas); com −10 o overall médio fica estável (~78,4 em 10 temporadas)
DESCONTO_OVERALL = 10
VARIACAO_OVERALL = 4
MARGEM_POTENCIAL = (8, 22)    # às vezes sai uma joia
OVERALL_MIN = 40


def quantos_sobem(clube):
    """Completa o elenco até TAMANHO_ALVO, com pelo menos um por temporada,
    sem passar de ELENCO_MAX."""
    vagas = mercado.ELENCO_MAX - len(clube.jogadores)
    return max(0, min(vagas, max(MINIMO_POR_TEMPORADA,
                                 TAMANHO_ALVO - len(clube.jogadores))))


def posicao_carente(clube, rng):
    """A posição com o maior déficit em relação à composição ideal (empate
    decidido na sorte)."""
    deficit = {
        pos: ideal - sum(1 for j in clube.jogadores if j.posicao == pos)
        for pos, ideal in COMPOSICAO_IDEAL.items()
    }
    maior = max(deficit.values())
    return rng.choice([pos for pos, d in deficit.items() if d == maior])


def gerar_nome(proibidos, rng):
    """Nome que ainda não existe (`proibidos` é atualizado). Sorteia; se a
    sorte não acha, percorre as combinações; esgotadas, numera ("Jr.", "II").
    """
    for _ in range(50):
        nome = f"{rng.choice(NOMES)} {rng.choice(SOBRENOMES)}"
        if nome not in proibidos:
            proibidos.add(nome)
            return nome
    for sufixo in ("", " Jr.", " II", " III", " IV"):
        for n, s in product(NOMES, SOBRENOMES):
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
    return Jogador(
        gerar_nome(proibidos, rng),
        rng.randint(IDADE_MIN, IDADE_MAX),
        posicao_carente(clube, rng),
        overall,
        potencial=potencial,
        contrato_anos=mercado.CONTRATO_PADRAO_ANOS,
    )


def subir_jovens(campeonato, nomes_usados, rng):
    """Cada clube sobe seus jovens (ver `quantos_sobem`). `nomes_usados`: os
    nomes que não podem se repetir (seed + quem já passou pela carreira).
    Devolve os movimentos (`subiu_da_base`)."""

    proibidos = set(nomes_usados) | {
        j.nome for c in campeonato.clubes for j in c.jogadores
    }
    movimentos = []
    for clube in campeonato.clubes:
        for _ in range(quantos_sobem(clube)):
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
