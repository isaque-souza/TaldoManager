"""Gera data/seeds/livres.json: os jogadores sem clube do começo da
temporada (v1.6). Os perfis e o gerador ficam em app.domain.livres (a
virada da carreira também gera livres).

As posições seguem a proporção de base.COMPOSICAO_IDEAL, então sempre tem
goleiro. Os nomes não repetem nenhum da seed (jogadores.json). Sem contrato
nem multa: quem contrata define o contrato (mercado.contratar_livre).

Uso (a partir da pasta backend/):
    python -m scripts.gerar_livres
"""

import json
import random
from pathlib import Path

from app.domain import base, livres

SEEDS_DIR = Path(__file__).resolve().parent.parent / "data" / "seeds"

# reprodutível: rodar de novo gera exatamente os mesmos livres
rng = random.Random(2030)


def funcoes():
    """livres.QUANTOS posições na proporção da composição ideal do elenco."""
    total = sum(base.COMPOSICAO_IDEAL.values())
    lista = [
        f for f, n in base.COMPOSICAO_IDEAL.items()
        for _ in range(round(livres.QUANTOS * n / total))
    ]
    # o arredondamento pode errar por um ou dois: completa (ou corta) no meio
    while len(lista) < livres.QUANTOS:
        lista.append("Meia central")
    rng.shuffle(lista)
    return lista[:livres.QUANTOS]


def perfis():
    lista = [
        p for p, (fatia, *_) in livres.PERFIS.items()
        for _ in range(round(livres.QUANTOS * fatia))
    ]
    while len(lista) < livres.QUANTOS:
        lista.append("auge")
    rng.shuffle(lista)
    return lista[:livres.QUANTOS]


def main():
    with open(SEEDS_DIR / "jogadores.json", encoding="utf-8") as f:
        nomes = {j["nome"] for j in json.load(f)}

    gerados = [livres.gerar(f, p, nomes, rng) for f, p in zip(funcoes(), perfis())]

    with open(SEEDS_DIR / "livres.json", "w", encoding="utf-8") as f:
        json.dump(gerados, f, ensure_ascii=False, indent=4)

    goleiros = sum(1 for j in gerados if j["funcao"] == "Goleiro")
    print(f"Livres: {len(gerados)}  |  Goleiros: {goleiros}")


if __name__ == "__main__":
    main()
