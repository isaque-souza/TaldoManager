"""Gera data/seeds/livres.json: os jogadores sem clube do começo da
temporada (v1.6).

São 50, como os que sobram no mercado de verdade: veteranos ainda bons que
ninguém renovou, jogadores comuns no auge e jovens que não vingaram onde
estavam. As posições seguem a proporção de base.COMPOSICAO_IDEAL, então
sempre tem goleiro. O nível fica na faixa dos reservas da liga — livre bom
demais esvaziaria o mercado entre os clubes.

Os nomes não repetem nenhum da seed (jogadores.json). Sem contrato nem
multa: quem contrata define o contrato (mercado.contratar_livre).

Uso (a partir da pasta backend/):
    python -m scripts.gerar_livres
"""

import json
import random
from pathlib import Path

from app.domain import base, posicoes
from scripts.ampliar_elencos import VIZINHAS

SEEDS_DIR = Path(__file__).resolve().parent.parent / "data" / "seeds"

# reprodutível: rodar de novo gera exatamente os mesmos livres
rng = random.Random(2030)

QUANTOS = 50

# perfil -> (fatia dos livres, idades, overall, margem de potencial)
PERFIS = {
    "veterano": (0.30, (30, 35), (70, 80), (0, 0)),
    "auge": (0.45, (23, 29), (64, 76), (0, 4)),
    "jovem": (0.25, (17, 21), (58, 68), (8, 20)),
}


def funcoes():
    """QUANTOS posições na proporção da composição ideal do elenco."""
    total = sum(base.COMPOSICAO_IDEAL.values())
    lista = [
        f for f, n in base.COMPOSICAO_IDEAL.items()
        for _ in range(round(QUANTOS * n / total))
    ]
    # o arredondamento pode errar por um ou dois: completa (ou corta) no meio
    while len(lista) < QUANTOS:
        lista.append("Meia central")
    rng.shuffle(lista)
    return lista[:QUANTOS]


def perfis():
    lista = [
        p for p, (fatia, *_) in PERFIS.items()
        for _ in range(round(QUANTOS * fatia))
    ]
    while len(lista) < QUANTOS:
        lista.append("auge")
    rng.shuffle(lista)
    return lista[:QUANTOS]


def secundarias(funcao):
    if funcao == "Goleiro":
        return []
    sorte = rng.random()
    quantas = 2 if sorte < 0.08 else 1 if sorte < 0.38 else 0
    return sorted(rng.sample(VIZINHAS[funcao], quantas))


def livre(funcao, perfil, nomes):
    _, idades, overalls, margem = PERFIS[perfil]
    overall = rng.randint(*overalls)
    return {
        "nome": base.gerar_nome(nomes, rng),
        "idade": rng.randint(*idades),
        "posicao": posicoes.SETOR[funcao],
        "overall": overall,
        "potencial": min(99, overall + rng.randint(*margem)),
        "funcao": funcao,
        "secundarias": secundarias(funcao),
    }


def main():
    with open(SEEDS_DIR / "jogadores.json", encoding="utf-8") as f:
        nomes = {j["nome"] for j in json.load(f)}

    livres = [livre(f, p, nomes) for f, p in zip(funcoes(), perfis())]

    with open(SEEDS_DIR / "livres.json", "w", encoding="utf-8") as f:
        json.dump(livres, f, ensure_ascii=False, indent=4)

    goleiros = sum(1 for j in livres if j["funcao"] == "Goleiro")
    print(f"Livres: {len(livres)}  |  Goleiros: {goleiros}")


if __name__ == "__main__":
    main()
