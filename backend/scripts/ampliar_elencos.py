"""Amplia os elencos da seed de 18 para 23 jogadores (v1.6). Lê e regrava
data/seeds/jogadores.json e clubes.json.

Com 18 jogadores, todo clube tinha exatamente 2 goleiros — o mínimo do
mercado (mercado.GOLEIROS_MIN) —, então nenhum goleiro podia ser vendido.
Cada clube ganha 5 reservas: as posições com o maior déficit em relação a
base.COMPOSICAO_IDEAL (3 goleiros, 4 zagueiros...), o que dá sempre 1 goleiro
e 4 de linha.

O reforço é reserva de verdade: overall em torno da média dos reservas do
clube, um pouco abaixo (o terceiro goleiro, mais abaixo ainda). Potencial,
contrato e multa seguem as regras do gerar_dados.py.

Separado do gerar_dados.py pelo mesmo motivo do gerar_funcoes.py: a seed já
foi editada depois de gerada. Só mexe em clube com menos de 23 jogadores,
então rodar de novo não muda nada.

Uso (a partir da pasta backend/):
    python -m scripts.ampliar_elencos
"""

import json
import random
from pathlib import Path

from app.domain import base, posicoes
from app.domain.jogador import Jogador

SEEDS_DIR = Path(__file__).resolve().parent.parent / "data" / "seeds"

# reprodutível: rodar de novo (numa seed de 18) dá os mesmos reforços
rng = random.Random(2029)

DESCONTO_RESERVA = 2          # abaixo da média dos reservas do clube
DESCONTO_TERCEIRO_GOLEIRO = 4
DESVIO_OVERALL = 3
OVERALL_MIN, OVERALL_MAX = 55, 97
CHANCE_MULTA = 0.55
VIZINHAS = {
    "Zagueiro": ["Lateral", "Volante"],
    "Lateral": ["Zagueiro", "Ponta", "Meia central"],
    "Volante": ["Zagueiro", "Meia central"],
    "Meia central": ["Volante", "Meia-atacante", "Ponta"],
    "Meia-atacante": ["Meia central", "Segundo atacante", "Ponta"],
    "Ponta": ["Meia-atacante", "Lateral", "Centroavante"],
    "Segundo atacante": ["Meia-atacante", "Centroavante"],
    "Centroavante": ["Segundo atacante", "Ponta"],
}


def posicao_carente(elenco):
    """A posição com o maior déficit (empate decidido na sorte)."""
    deficit = {
        f: ideal - sum(1 for j in elenco if j["funcao"] == f)
        for f, ideal in base.COMPOSICAO_IDEAL.items()
    }
    maior = max(deficit.values())
    return rng.choice([f for f, d in deficit.items() if d == maior])


def gerar_idade():
    faixa = rng.random()
    if faixa < 0.30:
        return rng.randint(17, 20)
    if faixa < 0.85:
        return rng.randint(21, 29)
    return rng.randint(30, 35)


def gerar_potencial(idade, overall):
    if idade <= 20:
        margem = rng.randint(5, 15)
    elif idade <= 24:
        margem = rng.randint(2, 8)
    elif idade <= 29:
        margem = rng.randint(0, 3)
    else:
        margem = 0
    return min(99, overall + margem)


def gerar_contrato(idade):
    return rng.randint(1, 2) if idade >= 32 else rng.randint(1, 5)


def gerar_multa(j):
    if rng.random() >= CHANCE_MULTA:
        return None
    valor = Jogador(
        j["nome"], j["idade"], j["posicao"], j["overall"],
        potencial=j["potencial"],
    ).valor_mercado()
    multa = valor * rng.uniform(1.8, 4.0)
    return max(500_000, round(multa / 100_000) * 100_000)


def secundarias(funcao):
    if funcao == "Goleiro":
        return []
    sorte = rng.random()
    quantas = 2 if sorte < 0.08 else 1 if sorte < 0.38 else 0
    return sorted(rng.sample(VIZINHAS[funcao], quantas))


def reforco(id_jogador, elenco, media_reservas, nomes):
    funcao = posicao_carente(elenco)
    goleiros = sum(1 for j in elenco if j["funcao"] == "Goleiro")
    desconto = DESCONTO_TERCEIRO_GOLEIRO if funcao == "Goleiro" and goleiros >= 2 \
        else DESCONTO_RESERVA
    overall = round(rng.gauss(media_reservas - desconto, DESVIO_OVERALL))
    idade = gerar_idade()
    j = {
        "id": id_jogador,
        "nome": base.gerar_nome(nomes, rng),
        "idade": idade,
        "posicao": posicoes.SETOR[funcao],
        "overall": max(OVERALL_MIN, min(OVERALL_MAX, overall)),
    }
    j["potencial"] = gerar_potencial(idade, j["overall"])
    j["contrato_anos"] = gerar_contrato(idade)
    j["multa_rescisoria"] = gerar_multa(j)
    j["funcao"] = funcao
    j["secundarias"] = secundarias(funcao)
    return j


def main():
    with open(SEEDS_DIR / "jogadores.json", encoding="utf-8") as f:
        jogadores = json.load(f)
    with open(SEEDS_DIR / "clubes.json", encoding="utf-8") as f:
        clubes = json.load(f)

    por_id = {j["id"]: j for j in jogadores}
    nomes = {j["nome"] for j in jogadores}
    proximo_id = max(por_id) + 1

    for clube in clubes:
        elenco = [por_id[i] for i in clube["titulares"] + clube["reservas"]]
        reservas = [por_id[i] for i in clube["reservas"]]
        media_reservas = sum(j["overall"] for j in reservas) / len(reservas)
        while len(elenco) < base.TAMANHO_ALVO:
            j = reforco(proximo_id, elenco, media_reservas, nomes)
            jogadores.append(j)
            elenco.append(j)
            clube["reservas"].append(j["id"])
            proximo_id += 1

    with open(SEEDS_DIR / "jogadores.json", "w", encoding="utf-8") as f:
        json.dump(jogadores, f, ensure_ascii=False, indent=4)
    with open(SEEDS_DIR / "clubes.json", "w", encoding="utf-8") as f:
        json.dump(clubes, f, ensure_ascii=False, indent=4)

    print(f"Clubes: {len(clubes)}  |  Jogadores: {len(jogadores)}")


if __name__ == "__main__":
    main()
