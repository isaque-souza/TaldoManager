import json
from pathlib import Path

from app.domain import estadio, fama, livres
from app.domain.jogador import Jogador
from app.domain.clube import Clube
from app.domain.campeonato import Campeonato

SEEDS_DIR = Path(__file__).resolve().parent.parent / "data" / "seeds"

# ligas (v1.6): id -> (nome, pasta da seed). A ordem é a das tabelas.
LIGAS = {
    "taldo": ("Liga Taldo", SEEDS_DIR),
    "premier": ("Premier League", SEEDS_DIR / "premier"),
}
LIGA_PADRAO = ("taldo",)   # saves de antes da v1.6


def carregar_jogadores(liga="taldo"):

    with open(
        LIGAS[liga][1] / "jogadores.json",
        encoding="utf-8"
    ) as arquivo:

        dados = json.load(arquivo)

    jogadores = {}

    for j in dados:

        # quem já está na liga começa com fama e tempo de casa (v1.4)
        fama_inicial, temporadas = fama.inicial(j["nome"], j["idade"], j["overall"])
        jogadores[j["id"]] = Jogador(
            j["nome"],
            j["idade"],
            j["posicao"],
            j["overall"],
            potencial=j.get("potencial"),
            contrato_anos=j.get("contrato_anos", 3),
            multa_rescisoria=j.get("multa_rescisoria"),
            funcao=j.get("funcao"),
            secundarias=j.get("secundarias"),
            fama=fama_inicial,
            temporadas_no_clube=temporadas,
        )
        # a camisa de verdade (Premier, v1.6); a Taldo não traz e o clube dá
        jogadores[j["id"]].numero = j.get("numero")

    return jogadores


def carregar_clubes(jogadores, liga="taldo"):

    with open(
        LIGAS[liga][1] / "clubes.json",
        encoding="utf-8"
    ) as arquivo:

        dados = json.load(
            arquivo
        )

    clubes = []

    for c in dados:

        clube = Clube(
            c["nome"],
            c["pais"],
            c["dinheiro"],
            c["torcedores"]
        )
        # o estádio nasce do tamanho da torcida (v1.5)
        clube.capacidade = estadio.capacidade_inicial(c["nome"], c["torcedores"])

        for id_jogador in c["titulares"]:

            clube.contratar_jogador(
                jogadores[id_jogador]
            )

        for id_jogador in c["reservas"]:

            clube.contratar_reserva(
                jogadores[id_jogador]
            )

        clube.rivais = set(c.get("rivais", []))
        clube.liga = liga
        # cores, escudo e camisa (v1.1) — só visual, o motor não usa
        clube.identidade = c.get("identidade")

        clubes.append(
            clube
        )

    return clubes


def carregar_livres(liga="taldo"):
    """Os jogadores sem clube do começo da temporada (v1.6). Sem contrato:
    quem contrata define (mercado.contratar_livre)."""

    caminho = LIGAS[liga][1] / "livres.json"
    if not caminho.exists():
        return []
    with open(caminho, encoding="utf-8") as arquivo:
        dados = json.load(arquivo)

    jogadores = []
    for j in dados:
        jogador = livres.para_jogador(j)
        jogador.fama = fama.inicial(j["nome"], j["idade"], j["overall"])[0]
        jogadores.append(jogador)
    return jogadores


def carregar_campeonato(ligas=LIGA_PADRAO):
    """O campeonato com os clubes das `ligas` (v1.6): cada liga tem a sua
    tabela e o seu calendário, jogados na mesma rodada. Os livres das ligas
    formam uma lista só."""

    clubes, sem_clube = [], []
    for liga in ligas:
        clubes += carregar_clubes(carregar_jogadores(liga), liga)
        sem_clube += carregar_livres(liga)

    campeonato = Campeonato(
        "Taldo",
        clubes
    )
    campeonato.livres = sem_clube
    return campeonato
