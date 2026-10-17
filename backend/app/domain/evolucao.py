"""Envelhecimento e evolução dos jogadores na virada de temporada (v0.8).

Jovens crescem uma fração da margem que falta até o potencial; a partir dos
30 o overall cai. Quem joga mais evolui mais: o jovem esquecido no banco
cresce devagar. Tudo acontece de uma vez, na virada — durante a temporada o
overall não muda.

O potencial não é garantido: a cada virada ele é revisado (tende a cair um
pouco, e cai mais para quem quase não jogou). Sem isso, todo jovem atingia o
teto em 4–5 temporadas e a liga inflava de craques (8 → ~50 jogadores 90+
em 6 temporadas, medido com a seed atual).
"""

OVERALL_MIN = 40
OVERALL_MAX = 99

# idade a partir da qual o jogador só cai (e o potencial acompanha o overall)
IDADE_DECLINIO = 30


def _taxa_crescimento(idade):
    """Fração da margem (potencial − overall) ganha numa temporada."""
    if idade <= 20:
        return 0.35
    if idade <= 23:
        return 0.30
    return 0.25


def _queda(idade):
    """Pontos de overall perdidos numa temporada (idade ≥ 30)."""
    if idade <= 31:
        return 1
    if idade <= 33:
        return 2
    return 3


def _fator_minutos(partidas):
    if partidas >= 25:
        return 1.25
    if partidas < 10:
        return 0.6
    return 1.0


# revisão do potencial a cada temporada: a média é negativa (−1), então o
# teto tende a encolher; o +1 é a surpresa de quem "estourou"
_REVISAO_POTENCIAL = (-3, -2, -1, -1, 0, 0, 1)
PENALIDADE_BANCO = 2   # pontos de potencial a menos para quem jogou < 10


def revisar_potencial(idade, overall, potencial, partidas, rng):
    """Novo potencial de um jovem que ainda tem margem; os demais ficam
    iguais. Nunca abaixo do overall nem acima de 99."""
    if idade >= IDADE_DECLINIO or potencial <= overall:
        return potencial
    potencial += rng.choice(_REVISAO_POTENCIAL)
    if partidas < 10:
        potencial -= PENALIDADE_BANCO
    return max(overall, min(OVERALL_MAX, potencial))


def evoluir(idade, overall, potencial, partidas, rng):
    """Novos (idade, overall, potencial) depois de uma temporada.

    `idade` é a da temporada que acabou; `partidas`, quantas ele jogou nela;
    `rng` é um `random.Random` (ou o módulo `random`) para a sorte (±1).
    """

    potencial = revisar_potencial(idade, overall, potencial, partidas, rng)
    sorte = rng.choice((-1, 0, 0, 1))   # o "0" pesa mais: a regra manda

    if idade < IDADE_DECLINIO:
        margem = max(0, potencial - overall)
        ganho = round(margem * _taxa_crescimento(idade) * _fator_minutos(partidas))
        # a sorte só mexe em quem ainda tem para onde crescer
        novo = overall + (max(0, ganho + sorte) if margem else 0)
        novo = min(novo, potencial)
    else:
        novo = overall - max(0, _queda(idade) + sorte)

    novo = max(OVERALL_MIN, min(OVERALL_MAX, novo))
    nova_idade = idade + 1

    # o potencial nunca fica abaixo do overall; a partir dos 30, acompanha
    if nova_idade >= IDADE_DECLINIO:
        novo_potencial = novo
    else:
        novo_potencial = max(potencial, novo)

    return nova_idade, novo, novo_potencial
