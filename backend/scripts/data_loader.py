import json
from pathlib import Path

from app.domain import estadio, fama
from app.domain.jogador import Jogador
from app.domain.clube import Clube
from app.domain.campeonato import Campeonato

SEEDS_DIR = Path(__file__).resolve().parent.parent / "data" / "seeds"


def carregar_jogadores():

    with open(
        SEEDS_DIR / "jogadores.json",
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

    return jogadores


def carregar_clubes(jogadores):

    with open(
        SEEDS_DIR / "clubes.json",
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
        # cores, escudo e camisa (v1.1) — só visual, o motor não usa
        clube.identidade = c.get("identidade")

        clubes.append(
            clube
        )

    return clubes


def carregar_livres():
    """Os jogadores sem clube do começo da temporada (v1.6). Sem contrato:
    quem contrata define (mercado.contratar_livre)."""

    caminho = SEEDS_DIR / "livres.json"
    if not caminho.exists():
        return []
    with open(caminho, encoding="utf-8") as arquivo:
        dados = json.load(arquivo)

    return [
        Jogador(
            j["nome"],
            j["idade"],
            j["posicao"],
            j["overall"],
            potencial=j["potencial"],
            contrato_anos=0,
            funcao=j["funcao"],
            secundarias=j["secundarias"],
            fama=fama.inicial(j["nome"], j["idade"], j["overall"])[0],
        )
        for j in dados
    ]


def carregar_campeonato():

    jogadores = carregar_jogadores()

    clubes = carregar_clubes(jogadores)

    campeonato = Campeonato(
        "Taldo",
        clubes
    )
    campeonato.livres = carregar_livres()
    return campeonato
