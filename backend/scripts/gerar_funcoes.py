"""Dá a cada jogador da seed a posição específica (v1.3) e, às vezes,
posições secundárias. Lê e regrava data/seeds/jogadores.json.

Separado do gerar_dados.py porque a seed já foi editada depois de gerada
(identidade dos clubes): rodar o gerador inteiro de novo desfaria isso.

Os titulares da seed viram 2 ZAG, 2 LAT, 1 VOL, 2 MEI, 2 PON e 1 CA (o
4-3-3, formação padrão de todo clube). Os reservas completam primeiro o
MINIMO de cada posição — o que a formação mais exigente pede, então todo
elenco cabe em qualquer formação (posicoes.VAGAS) sem improvisar — e depois
seguem o molde.

Uso (a partir da pasta backend/):
    python -m scripts.gerar_funcoes
"""

import json
import random
from pathlib import Path

SEEDS_DIR = Path(__file__).resolve().parent.parent / "data" / "seeds"

# reprodutível: rodar de novo dá exatamente as mesmas posições
rng = random.Random(2028)

# {grupo: {setor: posições a distribuir}}
MOLDE = {
    "titulares": {
        "Goleiro": ["Goleiro"],
        "Defesa": ["Zagueiro", "Zagueiro", "Lateral", "Lateral"],
        "Meio-Campo": ["Volante", "Meia", "Meia"],
        "Atacante": ["Ponta", "Ponta", "Centroavante"],
    },
    "reservas": {
        "Goleiro": ["Goleiro"],
        "Defesa": ["Zagueiro", "Lateral"],
        "Meio-Campo": ["Volante", "Meia"],
        "Atacante": ["Ponta", "Centroavante"],
    },
}

# o máximo que alguma formação pede de cada posição
MINIMO = {
    "Goleiro": 1, "Zagueiro": 3, "Lateral": 2, "Volante": 2, "Meia": 3,
    "Ponta": 2, "Centroavante": 2,
}

# secundárias possíveis: as vizinhas em campo
VIZINHAS = {
    "Zagueiro": ["Lateral", "Volante"],
    "Lateral": ["Zagueiro", "Ponta", "Meia"],
    "Volante": ["Zagueiro", "Meia"],
    "Meia": ["Volante", "Ponta", "Centroavante"],
    "Ponta": ["Meia", "Centroavante", "Lateral"],
    "Centroavante": ["Ponta", "Meia"],
}
CHANCE_UMA = 0.30
CHANCE_DUAS = 0.08


def secundarias(funcao):
    if funcao == "Goleiro":
        return []
    sorte = rng.random()
    quantas = 2 if sorte < CHANCE_DUAS else 1 if sorte < CHANCE_UMA + CHANCE_DUAS else 0
    return sorted(rng.sample(VIZINHAS[funcao], quantas))


def main():
    with open(SEEDS_DIR / "jogadores.json", encoding="utf-8") as f:
        jogadores = json.load(f)
    with open(SEEDS_DIR / "clubes.json", encoding="utf-8") as f:
        clubes = json.load(f)

    por_id = {j["id"]: j for j in jogadores}

    for clube in clubes:
        ja_tem = {}
        for grupo, molde in MOLDE.items():
            elenco = [por_id[i] for i in clube[grupo]]
            for setor, funcoes in molde.items():
                do_setor = [j for j in elenco if j["posicao"] == setor]
                # o que falta para o mínimo vem antes do molde (só nos
                # reservas: entre os titulares, o molde já é o 4-3-3)
                falta = [
                    f for f in dict.fromkeys(funcoes)
                    for _ in range(MINIMO[f] - ja_tem.get(f, 0))
                ] if grupo == "reservas" else []
                rng.shuffle(falta)
                resto = funcoes[:]
                rng.shuffle(resto)
                fila = falta + resto
                # setor com gente a mais: repete o molde
                for k, j in enumerate(do_setor):
                    j["funcao"] = fila[k % len(fila)]
                    ja_tem[j["funcao"]] = ja_tem.get(j["funcao"], 0) + 1

    for j in jogadores:
        j["secundarias"] = secundarias(j["funcao"])

    with open(SEEDS_DIR / "jogadores.json", "w", encoding="utf-8") as f:
        json.dump(jogadores, f, ensure_ascii=False, indent=4)
        f.write("\n")


if __name__ == "__main__":
    main()
