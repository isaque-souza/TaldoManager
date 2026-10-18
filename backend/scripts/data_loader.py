import json
from pathlib import Path

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


def carregar_campeonato():

    jogadores = carregar_jogadores()

    clubes = carregar_clubes(jogadores)

    return Campeonato(
        "Taldo",
        clubes
    )
