import json
from functools import lru_cache
from pathlib import Path

from app.domain import estadio, fama, financas, livres, vontade
from app.domain.jogador import Jogador
from app.domain.clube import Clube
from app.domain.campeonato import Campeonato
from scripts import mundos
from scripts.mundos import MUNDO_INICIAL, MUNDO_PADRAO  # noqa: F401 (reexporta)

SEEDS_DIR = Path(__file__).resolve().parent.parent / "data" / "seeds"

# Mundos versionados (v2.7): as seeds de cada liga saem do manifesto do
# mundo (scripts/mundos.py). Todo save carrega o mundo em que nasceu; sem
# dizer o mundo, é o v1 — as 8 ligas da v2.6, em data/seeds/, que nunca
# mudam. Por isso o padrão das funções abaixo é o v1, e não o de jogo novo.


def ligas_do_mundo(mundo=MUNDO_INICIAL):
    """{id: (nome, pasta da seed)}, na ordem das tabelas."""
    return {liga: (nome, mundos.pasta_da_liga(mundo, liga))
            for liga, nome in mundos.ligas(mundo).items()}


def todas_as_ligas(mundo=MUNDO_INICIAL):
    """As ligas do mundo, na ordem das tabelas (jogo novo tem todas)."""
    return tuple(mundos.ligas(mundo))


# ligas (v1.6) do v1: id -> (nome, pasta da seed). A ordem é a das tabelas.
LIGAS = ligas_do_mundo(MUNDO_INICIAL)
LIGA_PADRAO = ("taldo",)   # saves de antes da v1.6
TODAS_AS_LIGAS = tuple(LIGAS)   # todo jogo novo do v1 (v1.6)


def nome_da_liga(liga, mundo=None):
    """O nome de exibição da liga: do mundo dado; sem mundo, do primeiro que
    a tiver (o mesmo id tem o mesmo nome em todo mundo)."""
    for m in ([mundo] if mundo else [MUNDO_INICIAL, *mundos.ids()]):
        nome = mundos.ligas(m).get(liga)
        if nome:
            return nome
    return liga


def ligas_do_save(sim):
    """As ligas de uma simulação (linha da tabela `simulacao`); saves de
    antes da v1.6 (NULL) só têm a Taldo."""
    return tuple(json.loads(sim["ligas"])) if sim["ligas"] else LIGA_PADRAO


def mundo_do_save(sim):
    """O mundo de uma simulação (v2.7); saves de antes, e linhas sem a
    coluna, são do v1."""
    try:
        mundo = sim["mundo"]
    except (KeyError, IndexError):
        mundo = None
    return mundo or MUNDO_INICIAL


def _pasta(liga, mundo):
    """A pasta da liga no mundo, conferido (hashes) uma vez por processo."""
    mundos.verificar(mundo)
    if liga not in mundos.manifesto(mundo)["ligas"]:
        raise ValueError(f"A liga '{liga}' não existe no mundo '{mundo}'")
    return mundos.pasta_da_liga(mundo, liga)


@lru_cache(maxsize=None)
def rivais_do_seed(mundo=MUNDO_INICIAL):
    """{nome do clube: frozenset dos rivais} de todas as ligas do mundo, lido
    uma vez (os clássicos não mudam com o save)."""
    rivais = {}
    for liga in todas_as_ligas(mundo):
        with open(_pasta(liga, mundo) / "clubes.json", encoding="utf-8") as arquivo:
            for c in json.load(arquivo):
                rivais[c["nome"]] = frozenset(c.get("rivais", []))
    return rivais


def carregar_jogadores(liga="taldo", mundo=MUNDO_INICIAL):

    with open(
        _pasta(liga, mundo) / "jogadores.json",
        encoding="utf-8"
    ) as arquivo:

        dados = json.load(arquivo)

    jogadores = {}

    for j in dados:

        # quem já está na liga começa com fama e tempo de casa (v1.4)
        fama_inicial, temporadas = fama.inicial(j["nome"], j["idade"], j["overall"])
        # mundos da API (v2.7): `ref` ("apif:12345") é a chave e `nome` é o
        # de exibição; no v1 não há `ref` e a chave é o nome
        jogadores[j["id"]] = Jogador(
            j.get("ref") or j["nome"],
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
            exibicao=j["nome"] if j.get("ref") else None,
        )
        # a camisa de verdade (Premier, v1.6); a Taldo não traz e o clube dá
        jogadores[j["id"]].numero = j.get("numero")

    return jogadores


def carregar_clubes(jogadores, liga="taldo", mundo=MUNDO_INICIAL):

    with open(
        _pasta(liga, mundo) / "clubes.json",
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
        # posição na liga real do ano anterior (Premier 23/24), para a copa
        clube.posicao_anterior = c.get("posicao_2023_24")
        # cores, escudo e camisa (v1.1) — só visual, o motor não usa
        clube.identidade = c.get("identidade")

        clubes.append(
            clube
        )

    return clubes


def carregar_livres(liga="taldo", mundo=MUNDO_INICIAL):
    """Os jogadores sem clube do começo da temporada (v1.6). Sem contrato:
    quem contrata define (mercado.contratar_livre)."""

    caminho = _pasta(liga, mundo) / "livres.json"
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


def carregar_campeonato(ligas=LIGA_PADRAO, mundo=MUNDO_INICIAL):
    """O campeonato com os clubes das `ligas` (v1.6) do `mundo` (v2.7):
    cada liga tem a sua tabela e o seu calendário, jogados na mesma rodada.
    Os livres das ligas formam uma lista só."""

    clubes, sem_clube = [], []
    for liga in ligas:
        clubes += carregar_clubes(carregar_jogadores(liga, mundo), liga, mundo)
        sem_clube += carregar_livres(liga, mundo)

    campeonato = Campeonato(
        "Taldo",
        clubes
    )
    campeonato.livres = sem_clube
    campeonato.mundo = mundo
    # formador e sonho de todo mundo (v1.9)
    vontade.completar(campeonato)
    return campeonato


def carregar_campeonato_do_save(sim):
    """O campeonato com as ligas do save, no mundo do save (v2.7), pronto
    para `restaurar_estado`, com as regras de dinheiro em que o save está
    (v2.5)."""
    campeonato = carregar_campeonato(ligas_do_save(sim), mundo_do_save(sim))
    campeonato.economia = financas.economia_do_save(sim)
    return campeonato
