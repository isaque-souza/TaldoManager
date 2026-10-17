"""Gera os arquivos de seed (data/seeds/clubes.json e jogadores.json).

Cada clube tem um TIER que define a faixa de overall do elenco, então a liga
tem uma hierarquia real (times de elite, pelotão do meio, times fracos) em vez
de 20 elencos praticamente iguais.

Uso (a partir da pasta backend/):
    python -m scripts.gerar_dados
"""

import json
import random
from pathlib import Path

from app.domain.jogador import Jogador
from app.domain.nomes import NOMES, SOBRENOMES

# reprodutível: rodar de novo gera exatamente a mesma seed
random.seed(42)

SEEDS_DIR = Path(__file__).resolve().parent.parent / "data" / "seeds"

# tier -> (overall base do elenco, força financeira, lista de clubes)
TIERS = {
    "Elite": (85, 45_000_000, [
        "Taldo City",
        "Real Taldo",
    ]),
    "Forte": (81, 28_000_000, [
        "Sport Taldo",
        "Taldo Internacional",
        "FC Taldo",
        "Taldo Galaxy",
    ]),
    "Médio": (78, 14_000_000, [
        "Taldo United",
        "Atlético Taldo",
        "EC Taldo",
        "Taldo Nacional",
        "Taldo Sporting",
        "Taldo Warriors",
        "Taldo Legends",
        "Taldo Empire",
    ]),
    "Fraco": (76, 6_000_000, [
        "Taldo Rangers",
        "Taldo Athletic",
        "Taldo Stars",
        "Taldo Royals",
    ]),
    "Muito fraco": (73, 2_500_000, [
        "Taldo Dragons",
        "Taldo FC",
    ]),
}

# ordem final dos clubes na seed (mantém a lista original)
CLUBES_ORDEM = [
    "FC Taldo", "Real Taldo", "Taldo United", "Taldo City", "Atlético Taldo",
    "Sport Taldo", "Taldo Internacional", "Taldo Rangers", "Taldo Athletic",
    "EC Taldo", "Taldo Nacional", "Taldo Stars", "Taldo Sporting",
    "Taldo Galaxy", "Taldo Royals", "Taldo Warriors", "Taldo Legends",
    "Taldo Dragons", "Taldo Empire", "Taldo FC",
]

PAISES = [
    "Brasil", "Inglaterra", "Espanha", "Argentina",
    "Itália", "Alemanha", "Portugal", "França",
]

TITULARES = (
    ["Goleiro"] * 1
    + ["Defesa"] * 4
    + ["Meio-Campo"] * 3
    + ["Atacante"] * 3
)

RESERVAS = (
    ["Goleiro"] * 1
    + ["Defesa"] * 2
    + ["Meio-Campo"] * 2
    + ["Atacante"] * 2
)

nomes_usados = set()


def gerar_nome():
    while True:
        nome = f"{random.choice(NOMES)} {random.choice(SOBRENOMES)}"
        if nome not in nomes_usados:
            nomes_usados.add(nome)
            return nome


def gerar_idade():
    faixa = random.random()
    if faixa < 0.20:
        return random.randint(16, 20)
    if faixa < 0.80:
        return random.randint(21, 29)
    return random.randint(30, 37)


def gerar_overall(posicao, base, titular):
    """Overall em torno do `base` do clube. Titulares um pouco acima da média
    do elenco, reservas um pouco abaixo; algum ruído para ter craques e
    jogadores fracos dentro do mesmo time."""

    centro = base + (2 if titular else -3)

    overall = round(random.gauss(centro, 3.2))

    if posicao == "Goleiro":
        overall += random.randint(-2, 2)

    return max(55, min(97, overall))


def tier_do_clube(nome):
    for tier, (base, dinheiro, clubes) in TIERS.items():
        if nome in clubes:
            return tier, base, dinheiro
    raise ValueError(f"Clube sem tier: {nome}")


jogadores = []
clubes = []
id_jogador = 1

for id_clube, nome_clube in enumerate(CLUBES_ORDEM, start=1):

    tier, base, dinheiro_base = tier_do_clube(nome_clube)

    clube = {
        "id": id_clube,
        "nome": nome_clube,
        "pais": random.choice(PAISES),
        "dinheiro": random.randint(
            int(dinheiro_base * 0.6),
            int(dinheiro_base * 1.4),
        ),
        "torcedores": random.randint(
            50_000,
            int(dinheiro_base // 2),
        ),
        "titulares": [],
        "reservas": [],
    }

    for grupo, posicoes in (("titulares", TITULARES), ("reservas", RESERVAS)):
        for posicao in posicoes:
            jogadores.append({
                "id": id_jogador,
                "nome": gerar_nome(),
                "idade": gerar_idade(),
                "posicao": posicao,
                "overall": gerar_overall(
                    posicao, base, titular=(grupo == "titulares")
                ),
            })
            clube[grupo].append(id_jogador)
            id_jogador += 1

    clubes.append(clube)


# jogador especial (easter egg): terceiro reserva do primeiro clube da lista
jogadores[13]["nome"] = "Isaque Souza"
jogadores[13]["idade"] = 18
jogadores[13]["posicao"] = "Meio-Campo"
jogadores[13]["overall"] = 99


# dados de mercado (v0.7). Usam um gerador PRÓPRIO, sorteado depois de tudo:
# se usassem o `random` global dentro do loop acima, cada sorteio a mais
# deslocaria a sequência e mudaria nome/idade/overall de todos os jogadores.
rng_mercado = random.Random(2026)


def gerar_potencial(idade, overall):
    """Teto de overall que o jogador pode alcançar. Jovens têm margem de
    crescimento; a partir dos 30 o potencial é o próprio overall."""

    if idade <= 20:
        margem = rng_mercado.randint(5, 15)
    elif idade <= 24:
        margem = rng_mercado.randint(2, 8)
    elif idade <= 29:
        margem = rng_mercado.randint(0, 3)
    else:
        margem = 0
    return min(99, overall + margem)


def gerar_contrato(idade):
    """Temporadas restantes de contrato. Veteranos assinam por menos tempo."""

    if idade >= 32:
        return rng_mercado.randint(1, 2)
    return rng_mercado.randint(1, 5)


for j in jogadores:
    j["potencial"] = gerar_potencial(j["idade"], j["overall"])
    j["contrato_anos"] = gerar_contrato(j["idade"])


# multa rescisória: valor FIXO de contrato (não acompanha a valorização do
# jogador). Nem todo jogador tem: sem multa, o clube só vende se quiser.
rng_multa = random.Random(2027)
CHANCE_MULTA = 0.55


def gerar_multa(j):
    if rng_multa.random() >= CHANCE_MULTA:
        return None
    valor = Jogador(
        j["nome"], j["idade"], j["posicao"], j["overall"],
        potencial=j["potencial"],
    ).valor_mercado()
    multa = valor * rng_multa.uniform(1.8, 4.0)
    # arredonda para 100 mil (contrato não tem centavos)
    return max(500_000, round(multa / 100_000) * 100_000)


for j in jogadores:
    j["multa_rescisoria"] = gerar_multa(j)


# clássicos: cada clube tem um rival (lista, para no futuro poder ter mais)
CLASSICOS = [
    ("Real Taldo", "Taldo City"),
    ("Sport Taldo", "Taldo Internacional"),
    ("FC Taldo", "Taldo FC"),
    ("Taldo Galaxy", "Taldo Stars"),
    ("Taldo Empire", "Taldo Royals"),
    ("Taldo United", "Atlético Taldo"),
    ("EC Taldo", "Taldo Nacional"),
    ("Taldo Sporting", "Taldo Athletic"),
    ("Taldo Warriors", "Taldo Legends"),
    ("Taldo Dragons", "Taldo Rangers"),
]

for clube in clubes:
    clube["rivais"] = sorted(
        b if a == clube["nome"] else a
        for a, b in CLASSICOS
        if clube["nome"] in (a, b)
    )


SEEDS_DIR.mkdir(parents=True, exist_ok=True)

with open(SEEDS_DIR / "jogadores.json", "w", encoding="utf-8") as f:
    json.dump(jogadores, f, ensure_ascii=False, indent=4)

with open(SEEDS_DIR / "clubes.json", "w", encoding="utf-8") as f:
    json.dump(clubes, f, ensure_ascii=False, indent=4)


print("=" * 48)
print("TALDO MANAGER - GERADOR DE DADOS")
print("=" * 48)
print(f"Clubes: {len(clubes)}  |  Jogadores: {len(jogadores)}")
print("-" * 48)
print(f"{'Clube':22} {'Tier':12} {'Overall XI':>10}")
print("-" * 48)
por_id = {j["id"]: j for j in jogadores}
for clube in clubes:
    tier, _, _ = tier_do_clube(clube["nome"])
    ovs = sorted(
        (por_id[i]["overall"] for i in clube["titulares"]),
        reverse=True,
    )
    media = sum(ovs) / len(ovs)
    print(f"{clube['nome']:22} {tier:12} {media:>10.1f}")
print("=" * 48)
