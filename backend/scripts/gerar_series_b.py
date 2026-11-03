"""Gera as seeds das Séries B (v2.5): data/seeds/taldo_b/ (Liga Taldo B,
clubes inventados) e data/seeds/championship/ (Championship 2023/24, os
clubes reais do 1º ao 20º; os jogadores são fictícios). Cada uma com
clubes.json e jogadores.json no formato da Premier.

A força vem da ordem dos clubes: o elenco do 1º gira em torno de
FORCA_TOPO e o do 20º em torno de FORCA_FUNDO — abaixo da Série A (o
lanterna dela fica perto de 73), para que quem sobe sofra e quem cai seja
favorito. Os nomes não repetem os de nenhuma outra seed.

Determinístico: rodar de novo gera os mesmos arquivos.

Uso (a partir da pasta backend/):
    python -m scripts.gerar_series_b
"""

import json
import random
import zlib
from pathlib import Path

from app.domain import livres, posicoes
from app.domain.jogador import Jogador
from scripts.importar_premier import RIVAIS_NA_CHAMPIONSHIP, dar_funcoes, potencial, xi

SEEDS = Path(__file__).resolve().parent.parent / "data" / "seeds"

FORCA_TOPO, FORCA_FUNDO = 72, 65
TETO = 5                      # ninguém passa a força do clube + isto
OVERALL_MIN = 50
CORTE = {"GK": 3, "DF": 7, "MF": 8, "FW": 5}       # 23, como na Premier
TITULARES_DO_SETOR = {"GK": 1, "DF": 4, "MF": 3, "FW": 3}
CHANCE_MULTA = 0.55           # como na Taldo; na Inglaterra não há multa

NOMES_BR = [
    "Alan", "Alex", "Anderson", "André", "Bernardo", "Bruno", "Caio", "Carlos",
    "César", "Cristian", "Daniel", "Danilo", "Diego", "Douglas", "Eduardo",
    "Elias", "Emerson", "Everton", "Fabiano", "Fábio", "Felipe", "Fernando",
    "Gilberto", "Guilherme", "Heitor", "Hugo", "Iago", "Ítalo", "Jean",
    "Jefferson", "Jonas", "Jorge", "José", "Júlio", "Kaique", "Leandro",
    "Léo", "Luciano", "Luís", "Marcelo", "Márcio", "Marcos", "Mateus",
    "Maurício", "Murilo", "Nathan", "Nelson", "Otávio", "Paulo", "Rafael",
    "Renan", "Renato", "Ricardo", "Robson", "Rodrigo", "Rogério", "Samuel",
    "Sérgio", "Thales", "Tiago", "Ulisses", "Vagner", "Valdir", "Wallace",
    "Washington", "Wellington", "Willian", "Yago", "Yuri", "Zeca",
]
SOBRENOMES_BR = [
    "Alves", "Amaral", "Andrade", "Antunes", "Aragão", "Arruda", "Azevedo",
    "Bastos", "Batista", "Bezerra", "Brandão", "Brito", "Cabral", "Caldeira",
    "Campos", "Cardoso", "Carneiro", "Castro", "Cavalcanti", "Coelho",
    "Correia", "Cunha", "Dantas", "Duarte", "Esteves", "Fagundes", "Farias",
    "Figueiredo", "Fonseca", "Freitas", "Galvão", "Garcia", "Godoy",
    "Guimarães", "Leal", "Leite", "Lopes", "Macedo", "Machado", "Magalhães",
    "Matos", "Medeiros", "Meireles", "Mendes", "Menezes", "Miranda",
    "Monteiro", "Moraes", "Moreira", "Moura", "Nogueira", "Novaes", "Pacheco",
    "Paiva", "Peixoto", "Pinheiro", "Pires", "Prado", "Queiroz", "Ramos",
    "Rezende", "Sampaio", "Siqueira", "Soares", "Tavares", "Toledo",
    "Valente", "Vasconcelos", "Viana", "Vieira",
]
NOMES_EN = [
    "Aaron", "Adam", "Alfie", "Ben", "Billy", "Bradley", "Callum", "Charlie",
    "Connor", "Dan", "Danny", "Dean", "Dominic", "Elliot", "Ethan", "Finley",
    "Frankie", "Freddie", "George", "Harrison", "Harry", "Harvey", "Isaac",
    "Jack", "Jacob", "Jake", "James", "Jamie", "Jason", "Joe", "Jordan",
    "Josh", "Kai", "Kieran", "Kyle", "Lewis", "Liam", "Luke", "Mark", "Mason",
    "Matt", "Max", "Michael", "Nathan", "Ollie", "Owen", "Reece", "Rhys",
    "Ricky", "Ryan", "Sam", "Scott", "Sean", "Stuart", "Taylor", "Theo",
    "Tom", "Tyler", "Will", "Zak",
]
SOBRENOMES_EN = [
    "Adams", "Ainsworth", "Barker", "Barnes", "Bennett", "Bishop", "Bowen",
    "Bradshaw", "Brooks", "Burgess", "Butler", "Carter", "Chapman", "Clayton",
    "Coleman", "Collins", "Cooper", "Crawford", "Dawson", "Dixon", "Doyle",
    "Edwards", "Ellis", "Evans", "Fletcher", "Ford", "Foster", "Gibson",
    "Gordon", "Graham", "Grant", "Gray", "Hall", "Hamilton", "Harper",
    "Harris", "Hayes", "Holmes", "Howard", "Hudson", "Hunt", "Jenkins",
    "Johnson", "Kelly", "Kennedy", "Knight", "Lawrence", "Lloyd", "Marshall",
    "Mason", "Matthews", "Mills", "Mitchell", "Morgan", "Morris", "Murphy",
    "Murray", "Newton", "Owens", "Palmer", "Parker", "Payne", "Pearce",
    "Phillips", "Powell", "Price", "Reid", "Reynolds", "Richards", "Riley",
    "Robinson", "Rogers", "Russell", "Shaw", "Simpson", "Spencer", "Stevens",
    "Stone", "Sutton", "Taylor", "Turner", "Walker", "Wallace", "Ward",
    "Watson", "Webb", "Wells", "West", "Wilkinson", "Wood",
]
NACIONALIDADES_EN = ["ENG"] * 14 + ["SCO", "WAL", "IRL", "NIR"] * 2 + ["FRA", "NED", "JAM", "NGA"]

# nome -> (sigla, cor primária, secundária, camisa, escudo, caixa mi, torcida mi)
CHAMPIONSHIP = {
    "Leicester City": ("LEI", "#003090", "#FDBE11", "lisa", "classico", 6, 0.9),
    "Ipswich Town": ("IPS", "#0044A9", "#FFFFFF", "lisa", "classico", 3, 0.4),
    "Leeds United": ("LEE", "#FFFFFF", "#1D428A", "lisa", "classico", 6, 1.2),
    "Southampton": ("SOU", "#D71920", "#FFFFFF", "listras", "classico", 5, 0.6),
    "West Brom": ("WBA", "#122F67", "#FFFFFF", "listras", "classico", 3, 0.5),
    "Norwich City": ("NOR", "#FFF200", "#00A650", "lisa", "redondo", 3, 0.4),
    "Hull City": ("HUL", "#F5A12D", "#000000", "listras", "moderno", 2, 0.25),
    "Middlesbrough": ("MID", "#E11B22", "#FFFFFF", "lisa", "classico", 3, 0.35),
    "Coventry City": ("COV", "#87CEEB", "#FFFFFF", "lisa", "redondo", 2, 0.3),
    "Preston": ("PNE", "#FFFFFF", "#002D62", "lisa", "classico", 1.5, 0.2),
    "Bristol City": ("BRC", "#E21B23", "#FFFFFF", "lisa", "redondo", 2, 0.25),
    "Cardiff City": ("CAR", "#0070B5", "#FFFFFF", "lisa", "redondo", 2, 0.3),
    "Millwall": ("MIL", "#001D5E", "#FFFFFF", "lisa", "moderno", 1.5, 0.2),
    "Swansea City": ("SWA", "#FFFFFF", "#000000", "lisa", "moderno", 2, 0.3),
    "Watford": ("WAT", "#FBEE23", "#ED2127", "lisa", "moderno", 3, 0.3),
    "Sunderland": ("SUN", "#EB172B", "#FFFFFF", "listras", "classico", 3, 0.8),
    "Stoke City": ("STK", "#E03A3E", "#FFFFFF", "listras", "classico", 3, 0.35),
    "QPR": ("QPR", "#1D5BA4", "#FFFFFF", "aros", "moderno", 2, 0.25),
    "Blackburn Rovers": ("BLB", "#009EE0", "#FFFFFF", "metade", "classico", 2, 0.3),
    "Sheffield Wednesday": ("SHW", "#1F5FAD", "#FFFFFF", "listras", "classico", 2, 0.5),
}
# clássicos dentro da Championship e com clubes da Premier (o par vai nas
# duas seeds; ver RIVAIS_NA_PREMIER)
CLASSICOS_CHAMPIONSHIP = [
    ("Norwich City", "Ipswich Town"),
    ("Cardiff City", "Swansea City"),
    ("Bristol City", "Cardiff City"),
    ("Middlesbrough", "Sunderland"),
    ("Preston", "Blackburn Rovers"),
    ("Leeds United", "Hull City"),
    ("Coventry City", "Leicester City"),
    ("Stoke City", "West Brom"),
    ("Millwall", "QPR"),
    ("Southampton", "Watford"),
]
RIVAIS_NA_PREMIER = RIVAIS_NA_CHAMPIONSHIP   # a lista mora no importador da Premier

# Liga Taldo B, da mais forte para a mais fraca:
# nome -> (sigla, cor primária, secundária, camisa, escudo, caixa mi, torcida mi)
TALDO_B = {
    "Taldo Wanderers": ("TWA", "#5B2C83", "#FFFFFF", "lisa", "classico", 5, 1.4),
    "Taldo Albion": ("TAL", "#0B5394", "#FFFFFF", "listras", "classico", 4, 1.1),
    "Taldo Rovers": ("TRO", "#1E7B3A", "#FFFFFF", "aros", "redondo", 4, 1.0),
    "Olímpico Taldo": ("OLT", "#FFFFFF", "#C9A227", "faixa", "moderno", 4, 0.9),
    "Taldo Town": ("TTO", "#E06666", "#FFFFFF", "lisa", "redondo", 3, 0.8),
    "Racing Taldo": ("RCT", "#6FA8DC", "#FFFFFF", "listras", "classico", 3, 0.8),
    "Taldo County": ("TCO", "#38761D", "#F1C232", "lisa", "classico", 3, 0.6),
    "Taldo Ferroviário": ("TFE", "#CC0000", "#000000", "metade", "classico", 3, 0.7),
    "Operário Taldo": ("OPT", "#000000", "#FFFFFF", "listras", "moderno", 2, 0.6),
    "Taldo Unidos": ("TUN", "#073763", "#E69138", "lisa", "redondo", 2, 0.5),
    "Taldo Atlântico": ("TAT", "#0097A7", "#FFFFFF", "faixa", "moderno", 2, 0.5),
    "Taldo Norte": ("TNO", "#274E13", "#FFFFFF", "lisa", "classico", 2, 0.45),
    "Taldo Sul": ("TSU", "#990000", "#FFD966", "lisa", "classico", 2, 0.45),
    "Taldo Litoral": ("TLI", "#3D85C6", "#FFE599", "listras", "redondo", 2, 0.4),
    "Taldo Serrano": ("TSE", "#783F04", "#FFFFFF", "lisa", "classico", 1.5, 0.3),
    "Taldo Vale": ("TVA", "#6AA84F", "#000000", "metade", "moderno", 1.5, 0.3),
    "Taldo Porto": ("TPO", "#1C4587", "#FFFFFF", "aros", "classico", 1.5, 0.3),
    "Taldo Central": ("TCE", "#B45F06", "#000000", "lisa", "redondo", 1.5, 0.25),
    "Taldo Phoenix": ("TPH", "#E69138", "#990000", "faixa", "moderno", 1, 0.2),
    "Taldo Comets": ("TCM", "#674EA7", "#F1C232", "lisa", "moderno", 1, 0.15),
}
CLASSICOS_TALDO_B = [
    ("Taldo Norte", "Taldo Sul"),
    ("Taldo Ferroviário", "Operário Taldo"),
    ("Taldo Wanderers", "Taldo Rovers"),
    ("Taldo Litoral", "Taldo Porto"),
    ("Taldo Serrano", "Taldo Vale"),
    ("Taldo Albion", "Taldo Town"),
    ("Olímpico Taldo", "Racing Taldo"),
    ("Taldo County", "Taldo Central"),
    ("Taldo Unidos", "Taldo Atlântico"),
    ("Taldo Phoenix", "Taldo Comets"),
]

# id do primeiro jogador de cada seed (Taldo ~1–500, Premier 10 001+)
LIGAS = {
    "taldo_b": dict(pasta="taldo_b", clubes=TALDO_B, classicos=CLASSICOS_TALDO_B,
                    pais="Taldo", primeiro_id=20_001, nomes=(NOMES_BR, SOBRENOMES_BR),
                    multa=True, ingles=False),
    "championship": dict(pasta="championship", clubes=CHAMPIONSHIP,
                         classicos=CLASSICOS_CHAMPIONSHIP + RIVAIS_NA_PREMIER,
                         pais="Inglaterra", primeiro_id=30_001,
                         nomes=(NOMES_EN, SOBRENOMES_EN), multa=False, ingles=True),
}


def _rng(chave):
    return random.Random(zlib.crc32(chave.encode("utf-8")))


def nomes_ocupados():
    """Os nomes de todas as seeds que já existem (Taldo e Premier)."""
    nomes = set()
    for pasta in (SEEDS, SEEDS / "premier"):
        for arquivo in ("jogadores.json", "livres.json"):
            caminho = pasta / arquivo
            if caminho.exists():
                nomes |= {j["nome"] for j in json.loads(caminho.read_text(encoding="utf-8"))}
    return nomes


def _idade(rng):
    faixa = rng.random()
    if faixa < 0.20:
        return rng.randint(17, 20)
    if faixa < 0.80:
        return rng.randint(21, 29)
    return rng.randint(30, 35)


def _ajuste_idade(idade):
    if idade <= 19:
        return -5
    if idade <= 21:
        return -2
    if idade <= 30:
        return 0
    return -1 if idade <= 32 else -3


def _elenco(clube, forca, ocupados, nomes, rng):
    elenco = []
    for setor, quantos in CORTE.items():
        for i in range(quantos):
            idade = _idade(rng)
            titular = i < TITULARES_DO_SETOR[setor]
            valor = forca + (2 if titular else -2) + _ajuste_idade(idade) + rng.gauss(0, 2.5)
            nome = None
            while nome is None or nome in ocupados:
                nome = f"{rng.choice(nomes[0])} {rng.choice(nomes[1])}"
            ocupados.add(nome)
            elenco.append({
                "nome": nome, "idade": idade, "setor": setor,
                "overall": max(OVERALL_MIN, min(forca + TETO, round(valor))),
            })
    for j in elenco:
        j["potencial"] = potencial(j)
    dar_funcoes(elenco)
    return elenco


def _ficha(j, liga, rng):
    funcao = j["funcao"]
    ficha = {
        "nome": j["nome"],
        "idade": j["idade"],
        "posicao": posicoes.SETOR[funcao],
        "overall": j["overall"],
        "potencial": j["potencial"],
        "funcao": funcao,
        "secundarias": livres.secundarias(funcao, _rng(j["nome"] + "/sec")),
        "contrato_anos": rng.randint(1, 2) if j["idade"] >= 32 else rng.randint(1, 5),
        "multa_rescisoria": None,
    }
    if liga["multa"] and rng.random() < CHANCE_MULTA:
        valor = Jogador(ficha["nome"], ficha["idade"], ficha["posicao"], ficha["overall"],
                        potencial=ficha["potencial"]).valor_mercado()
        ficha["multa_rescisoria"] = max(500_000, round(valor * rng.uniform(1.8, 4.0) / 100_000) * 100_000)
    if liga["ingles"]:
        ficha["nacionalidade"] = rng.choice(NACIONALIDADES_EN)
    return ficha


def gerar(id_liga, ocupados):
    liga = LIGAS[id_liga]
    rng = random.Random(f"serie-b:{id_liga}")
    nomes_clubes = list(liga["clubes"])
    passo = (FORCA_TOPO - FORCA_FUNDO) / (len(nomes_clubes) - 1)
    clubes, jogadores = [], []
    proximo = liga["primeiro_id"]
    for i, nome in enumerate(nomes_clubes):
        forca = round(FORCA_TOPO - i * passo)
        elenco = _elenco(nome, forca, ocupados, liga["nomes"], rng)
        titulares = xi(elenco)
        numero = iter(range(1, 99))
        for j in titulares + [j for j in elenco if j not in titulares]:
            j["id"] = proximo
            proximo += 1
            jogadores.append({"id": j["id"], **_ficha(j, liga, rng), "numero": next(numero)})
        sigla, cor1, cor2, camisa, escudo, caixa, torcida = liga["clubes"][nome]
        clubes.append({
            "id": i + 1,
            "nome": nome,
            "pais": liga["pais"],
            "dinheiro": round(caixa * 1_000_000),
            "torcedores": round(torcida * 1_000_000),
            "titulares": [j["id"] for j in titulares],
            "reservas": [j["id"] for j in elenco if j not in titulares],
            "rivais": sorted(b if a == nome else a for a, b in liga["classicos"] if nome in (a, b)),
            "identidade": {"cor_primaria": cor1, "cor_secundaria": cor2,
                           "camisa": camisa, "escudo": escudo, "sigla": sigla},
        })
    return clubes, jogadores


def main():
    ocupados = nomes_ocupados()
    for id_liga, liga in LIGAS.items():
        clubes, jogadores = gerar(id_liga, ocupados)
        destino = SEEDS / liga["pasta"]
        destino.mkdir(parents=True, exist_ok=True)
        for arquivo, dados in (("clubes.json", clubes), ("jogadores.json", jogadores)):
            (destino / arquivo).write_text(json.dumps(dados, ensure_ascii=False, indent=4),
                                           encoding="utf-8")
        por_id = {j["id"]: j for j in jogadores}
        print(f"\n{id_liga}: {len(clubes)} clubes, {len(jogadores)} jogadores")
        for c in clubes:
            xi_ = [por_id[i]["overall"] for i in c["titulares"]]
            print(f"  {c['nome']:22} XI {sum(xi_) / 11:5.1f}  rivais {c['rivais']}")


if __name__ == "__main__":
    main()
