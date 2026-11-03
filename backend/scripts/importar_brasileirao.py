"""Importa o Brasileirão 2017 (v2.5) — o ano do hepta do Corinthians — e
gera a seed em data/seeds/brasileirao/ (clubes.json, jogadores.json e
livres.json, no formato da Premier).

Lê só do disco: os elencos de data/fontes/wikipedia/brasileirao-2017/
(baixados por scripts/baixar_brasileirao.py) e o ajuste manual de
data/fontes/estrelas-brasileirao.json. Determinístico.

Como na Premier (scripts/importar_premier.py):
- elenco: 23, cortados por setor; antes, quem parece do time principal
  (camisa até 40 ou 22+ anos) e as estrelas; a base só completa;
- overall: a força do clube (a posição na tabela de 2017) ajustada pela
  camisa e pela idade, com um ruído fixo por nome e um teto — acima dele,
  só as estrelas;
- nomes: o jogo identifica o jogador pelo nome. Quem repete o nome de
  outro (no Brasileirão ou em outra seed) ganha o sobrenome de verdade
  (NOMES_REAIS, do nome completo no Wikidata): "Gabriel Girotto".

Uso (a partir da pasta backend/):
    python -m scripts.importar_brasileirao
"""

import json
from datetime import date
from pathlib import Path

from app.domain import livres
from scripts.importar_premier import (
    CORTE, _ficha, _rng, cortar, dar_funcoes, overall, potencial, xi,
)

DADOS = Path(__file__).resolve().parent.parent / "data"
FONTE = DADOS / "fontes" / "wikipedia" / "brasileirao-2017" / "elencos.json"
ESTRELAS = DADOS / "fontes" / "estrelas-brasileirao.json"
DESTINO = DADOS / "seeds" / "brasileirao"

INICIO = date(2017, 5, 13)    # a 1ª rodada de 2017: a idade é a do começo
PRIMEIRO_ID = 60_001
IDADE_SEM_DATA = 24           # quem não tem nascimento no Wikidata
# o titular comum: ~76 no campeão, ~69 no lanterna (as estrelas, acima)
OVERALL_CAMPEAO, OVERALL_LANTERNA = 76, 69

# nome no jogo -> (sigla, cor primária, secundária, camisa, escudo,
#                  caixa em milhões, torcida em milhões)
CLUBES = {
    "Corinthians": ("COR", "#FFFFFF", "#000000", "lisa", "classico", 12, 11),
    "Palmeiras": ("PAL", "#006437", "#FFFFFF", "lisa", "classico", 15, 6),
    "Santos": ("SAN", "#FFFFFF", "#000000", "lisa", "classico", 6, 2.5),
    "Grêmio": ("GRE", "#0D80BF", "#000000", "listras", "classico", 8, 3.5),
    "Cruzeiro": ("CRU", "#0033A0", "#FFFFFF", "lisa", "classico", 7, 3.5),
    "Flamengo": ("FLA", "#C8102E", "#000000", "aros", "classico", 14, 12),
    "Vasco": ("VAS", "#000000", "#FFFFFF", "faixa", "classico", 5, 4),
    "Chapecoense": ("CHA", "#00843D", "#FFFFFF", "lisa", "redondo", 3, 0.3),
    "Atlético Mineiro": ("CAM", "#000000", "#FFFFFF", "listras", "classico", 8, 3),
    "Botafogo": ("BOT", "#000000", "#FFFFFF", "listras", "classico", 4, 1.5),
    "Atlético Paranaense": ("CAP", "#C8102E", "#000000", "listras", "moderno", 6, 0.8),
    "Bahia": ("BAH", "#FFFFFF", "#0055A4", "lisa", "redondo", 3, 1.2),
    "São Paulo": ("SAO", "#FFFFFF", "#C8102E", "faixa", "classico", 10, 6),
    "Fluminense": ("FLU", "#8B1A3C", "#00613C", "listras", "classico", 4, 1.5),
    "Sport": ("SPT", "#000000", "#C8102E", "aros", "classico", 3, 1.2),
    "Vitória": ("VIT", "#C8102E", "#000000", "aros", "classico", 2.5, 0.8),
    "Coritiba": ("CFC", "#FFFFFF", "#00543C", "faixa", "classico", 3, 0.6),
    "Avaí": ("AVA", "#0055A4", "#FFFFFF", "listras", "redondo", 2, 0.3),
    "Ponte Preta": ("PON", "#FFFFFF", "#000000", "faixa", "classico", 2, 0.3),
    "Atlético Goianiense": ("ACG", "#C8102E", "#000000", "listras", "moderno", 2, 0.2),
}

# quem repete o nome de outro jogador ganha o sobrenome de verdade (do nome
# completo no Wikidata), não o clube: (clube, nome na fonte) -> nome no jogo
NOMES_REAIS = {
    ("Corinthians", "Gabriel"): "Gabriel Girotto",
    ("Corinthians", "Moisés"): "Moisés Barbosa",
    ("Corinthians", "Danilo"): "Danilo Gabriel",
    ("Palmeiras", "Thiago Santos"): "Thiago dos Santos",
    ("Palmeiras", "Luan"): "Luan Garcia",
    ("Palmeiras", "Willian"): "Willian Siqueira",
    ("Santos", "Lucas Lima"): "Lucas Araújo Lima",
    ("Santos", "Bruno Henrique"): "Bruno Henrique Pinto",
    ("Santos", "Matheus Ribeiro"): "Matheus Antunes",
    ("Santos", "Yuri"): "Yuri Lima",
    ("Santos", "João Paulo"): "João Paulo Martins",
    ("Grêmio", "Jailson"): "Jailson Siqueira",
    ("Cruzeiro", "Robinho"): "Robinho Signorini",
    ("Cruzeiro", "Lucas Silva"): "Lucas Silva Borges",
    ("Flamengo", "Lucas Paquetá"): "Lucas Tolentino",
    ("Flamengo", "Ederson"): "Ederson Honorato",
    ("Flamengo", "Gabriel"): "Gabriel Santana",
    ("Flamengo", "Thiago Santos"): "Thiago Nascimento",
    ("Vasco", "Guilherme"): "Guilherme Costa",
    ("Vasco", "João Pedro"): "João Pedro Borges",
    ("Vasco", "Rafael Marques"): "Rafael Marques Pinto",
    ("Vasco", "Jean"): "Jean Irmer",
    ("Vasco", "Gilberto"): "Gilberto Moraes",
    ("Chapecoense", "Neto"): "Hélio Neto",
    ("Chapecoense", "Elias"): "Elias Curzel",
    ("Chapecoense", "Douglas"): "Douglas Bacelar",
    ("Chapecoense", "João Pedro"): "João Pedro Maturano",
    ("Chapecoense", "Moisés"): "Moisés Wolschick",
    ("Atlético Mineiro", "Luan"): "Luan Madson",
    ("Atlético Mineiro", "Leonardo Silva"): "Léo Silva",
    ("Atlético Mineiro", "Rodrigão"): "Rodrigão Prado",
    ("Botafogo", "Emerson"): "Emerson Santos",
    ("Botafogo", "Guilherme"): "Guilherme Santos",
    ("Atlético Paranaense", "Pablo"): "Pablo Teixeira",
    ("Atlético Paranaense", "Bruno Guimarães"): "Bruno Guimarães Moura",
    ("Atlético Paranaense", "Eduardo"): "Eduardo da Silva",
    ("Bahia", "Jean"): "Jean Fernandes",
    ("Bahia", "Juninho"): "Juninho Valoura",
    ("Bahia", "Anderson"): "Anderson Campos",
    ("São Paulo", "Bruno"): "Bruno Nascimento",
    ("São Paulo", "Lucas Fernandes"): "Lucas Fernandes da Silva",
    ("São Paulo", "Brenner"): "Brenner Souza",
    ("Fluminense", "Léo"): "Léo Pelé",
    ("Fluminense", "Wellington Silva"): "Wellington Alves",
    ("Fluminense", "Henrique"): "Henrique Buss",
    ("Fluminense", "Douglas"): "Douglas Augusto",
    ("Fluminense", "Robinho"): "Robinho Azevedo",
    ("Fluminense", "Renato"): "José Renato",
    ("Fluminense", "Felipe"): "Felipe Sampaio",
    ("Fluminense", "Matheus"): "Matheus Coutinho",
    ("Sport", "Diego Souza"): "Diego Souza Andrade",
    ("Sport", "Lucas Ferreira"): "Lucas Amaral",
    ("Sport", "Marquinhos"): "Marquinhos Gonçalves",
    ("Vitória", "Juninho"): "Juninho Barbosa",
    ("Vitória", "Fred"): "Fred Burgel",
    ("Vitória", "Yago"): "Yago Felipe",
    ("Coritiba", "João Paulo"): "João Paulo da Silva",
    ("Avaí", "Luan"): "Luan Scapolan",
    ("Avaí", "Douglas"): "Douglas Friedrich",
    ("Avaí", "Maicon"): "Maicon Sisenando",
    ("Ponte Preta", "Rodrigo"): "Rodrigo Baldasso",
    ("Ponte Preta", "Jádson"): "Jádson Alves",
    ("Ponte Preta", "Wendel"): "Wendel Maurício",
    ("Ponte Preta", "Emerson"): "Emerson Sheik",
    ("Atlético Goianiense", "Walter"): "Walter Henrique",
    ("Atlético Goianiense", "Jorginho"): "Jorginho Xavier",
    ("Atlético Goianiense", "Igor"): "Igor Machado",
    ("Atlético Goianiense", "Alison"): "Alison Mira",
}

CLASSICOS = [
    ("Corinthians", "Palmeiras"),
    ("Corinthians", "São Paulo"),
    ("Corinthians", "Santos"),
    ("Palmeiras", "São Paulo"),
    ("Palmeiras", "Santos"),
    ("São Paulo", "Santos"),
    ("Flamengo", "Vasco"),
    ("Flamengo", "Fluminense"),
    ("Flamengo", "Botafogo"),
    ("Vasco", "Botafogo"),
    ("Vasco", "Fluminense"),
    ("Fluminense", "Botafogo"),
    ("Cruzeiro", "Atlético Mineiro"),
    ("Atlético Paranaense", "Coritiba"),
    ("Bahia", "Vitória"),
]
# clássicos com a Série B de 2017 (scripts/gerar_ligas.py): o clube daqui
# também lista o rival de lá
RIVAIS_NA_SERIE_B = [
    ("Internacional", "Grêmio"),
    ("América Mineiro", "Atlético Mineiro"),
    ("América Mineiro", "Cruzeiro"),
    ("Náutico", "Sport"),
    ("Santa Cruz", "Sport"),
    ("Figueirense", "Avaí"),
    ("Figueirense", "Chapecoense"),
    ("Guarani", "Ponte Preta"),
    ("Goiás", "Atlético Goianiense"),
    ("Paraná", "Coritiba"),
    ("Paraná", "Atlético Paranaense"),
]


def _idade(nascimento):
    if not nascimento:
        return IDADE_SEM_DATA
    n = date.fromisoformat(nascimento[:4] + "-" + (nascimento[5:7] if nascimento[5:7] != "00" else "07")
                           + "-" + (nascimento[8:10] if nascimento[8:10] != "00" else "01"))
    return INICIO.year - n.year - ((INICIO.month, INICIO.day) < (n.month, n.day))


_PARTICULAS = {"de", "da", "do", "das", "dos", "e"}
_SUFIXOS = {"júnior", "junior", "filho", "neto", "sobrinho"}


def _com_sobrenome(nome, clube, j):
    """Quem repete um nome e não está em NOMES_REAIS (as sobras, que não
    entram na seed): o nome + o último sobrenome do nome completo. Sem nome
    completo (artigo "Fulano (footballer, ...)"), o clube."""
    artigo = j.get("artigo") or ""
    if "(" not in artigo:
        ja = {p.lower() for p in nome.split()}
        for parte in reversed(artigo.split()):
            if parte.lower() not in _PARTICULAS | _SUFIXOS | ja:
                return f"{nome} {parte}"
    return f"{nome} ({clube})"


def _p_sorteio(j):
    return {**j, "nome": j.get("nome_sorteio", j["nome"])}


def nomes_ocupados():
    """Os nomes das outras seeds (o Brasileirão não pode repeti-los)."""
    nomes = set()
    for pasta in (DADOS / "seeds").iterdir():
        if not pasta.is_dir() or pasta == DESTINO:
            continue
        for arquivo in ("jogadores.json", "livres.json"):
            if (pasta / arquivo).exists():
                nomes |= {j["nome"] for j in json.loads((pasta / arquivo).read_text(encoding="utf-8"))}
    for arquivo in ("jogadores.json", "livres.json"):
        caminho = DADOS / "seeds" / arquivo
        if caminho.exists():
            nomes |= {j["nome"] for j in json.loads(caminho.read_text(encoding="utf-8"))}
    return nomes


def importar():
    fonte = json.loads(FONTE.read_text(encoding="utf-8"))["clubes"]
    ajustes = {c: v for c, v in json.loads(ESTRELAS.read_text(encoding="utf-8")).items()
               if not c.startswith("_")}
    ordem = list(CLUBES)
    passo = (OVERALL_CAMPEAO - OVERALL_LANTERNA) / (len(ordem) - 1)

    por_clube = {}
    for posicao, nome in enumerate(ordem):
        ajuste = ajustes.get(nome, {})
        estrelas = {n: e for n, e in ajuste.items() if not n.startswith("_")}
        jogadores = []
        for j in fonte[nome]["jogadores"] + ajuste.get("_acrescentar", []):
            if j["setor"] not in CORTE:
                continue
            jogadores.append({
                "artigo": j.get("artigo"),
                "numero": j.get("numero"),
                "nome": j["nome"],
                "nacionalidade": j.get("nacionalidade") or "Brazil",
                "setor": j["setor"],
                "idade": j["idade"] if "idade" in j else _idade(j.get("nascimento")),
            })
        forca = OVERALL_CAMPEAO - posicao * passo
        elenco, sobras = cortar(jogadores, estrelas)
        for j in elenco + sobras:
            j["overall"] = overall({**j, "nome": f"{nome}/{j['nome']}"}, forca)
            j["potencial"] = potencial({**j, "nome": f"{nome}/{j['nome']}"})
            j.update(estrelas.get(j["nome"], {}))
        dar_funcoes(elenco)
        dar_funcoes(sobras)
        por_clube[nome] = (elenco, sobras)

    # nomes repetidos ganham o sobrenome real (NOMES_REAIS). Entre os do
    # Brasileirão, o melhor fica com o nome; quem repete o de outra seed (que
    # não pode mudar: os saves acham o jogador pelo nome) ganha sempre
    ocupados = nomes_ocupados()
    por_nome = {}
    for clube, (elenco, sobras) in por_clube.items():
        for j in elenco + sobras:
            por_nome.setdefault(j["nome"], []).append((clube, j))
    for nome, donos in por_nome.items():
        if nome not in ocupados and len(donos) == 1:
            continue
        donos.sort(key=lambda d: (-d[1]["overall"], ordem.index(d[0])))
        for i, (clube, j) in enumerate(donos):
            if i > 0 or nome in ocupados:
                # o nome novo só entra na ficha: o sorteio (contrato,
                # secundárias) segue com o nome de antes da v2.5.1, "Gabriel
                # (Corinthians)", para a seed não mudar além do nome
                j["nome_sorteio"] = f"{nome} ({clube})"
                j["nome_jogo"] = NOMES_REAIS.get((clube, nome)) or _com_sobrenome(nome, clube, j)
    finais = [j.get("nome_jogo", j["nome"]) for el, so in por_clube.values() for j in el + so]
    repetidos = {n for n in finais if finais.count(n) > 1 or n in ocupados}
    if repetidos:
        raise SystemExit(f"nomes repetidos: {sorted(repetidos)}")

    clubes, jogadores, sobras_todas = [], [], []
    proximo = PRIMEIRO_ID
    for id_clube, nome in enumerate(ordem, start=1):
        elenco, sobras = por_clube[nome]
        sobras_todas += sobras
        titulares = xi(elenco)
        for j in titulares + [j for j in elenco if j not in titulares]:
            j["id"] = proximo
            proximo += 1
            ficha = {**_ficha(_p_sorteio(j)), "nome": j.get("nome_jogo", j["nome"])}
            ficha["multa_rescisoria"] = None    # quem compra negocia (como na Premier)
            ficha["nacionalidade"] = _sigla_pais(j["nacionalidade"])
            jogadores.append({"id": j["id"], **ficha})
        sigla, cor1, cor2, camisa, escudo, caixa, torcida = CLUBES[nome]
        clubes.append({
            "id": id_clube,
            "nome": nome,
            "pais": "Brasil",
            "dinheiro": round(caixa * 1_000_000),
            "torcedores": round(torcida * 1_000_000),
            "titulares": [j["id"] for j in titulares],
            "reservas": [j["id"] for j in elenco if j not in titulares],
            "rivais": sorted(
                [b if a == nome else a for a, b in CLASSICOS if nome in (a, b)]
                + [a for a, b in RIVAIS_NA_SERIE_B if b == nome]
            ),
            "identidade": {"cor_primaria": cor1, "cor_secundaria": cor2,
                           "camisa": camisa, "escudo": escudo, "sigla": sigla},
            # a posição de 2017, para a copa (como a Premier 23/24)
            "posicao_2023_24": id_clube,
        })

    livres_seed = [
        {k: v for k, v in {**_ficha(_p_sorteio(j)), "nome": j.get("nome_jogo", j["nome"]),
                           "nacionalidade": _sigla_pais(j["nacionalidade"])}.items()
         if k not in ("contrato_anos", "multa_rescisoria")}
        for j in sorted(sobras_todas, key=lambda j: (-j["overall"], _p_sorteio(j)["nome"]))
    ][:livres.QUANTOS]
    return clubes, jogadores, livres_seed


PAISES = {
    "Brazil": "BRA", "Argentina": "ARG", "Paraguay": "PAR", "Uruguay": "URU",
    "Colombia": "COL", "Chile": "CHI", "Peru": "PER", "Ecuador": "ECU",
    "Venezuela": "VEN", "Turkey": "TUR", "Germany": "GER", "Portugal": "POR",
    "Bolivia": "BOL", "Costa Rica": "CRC", "Panama": "PAN", "Angola": "ANG",
}


def _sigla_pais(nome):
    return PAISES.get(nome, nome[:3].upper())


def main():
    clubes, jogadores, livres_seed = importar()
    DESTINO.mkdir(parents=True, exist_ok=True)
    for arquivo, dados in (("clubes.json", clubes), ("jogadores.json", jogadores),
                           ("livres.json", livres_seed)):
        (DESTINO / arquivo).write_text(json.dumps(dados, ensure_ascii=False, indent=4),
                                       encoding="utf-8")
    por_id = {j["id"]: j for j in jogadores}
    print(f"Clubes: {len(clubes)}  |  Jogadores: {len(jogadores)}  |  Livres: {len(livres_seed)}")
    for c in clubes:
        xi_ = [por_id[i] for i in c["titulares"]]
        print(f"{c['id']:>3} {c['nome']:20} XI {sum(j['overall'] for j in xi_) / 11:5.1f}  "
              + ", ".join(f"{j['nome']} {j['overall']}" for j in sorted(xi_, key=lambda j: -j['overall'])[:4]))


if __name__ == "__main__":
    main()
