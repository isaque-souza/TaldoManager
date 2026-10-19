"""Importa a Premier League 2023/24 do OpenFootball (v1.6) e gera a seed da
segunda liga em data/seeds/premier/ (clubes.json, jogadores.json e
livres.json, no formato da liga Taldo).

Lê só do disco (data/fontes/openfootball/premier-2023-24/, baixados por
scripts/baixar_openfootball.py) e é determinístico: rodar de novo gera os
mesmos arquivos.

O OpenFootball dá número, nome, nacionalidade, setor (GK/DF/MF/FW) e ano de
nascimento — e lista a base inteira (30 a 74 nomes por clube). O resto é
calculado aqui:

- elenco: 23, cortados por setor (CORTE). Antes vem quem parece do time
  principal (camisa até 40 ou 22+ anos; a camisa sozinha não basta: o Foden
  usa a 47); a base só completa;
- overall: a força do clube (a posição na tabela de 23/24, calculada dos 380
  jogos) ajustada pela camisa e pela idade, com um ruído fixo por nome e um
  teto (acima dele, só as estrelas);
- posição específica: a que mais falta no elenco (base.COMPOSICAO_IDEAL)
  entre as possíveis do setor;
- estrelas: data/fontes/estrelas-premier.json corrige overall, potencial e
  posição à mão (e garante a vaga no elenco);
- livres: os melhores de quem é do time principal e sobrou no corte;
- nomes: o jogo identifica o jogador pelo nome, então quem tem o nome de um
  jogador (fictício) da liga Taldo ganha a nacionalidade: "João Gomes (BRA)".

Uso (a partir da pasta backend/):
    python -m scripts.importar_premier
"""

import json
import random
import re
import zlib
from pathlib import Path

from app.domain import base, livres, posicoes

DADOS = Path(__file__).resolve().parent.parent / "data"
FONTE = DADOS / "fontes" / "openfootball" / "premier-2023-24"
ESTRELAS = DADOS / "fontes" / "estrelas-premier.json"
DESTINO = DADOS / "seeds" / "premier"

ANO = 2023                    # a temporada começa em agosto de 2023
PRIMEIRO_ID = 10_001          # ids da Taldo vão até ~500: não colidem

# 23 por setor do arquivo (GK/DF/MF/FW); muitos pontas vêm como MF
CORTE = {"GK": 3, "DF": 7, "MF": 8, "FW": 5}
# posições específicas possíveis para cada setor do arquivo
FUNCOES_DO_SETOR = {
    "GK": ("Goleiro",),
    "DF": ("Zagueiro", "Lateral"),
    "MF": ("Volante", "Meia central", "Meia-atacante", "Ponta"),
    "FW": ("Centroavante", "Segundo atacante", "Ponta"),
}

# o titular comum (quem não está em estrelas-premier.json): ~82 no campeão,
# ~72 no lanterna, nunca mais que TETO acima disso — acima, só as estrelas.
# Com elas, o XI vai de ~74 a ~87 (o da Taldo, de ~73 a ~88)
OVERALL_CAMPEAO, OVERALL_LANTERNA = 82, 72
TETO = 2
OVERALL_MIN = 50
# perdas de pontos de 2023/24 (Everton −8, Forest −4) — a tabela oficial
DEDUCOES = {"Everton FC": 8, "Nottingham Forest FC": 4}

# nome no arquivo -> (nome no jogo, sigla, cores, camisa, escudo,
#                     caixa em milhões, torcida em milhões)
CLUBES = {
    "Arsenal FC": ("Arsenal", "ARS", "#EF0107", "#FFFFFF", "lisa", "classico", 30, 9.0),
    "Aston Villa FC": ("Aston Villa", "AVL", "#670E36", "#95BFE5", "lisa", "classico", 18, 2.5),
    "AFC Bournemouth": ("Bournemouth", "BOU", "#DA291C", "#000000", "listras", "redondo", 7, 0.4),
    "Brentford FC": ("Brentford", "BRE", "#E30613", "#FFFFFF", "listras", "redondo", 8, 0.5),
    "Brighton & Hove Albion FC": ("Brighton", "BHA", "#0057B8", "#FFFFFF", "listras", "redondo", 12, 1.2),
    "Burnley FC": ("Burnley", "BUR", "#6C1D45", "#99D6EA", "lisa", "classico", 5, 0.5),
    "Chelsea FC": ("Chelsea", "CHE", "#034694", "#FFFFFF", "lisa", "redondo", 28, 8.0),
    "Crystal Palace FC": ("Crystal Palace", "CRY", "#1B458F", "#C4122E", "listras", "moderno", 8, 1.0),
    "Everton FC": ("Everton", "EVE", "#003399", "#FFFFFF", "lisa", "classico", 8, 3.0),
    "Fulham FC": ("Fulham", "FUL", "#FFFFFF", "#000000", "lisa", "moderno", 9, 0.8),
    "Liverpool FC": ("Liverpool", "LIV", "#C8102E", "#F6EB61", "lisa", "classico", 32, 11.0),
    "Luton Town FC": ("Luton Town", "LUT", "#F78F1E", "#002D62", "lisa", "redondo", 3, 0.25),
    "Manchester City FC": ("Manchester City", "MCI", "#6CABDD", "#FFFFFF", "lisa", "redondo", 35, 7.0),
    "Manchester United FC": ("Manchester United", "MUN", "#DA291C", "#000000", "lisa", "classico", 30, 12.0),
    "Newcastle United FC": ("Newcastle", "NEW", "#241F20", "#FFFFFF", "listras", "classico", 25, 4.0),
    "Nottingham Forest FC": ("Nottingham Forest", "NFO", "#DD0000", "#FFFFFF", "lisa", "moderno", 7, 1.2),
    "Sheffield United FC": ("Sheffield United", "SHU", "#EE2737", "#FFFFFF", "listras", "classico", 5, 0.8),
    "Tottenham Hotspur FC": ("Tottenham", "TOT", "#FFFFFF", "#132257", "lisa", "moderno", 22, 5.0),
    "West Ham United FC": ("West Ham", "WHU", "#7A263A", "#1BB1E7", "lisa", "classico", 14, 2.5),
    "Wolverhampton Wanderers FC": ("Wolves", "WOL", "#FDB913", "#231F20", "lisa", "moderno", 9, 1.2),
}

CLASSICOS = [
    ("Arsenal", "Tottenham"),
    ("Liverpool", "Everton"),
    ("Manchester City", "Manchester United"),
    ("Liverpool", "Manchester United"),
    ("Chelsea", "Tottenham"),
    ("Aston Villa", "Wolves"),
    ("Crystal Palace", "Brighton"),
    ("Brentford", "Fulham"),
    ("West Ham", "Chelsea"),
]

_LINHA_ELENCO = re.compile(
    r"^\s*(\d+)?\s*,\s*(.+?)(?:\s+\(([A-Z]{3})\))?\s*,\s*(GK|DF|MF|FW)\s*,"
    r"\s*b\.\s*(\d{4}|\?{4})\s*,"
)
_LINHA_JOGO = re.compile(
    r"^\s*(?:\d{1,2}:\d{2})?\s+(.+?)\s{2,}(\d+)-(\d+)(?:\s+\([^)]*\))?\s{2,}(.+?)\s*$"
)


# ---------------------------------------------------------------------------
# leitura
# ---------------------------------------------------------------------------

def ler_elenco(caminho):
    """(nome do clube no arquivo, [jogadores])."""
    linhas = caminho.read_text(encoding="utf-8").splitlines()
    clube = linhas[0].lstrip("= ").split(" - ")[0].strip()
    jogadores = []
    for linha in linhas[1:]:
        m = _LINHA_ELENCO.match(linha)
        if not m:
            continue
        numero, nome, pais, setor, ano = m.groups()
        jogadores.append({
            "numero": int(numero) if numero else None,
            "nome": nome.strip(),
            "nacionalidade": pais or "ENG",
            "setor": setor,
            # sem ano (????): só aparece na base
            "idade": ANO - int(ano) if ano.isdigit() else 18,
        })
    return clube, jogadores


def classificacao(caminho):
    """Nomes dos clubes do 1º ao 20º, pelos pontos (com as deduções) e o
    saldo de gols."""
    pontos, saldo = {}, {}
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        m = _LINHA_JOGO.match(linha)
        if not m:
            continue
        casa, gc, gf, fora = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)
        for clube, pro, contra in ((casa, gc, gf), (fora, gf, gc)):
            pontos[clube] = pontos.get(clube, 0) + (3 if pro > contra else pro == contra)
            saldo[clube] = saldo.get(clube, 0) + pro - contra
    for clube, menos in DEDUCOES.items():
        pontos[clube] -= menos
    return sorted(pontos, key=lambda c: (-pontos[c], -saldo[c]))


# ---------------------------------------------------------------------------
# cálculo
# ---------------------------------------------------------------------------

def _rng(nome):
    """Sorte fixa por jogador: reimportar não muda ninguém."""
    return random.Random(zlib.crc32(nome.encode("utf-8")))


def do_time_principal(j):
    return (j["numero"] or 99) <= 40 or j["idade"] >= 22


def cortar(jogadores, estrelas):
    """Os 23 do elenco e quem sobrou do time principal (os livres)."""
    elenco, sobras = [], []
    for setor, quantos in CORTE.items():
        do_setor = sorted(
            (j for j in jogadores if j["setor"] == setor),
            key=lambda j: (j["nome"] not in estrelas, not do_time_principal(j),
                           j["numero"] or 99),
        )
        elenco += do_setor[:quantos]
        sobras += [j for j in do_setor[quantos:] if do_time_principal(j)]
    return elenco, sobras


def _ajuste_idade(idade):
    if idade <= 19:
        return -6
    if idade <= 21:
        return -3
    if idade <= 23:
        return -1
    if idade <= 30:
        return 0
    return -1 if idade <= 32 else -3


def _ajuste_numero(numero):
    if numero is None or numero > 40:
        return -4
    if numero <= 11:
        return 2
    return 0 if numero <= 23 else -2


def overall(j, forca):
    rng = _rng(j["nome"])
    valor = forca + _ajuste_numero(j["numero"]) + _ajuste_idade(j["idade"])
    return max(OVERALL_MIN, min(round(forca) + TETO, round(valor + rng.gauss(0, 2))))


def potencial(j):
    rng = _rng(j["nome"] + "/potencial")
    idade, ovr = j["idade"], j["overall"]
    if idade <= 20:
        margem = rng.randint(5, 15)
    elif idade <= 24:
        margem = rng.randint(2, 8)
    elif idade <= 29:
        margem = rng.randint(0, 3)
    else:
        margem = 0
    return min(99, ovr + margem)


def dar_funcoes(elenco):
    """Posição específica: a da estrela, ou a que mais falta no elenco entre
    as do setor (do melhor para o pior)."""
    conta = {f: 0 for f in base.COMPOSICAO_IDEAL}
    for j in elenco:
        if j.get("funcao"):
            conta[j["funcao"]] += 1
    for j in sorted(elenco, key=lambda j: -j["overall"]):
        if j.get("funcao"):
            continue
        j["funcao"] = max(
            FUNCOES_DO_SETOR[j["setor"]],
            key=lambda f: base.COMPOSICAO_IDEAL[f] - conta[f],
        )
        conta[j["funcao"]] += 1


def xi(elenco):
    """Os titulares no 4-3-3: para cada vaga, quem rende mais nela (o
    overall menos a perda fora da posição, como no motor). As vagas mais
    raras escolhem primeiro."""
    vagas = sorted(posicoes.vagas("4-3-3"),
                   key=lambda v: sum(1 for j in elenco if j["funcao"] == v))
    titulares = []
    for vaga in vagas:
        titulares.append(max(
            (j for j in elenco if j not in titulares),
            key=lambda j: j["overall"] - posicoes.perda(j["funcao"], vaga),
        ))
    return titulares


def nomes_da_taldo():
    nomes = set()
    for arquivo in ("jogadores.json", "livres.json"):
        caminho = DADOS / "seeds" / arquivo
        if caminho.exists():
            nomes |= {j["nome"] for j in json.loads(caminho.read_text(encoding="utf-8"))}
    return nomes


def _ficha(j, ocupados=frozenset()):
    """O jogador no formato da seed (sem id). `ocupados`: nomes da Taldo."""
    rng = _rng(j["nome"] + "/contrato")
    funcao = j["funcao"]
    nome = j["nome"]
    if nome in ocupados:
        nome = f"{nome} ({j['nacionalidade']})"
    return {
        "nome": nome,
        "idade": j["idade"],
        "posicao": posicoes.SETOR[funcao],
        "overall": j["overall"],
        "potencial": j["potencial"],
        "funcao": funcao,
        "secundarias": livres.secundarias(funcao, _rng(j["nome"] + "/sec")),
        "contrato_anos": rng.randint(1, 2) if j["idade"] >= 32 else rng.randint(1, 5),
        "multa_rescisoria": None,      # sem multa na Inglaterra
        "numero": j["numero"],
        "nacionalidade": j["nacionalidade"],
    }


def importar():
    """Monta (clubes, jogadores, livres) da seed."""
    estrelas = {
        n: e for n, e in json.loads(ESTRELAS.read_text(encoding="utf-8")).items()
        if not n.startswith("_")
    }
    tabela = classificacao(FONTE / "1-premierleague.txt")
    ocupados = nomes_da_taldo()
    passo = (OVERALL_CAMPEAO - OVERALL_LANTERNA) / (len(tabela) - 1)

    elencos = {}
    for caminho in sorted((FONTE / "squads").glob("*.txt")):
        nome, jogadores = ler_elenco(caminho)
        elencos[nome] = jogadores

    clubes, jogadores, sobras_todas = [], [], []
    proximo_id = PRIMEIRO_ID
    for id_clube, nome in enumerate(sorted(elencos, key=tabela.index), start=1):
        forca = OVERALL_CAMPEAO - tabela.index(nome) * passo
        elenco, sobras = cortar(elencos[nome], estrelas)
        for j in elenco + sobras:
            j["overall"] = overall(j, forca)
            j["potencial"] = potencial(j)
            j.update(estrelas.get(j["nome"], {}))
        dar_funcoes(elenco)
        dar_funcoes(sobras)
        sobras_todas += sobras

        titulares = xi(elenco)
        for j in titulares + [j for j in elenco if j not in titulares]:
            j["id"] = proximo_id
            proximo_id += 1
            jogadores.append({"id": j["id"], **_ficha(j, ocupados)})

        jogo, sigla, cor1, cor2, camisa, escudo, caixa, torcida = CLUBES[nome]
        clubes.append({
            "id": id_clube,
            "nome": jogo,
            "pais": "Inglaterra",
            "dinheiro": caixa * 1_000_000,
            "torcedores": round(torcida * 1_000_000),
            "titulares": [j["id"] for j in titulares],
            "reservas": [j["id"] for j in elenco if j not in titulares],
            "rivais": sorted(
                b if a == jogo else a for a, b in CLASSICOS if jogo in (a, b)
            ),
            "identidade": {
                "cor_primaria": cor1, "cor_secundaria": cor2,
                "camisa": camisa, "escudo": escudo, "sigla": sigla,
            },
            "posicao_2023_24": tabela.index(nome) + 1,
        })

    # livres: as melhores sobras (livres.QUANTOS), sem os campos de
    # contrato (quem contrata define)
    livres_seed = [
        {k: v for k, v in _ficha(j, ocupados).items()
         if k not in ("contrato_anos", "multa_rescisoria")}
        for j in sorted(sobras_todas, key=lambda j: (-j["overall"], j["nome"]))
    ][:livres.QUANTOS]
    return clubes, jogadores, livres_seed


def main():
    clubes, jogadores, livres_seed = importar()
    DESTINO.mkdir(parents=True, exist_ok=True)
    for arquivo, dados in (("clubes.json", clubes), ("jogadores.json", jogadores),
                           ("livres.json", livres_seed)):
        with open(DESTINO / arquivo, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=4)

    por_id = {j["id"]: j for j in jogadores}
    print(f"Clubes: {len(clubes)}  |  Jogadores: {len(jogadores)}  |  Livres: {len(livres_seed)}")
    print(f"{'Pos':>3} {'Clube':20} {'XI':>5} {'Elenco':>6}")
    for c in clubes:
        xi_ = [por_id[i]["overall"] for i in c["titulares"]]
        todos = xi_ + [por_id[i]["overall"] for i in c["reservas"]]
        print(f"{c['posicao_2023_24']:>3} {c['nome']:20} {sum(xi_) / 11:>5.1f} "
              f"{sum(todos) / len(todos):>6.1f}")


if __name__ == "__main__":
    main()
