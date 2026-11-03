"""As copas (v1.6; v2.6, várias): mata-mata de jogo único, no meio da
semana, com pênaltis no empate.

- a **copa entre as ligas** (continental): os 8 melhores de cada Série A
  (32 clubes com as 4 ligas; 16 com duas). Paga como a Champions;
- uma **copa nacional** por país que tem a A e a B no save: os 20 da A e os
  12 melhores da B (32 clubes).

As fases são jogadas depois de algumas rodadas da liga (`DATAS`). As
nacionais jogam nas mesmas quartas (cada clube só está na do seu país) e a
continental em outras: o técnico nunca tem dois jogos de copa na mesma
semana. Uma fase é chamada
pela `chave` "copa:fase" ("brasil:oitavas", "continental:final").

Um jogo de copa é uma `Partida` comum, mas ela foi feita para a liga e mexe
direto nos jogadores e clubes (gols, cartões, suspensões, pontos...). Por
isso a copa tira uma foto dos números antes do apito e devolve depois: só o
cansaço e as lesões novas ficam (`_isolar_da_liga`).

O estado é um dict JSON (`Copas.para_dict` / `Copas.de_dict`), para ir no
snapshot. O formato de antes da v2.6 (uma copa só, Taldo x Premier) ainda
é lido: vira a copa "continental" com as datas de então (`normalizar`).
"""

import random

from . import diretoria, divisoes, financas
from .estadio import publico
from .partida import Partida

VAGAS_POR_LIGA = 8          # na copa entre as ligas
VAGAS_DA_SERIE_B = 12       # na copa nacional (com os 20 da A: 32)

CONTINENTAL = "continental"
NOME_CONTINENTAL = "Copa entre as ligas"
# país (app.domain.divisoes) -> nome da copa nacional
NOMES_NACIONAIS = {
    "taldo": "Taça Taldo",
    "inglaterra": "FA Cup",
    "espanha": "Copa del Rey",
    "brasil": "Copa do Brasil",
}

# todas as fases, da primeira à final; uma copa de N clubes joga as últimas
# log2(N)
FASES_TODAS = ["16-avos", "oitavas", "quartas", "semi", "final"]
NOMES_DAS_FASES = {
    "16-avos": "16 avos de final",
    "oitavas": "Oitavas de final",
    "quartas": "Quartas de final",
    "semi": "Semifinal",
    "final": "Final",
}

# a fase é jogada no meio da semana, depois desta rodada da liga
DATAS = {
    CONTINENTAL: {"16-avos": 5, "oitavas": 12, "quartas": 19, "semi": 26, "final": 34},
    "nacional": {"16-avos": 3, "oitavas": 9, "quartas": 16, "semi": 23, "final": 30},
}
# a copa de antes da v2.6 (16 clubes, Taldo x Premier)
DATAS_V1 = {"oitavas": 8, "quartas": 17, "semi": 26, "final": 35}

# prêmio por vitória em cada fase (economia v2, v2.5). A copa entre as ligas
# paga igual para todos, como a Champions: o campeão soma 19 mi (a de antes
# da v2.6, com uma fase a menos, 20 mi). A nacional é a de um país de peso
# 1,0 (a FA Cup, 8,1 mi): cada país paga pelo peso da sua Série A, como a
# premiação da liga (`financas.PESO_LIGA`) — a Copa do Brasil, 3,2 mi
PREMIOS = {
    CONTINENTAL: {"16-avos": 1_000_000, "oitavas": 2_000_000, "quartas": 3_500_000,
                  "semi": 5_500_000, "final": 7_000_000},
    "nacional": {"16-avos": 300_000, "oitavas": 600_000, "quartas": 1_200_000,
                 "semi": 2_000_000, "final": 4_000_000},
}
# economia v1: o campeão da continental levava 7,5 mi (o da liga, 10 mi)
PREMIOS_V1 = {
    CONTINENTAL: {"16-avos": 250_000, "oitavas": 500_000, "quartas": 1_000_000,
                  "semi": 2_000_000, "final": 4_000_000},
    "nacional": {"16-avos": 100_000, "oitavas": 200_000, "quartas": 400_000,
                 "semi": 800_000, "final": 1_500_000},
}


def premios(economia, tipo=CONTINENTAL, copa_id=None):
    """{fase: prêmio por vitória} da copa do `tipo` (continental/nacional).
    A nacional (`copa_id` = o país) sai pelo peso da Série A dele."""
    base = (PREMIOS_V1 if economia < 2 else PREMIOS)[tipo]
    if tipo == CONTINENTAL or copa_id is None:
        return dict(base)
    serie_a = next((l for l, (p, d) in divisoes.DIVISOES.items() if p == copa_id and d == 1), None)
    fator = financas.peso(serie_a) if serie_a else 1.0
    return {f: round(v * fator / 10_000) * 10_000 for f, v in base.items()}


def premios_da_copa(economia, c):
    """Os prêmios de uma copa (um `Copa` ou o dict dela)."""
    tipo, copa_id = (c["tipo"], c["id"]) if isinstance(c, dict) else (c.tipo, c.id)
    return premios(economia, tipo, copa_id)


# disputa de pênaltis
COBRANCAS = 5

# o que um jogo de copa deixa no jogador; o resto volta ao que era
FICA_DA_COPA = {"energia", "rodadas_lesao"}

# os lances que o jogo da copa guarda (a liga guarda todos em `lance`; o
# chute para fora só enche a linha do tempo)
EVENTOS_DO_RELATORIO = (
    "gol", "penalti", "penalti_perdido", "penalti_defendido",
    "cartao_amarelo", "expulsao", "substituicao", "lesao",
)


# --- chaves "copa:fase" -------------------------------------------------------

def chave(copa_id, fase):
    return f"{copa_id}:{fase}"


def dividir(chave_):
    """(copa, fase) de uma chave. A fase sozinha (saves de antes da v2.6,
    em `simulacao.copa_pendente`) é da continental."""
    if ":" not in chave_:
        return CONTINENTAL, chave_
    copa_id, fase = chave_.rsplit(":", 1)
    return copa_id, fase


def nome_da_fase(fase):
    return NOMES_DAS_FASES[fase]


# --- quem joga ----------------------------------------------------------------

def classificados_de_inicio(campeonato):
    """A ordem de cada liga num jogo novo: {liga: [nomes, do 1º ao último]}.
    A liga com tabela do ano anterior (Premier 23/24) usa a posição nela; a
    outra, o ranking de força dos elencos."""
    classificados = {}
    for liga in campeonato.ligas:
        clubes = campeonato.clubes_da_liga(liga)
        forca = diretoria.ranking_de_forca(clubes)
        ordem = sorted(clubes, key=lambda c: (c.posicao_anterior or 99, forca[c.nome]))
        classificados[liga] = [c.nome for c in ordem]
    return classificados


def classificados_pela_tabela(clubes_finais):
    """A ordem de cada liga pela tabela da temporada anterior (carreira):
    `clubes_finais` são as linhas da tabela `clube` (nome, liga,
    posicao_final)."""
    classificados = {}
    for c in sorted(clubes_finais, key=lambda c: c["posicao_final"]):
        classificados.setdefault(c["liga"], []).append(c["nome"])
    return classificados


def montar(campeonato, classificados):
    """As copas da temporada, com a ordem de cada liga (`classificados_*`):
    a continental com os 8 melhores de cada Série A (2 ou 4 ligas; com outro
    número, não tem) e a nacional de cada país com a A e a B no save. A
    nacional usa as divisões de agora (quem subiu joga entre os da A) e a
    ordem de antes (quem caiu vem antes dos da B)."""
    copas = []

    primeiras = [l for l in divisoes.primeiras(campeonato.ligas) if l in classificados]
    if len(primeiras) in (2, 4):
        copas.append(Copa.continental({l: classificados[l][:VAGAS_POR_LIGA] for l in primeiras}))

    # (divisão antes, posição antes): quem caiu vem antes dos da B
    antes = {
        nome: (divisoes.divisao(liga), posicao)
        for liga, nomes in classificados.items()
        for posicao, nome in enumerate(nomes, start=1)
    }
    for a in divisoes.primeiras(campeonato.ligas):
        b = divisoes.da_divisao(a, 2)
        if b not in campeonato.ligas:
            continue
        ordem = lambda liga: sorted(
            (c.nome for c in campeonato.clubes_da_liga(liga)),
            key=lambda n: (*antes.get(n, (9, 99)), n),
        )
        da_a, da_b = ordem(a), ordem(b)[:VAGAS_DA_SERIE_B]
        if len(da_a) + len(da_b) == 32:
            copas.append(Copa.nacional(divisoes.pais(a), {a: da_a, b: da_b}))
    return Copas(copas)


def _chaveamento(n):
    """A ordem dos seeds na primeira fase: 1 x n, ... e o 1º e o 2º só se
    encontram na final ([1, 4, 2, 3] para 4)."""
    ordem = [1]
    while len(ordem) < n:
        tamanho = len(ordem) * 2
        ordem = [s for x in ordem for s in (x, tamanho + 1 - x)]
    return ordem


class Copa:
    """Uma copa: os jogos de cada fase, as datas e o seed de cada clube (o
    melhor seed joga em casa)."""

    def __init__(self, id, nome, tipo, classificados, seed, ordem, datas, fases):
        self.id = id
        self.nome = nome
        self.tipo = tipo                    # continental | nacional
        self.classificados = classificados  # {liga: [nomes]}
        self.seed = seed                    # {nome: seed}
        self.ordem = ordem                  # as fases, da primeira à final
        self.datas = datas                  # {fase: rodada}
        self.fases = fases                  # {fase: [jogos]}
        self.partida_usuario = None

    @classmethod
    def _nova(cls, id, nome, tipo, classificados, participantes):
        """`participantes`: do seed 1 ao último (32 ou 16)."""
        n = len(participantes)
        ordem = FASES_TODAS[len(FASES_TODAS) - (n.bit_length() - 1):]
        if 2 ** len(ordem) != n:
            raise ValueError(f"a copa precisa de 2, 4, 8, 16 ou 32 clubes, não {n}")
        seed = {nome: i for i, nome in enumerate(participantes, start=1)}
        seeds = _chaveamento(n)
        primeira = [
            _jogo(participantes[seeds[i] - 1], participantes[seeds[i + 1] - 1])
            for i in range(0, n, 2)
        ]
        datas = {f: DATAS[CONTINENTAL if tipo == CONTINENTAL else "nacional"][f] for f in ordem}
        return cls(id, nome, tipo, classificados, seed, ordem, datas, {ordem[0]: primeira})

    @classmethod
    def continental(cls, classificados):
        """`classificados`: {liga: [do 1º ao 8º]}. Seed pela posição e, no
        empate, pela ordem das ligas: na primeira fase ninguém pega um clube
        da própria liga, e os 1º das ligas só se cruzam a partir da
        semifinal (com duas ligas, só na final)."""
        ligas = list(classificados)
        if len(ligas) < 2:
            raise ValueError("a copa entre as ligas precisa de duas ligas")
        participantes = [
            classificados[liga][p]
            for p in range(VAGAS_POR_LIGA)
            for liga in ligas
        ]
        return cls._nova(CONTINENTAL, NOME_CONTINENTAL, CONTINENTAL, classificados, participantes)

    @classmethod
    def nacional(cls, pais, classificados):
        """`classificados`: {Série A: [os 20], Série B: [os 12]}, cada uma na
        ordem. Seed: os da A, depois os da B."""
        participantes = [n for nomes in classificados.values() for n in nomes]
        return cls._nova(pais, NOMES_NACIONAIS.get(pais, f"Copa {pais}"), "nacional",
                         classificados, participantes)

    # --- estado ---------------------------------------------------------

    def para_dict(self):
        return {
            "id": self.id, "nome": self.nome, "tipo": self.tipo,
            "classificados": self.classificados, "seed": self.seed,
            "ordem": self.ordem, "datas": self.datas, "fases": self.fases,
        }

    @classmethod
    def de_dict(cls, dados):
        d = _normalizar_copa(dados)
        return cls(d["id"], d["nome"], d["tipo"], d["classificados"], d["seed"],
                   d["ordem"], d["datas"], d["fases"])

    # --- andamento ------------------------------------------------------

    def fase_da_rodada(self, rodada):
        """A fase jogada depois desta rodada da liga, ou None."""
        return next((f for f in self.ordem if self.datas[f] == rodada), None)

    @property
    def campeao(self):
        final = self.fases.get("final")
        return final[0]["vencedor"] if final and final[0]["vencedor"] else None

    def jogos_do_clube(self, nome):
        return [
            {"fase": fase, **jogo}
            for fase in self.ordem
            for jogo in self.fases.get(fase, [])
            if nome in (jogo["mandante"], jogo["visitante"])
        ]

    def jogar_fase(self, fase, clubes, ao_vivo=None, premios=None):
        """Joga os jogos da fase (`clubes`: {nome: Clube}), paga prêmio e
        bilheteria e monta a próxima. Devolve os jogos jogados.

        `ao_vivo` (o jogo do técnico, transmitido): {"clube", "decisoes",
        "capturar_em", "semente"}. O jogo dele roda na corrente de RNG da
        `semente`, como na liga (`Campeonato.jogar_rodada`), e a Partida
        fica em `self.partida_usuario`."""

        self.partida_usuario = None
        jogos = self.fases.get(fase)
        if not jogos or jogos[0]["vencedor"]:
            return []
        premios = premios or premios_da_copa(financas.ECONOMIA_ATUAL, self)

        for jogo in jogos:
            dele = ao_vivo and ao_vivo["clube"] in (jogo["mandante"], jogo["visitante"])
            partida = _disputar(
                jogo, clubes[jogo["mandante"]], clubes[jogo["visitante"]],
                ao_vivo if dele else None,
            )
            if dele:
                self.partida_usuario = partida
            clubes[jogo["vencedor"]].lancar("receita_premiacao", premios[fase])

        proxima = self.ordem.index(fase) + 1
        if proxima < len(self.ordem):
            vencedores = [j["vencedor"] for j in jogos]
            self.fases[self.ordem[proxima]] = [
                self._confronto(vencedores[i], vencedores[i + 1])
                for i in range(0, len(vencedores), 2)
            ]
        return jogos

    def _confronto(self, a, b):
        """Joga em casa quem tem o melhor seed; no empate (a copa de antes
        da v2.6, com o seed pela posição na liga), quem vem antes na chave."""
        return _jogo(a, b) if self.seed[a] <= self.seed[b] else _jogo(b, a)


class Copas:
    """As copas da temporada, jogadas pela chave "copa:fase"."""

    def __init__(self, copas):
        self.copas = list(copas)
        self.partida_usuario = None

    def __iter__(self):
        return iter(self.copas)

    def __len__(self):
        return len(self.copas)

    def copa(self, copa_id):
        return next((c for c in self.copas if c.id == copa_id), None)

    # --- estado ---------------------------------------------------------

    def para_dict(self):
        return {"copas": [c.para_dict() for c in self.copas]}

    @classmethod
    def de_dict(cls, dados):
        return cls(Copa.de_dict(c) for c in normalizar(dados)["copas"])

    # --- andamento ------------------------------------------------------

    @property
    def fases(self):
        """{chave: jogos} de todas as copas (as listas são as delas)."""
        return {chave(c.id, f): jogos for c in self.copas for f, jogos in c.fases.items()}

    def chaves_da_rodada(self, rodada):
        """As chaves das fases jogadas depois desta rodada (as nacionais
        caem juntas)."""
        return [chave(c.id, f) for c in self.copas if (f := c.fase_da_rodada(rodada))]

    def fase_da_rodada(self, rodada, clube=None):
        """A chave da fase desta rodada da copa em que o `clube` está (ou da
        primeira), ou None."""
        chaves = self.chaves_da_rodada(rodada)
        if clube:
            dele = [k for k in chaves if any(
                clube in n for n in self.copa(dividir(k)[0]).classificados.values())]
            chaves = dele or chaves
        return chaves[0] if chaves else None

    def rodada_da_chave(self, chave_):
        copa_id, fase = dividir(chave_)
        return self.copa(copa_id).datas[fase]

    @property
    def campeao(self):
        """O campeão da copa entre as ligas."""
        c = self.copa(CONTINENTAL)
        return c.campeao if c else None

    def jogar_fase(self, chave_, clubes, ao_vivo=None, economia=financas.ECONOMIA_ATUAL):
        copa_id, fase = dividir(chave_)
        c = self.copa(copa_id)
        jogos = c.jogar_fase(fase, clubes, ao_vivo, premios_da_copa(economia, c))
        self.partida_usuario = c.partida_usuario
        return jogos


# --- o estado em dict (para os serviços, que não restauram nada) --------------

def _normalizar_copa(dados):
    """Uma copa em dict; a de antes da v2.6 ganha id, nome, datas e o seed
    (a posição na liga)."""
    if "id" in dados:
        return dados
    return {
        "id": CONTINENTAL, "nome": NOME_CONTINENTAL, "tipo": CONTINENTAL,
        "classificados": dados["classificados"],
        "seed": {n: p for nomes in dados["classificados"].values()
                 for p, n in enumerate(nomes, start=1)},
        "ordem": list(DATAS_V1), "datas": dict(DATAS_V1), "fases": dados["fases"],
    }


def normalizar(dados):
    """{"copas": [...]} de qualquer formato (o de antes da v2.6 é uma copa
    só); None fica None."""
    if not dados:
        return dados
    if "copas" in dados:
        return {"copas": [_normalizar_copa(c) for c in dados["copas"]]}
    return {"copas": [_normalizar_copa(dados)]}


def copa_de(dados, copa_id):
    dados = normalizar(dados)
    return next((c for c in (dados or {}).get("copas", []) if c["id"] == copa_id), None)


def jogos_da_chave(dados, chave_):
    copa_id, fase = dividir(chave_)
    c = copa_de(dados, copa_id)
    return (c or {}).get("fases", {}).get(fase) or []


def rodada_da_chave(dados, chave_):
    copa_id, fase = dividir(chave_)
    return copa_de(dados, copa_id)["datas"][fase]


def chave_da_rodada(dados, rodada, clube=None):
    """A chave da fase jogada depois desta rodada, ou None: a da copa em
    que o `clube` está, se ele está em alguma; senão, a da primeira."""
    chaves = []
    for i, c in enumerate((normalizar(dados) or {}).get("copas", [])):
        fase = next((f for f in c["ordem"] if c["datas"][f] == rodada), None)
        if fase:
            dele = any(clube in n for n in c["classificados"].values()) if clube else False
            chaves.append((not dele, i, chave(c["id"], fase)))
    return min(chaves)[2] if chaves else None


def nome_da_chave(dados, chave_):
    """"Copa do Brasil · Oitavas de final"."""
    copa_id, fase = dividir(chave_)
    c = copa_de(dados, copa_id)
    return f"{c['nome'] if c else NOME_CONTINENTAL} · {nome_da_fase(fase)}"


def jogos_de_todas(dados):
    """[(copa, fase, jogo)] de todas as copas, na ordem das fases."""
    return [
        (c, fase, j)
        for c in (normalizar(dados) or {}).get("copas", [])
        for fase in c["ordem"]
        for j in c["fases"].get(fase) or []
    ]


def campeao_de(dados, copa_id=CONTINENTAL):
    """O campeão de uma copa (no dict de `Copas.para_dict`), ou None."""
    c = copa_de(dados, copa_id)
    final = (c or {}).get("fases", {}).get("final")
    return final[0]["vencedor"] if final and final[0]["vencedor"] else None


def campeoes_de(dados):
    """{copa: campeão} das copas que já têm campeão."""
    return {
        c["id"]: campeao_de(dados, c["id"])
        for c in (normalizar(dados) or {}).get("copas", [])
        if campeao_de(dados, c["id"])
    }


def ate_onde(dados, clube, copa_id=CONTINENTAL):
    """Até onde o clube foi na copa: "campeao", a fase em que caiu (ou a
    que vai jogar, com a copa em andamento) ou None se não entrou."""
    c = copa_de(dados, copa_id)
    if not c or not any(clube in n for n in c["classificados"].values()):
        return None
    if campeao_de(dados, copa_id) == clube:
        return "campeao"
    alcancada = c["ordem"][0]
    for fase in c["ordem"]:
        if any(clube in (j["mandante"], j["visitante"]) for j in c["fases"].get(fase, [])):
            alcancada = fase
    return alcancada


def _jogo(mandante, visitante):
    return {
        "mandante": mandante,
        "visitante": visitante,
        "gols_mandante": None,
        "gols_visitante": None,
        "penaltis": None,          # [mandante, visitante] se foi para eles
        "vencedor": None,
        "publico": None,
        "gols": [],                # [{minuto, jogador, clube, tipo}]
    }


def _disputar(jogo, mandante, visitante, ao_vivo=None):
    partida = Partida(mandante, visitante)
    partida.publico = publico(mandante, visitante)

    fora = None
    if ao_vivo:
        partida.decisoes = ao_vivo.get("decisoes") or []
        partida.capturar_em = ao_vivo.get("capturar_em")
        fora = random.getstate()
        random.seed(ao_vivo["semente"])
    try:
        with _isolar_da_liga(mandante, visitante):
            partida.simular_partida()
            penaltis = None
            if partida.gols_c1 == partida.gols_c2:
                penaltis = disputa_de_penaltis(partida)
    finally:
        if fora is not None:
            random.setstate(fora)

    mandante.lancar(
        "receita_bilheteria", financas.bilheteria(mandante, partida.publico)
    )

    jogo["gols_mandante"] = partida.gols_c1
    jogo["gols_visitante"] = partida.gols_c2
    jogo["penaltis"] = penaltis
    jogo["publico"] = partida.publico
    if penaltis:
        jogo["vencedor"] = mandante.nome if penaltis[0] > penaltis[1] else visitante.nome
    else:
        jogo["vencedor"] = mandante.nome if partida.gols_c1 > partida.gols_c2 else visitante.nome
    eventos = partida.resumo_eventos()
    jogo["gols"] = [
        {k: e[k] for k in ("minuto", "jogador", "clube", "tipo")}
        for e in eventos
        if e["tipo"] in ("gol", "penalti")
    ]
    # para o relatório pós-jogo (v2.2): o que a liga guarda em partida,
    # lance e atuacao. Jogos de saves anteriores não têm estes três.
    jogo["estatisticas"] = {
        "posse_mandante": partida.posse_c1,
        "finalizacoes_mandante": partida.finalizacoes_c1,
        "finalizacoes_visitante": partida.finalizacoes_c2,
        "finalizacoes_gol_mandante": partida.finalizacoes_gol_c1,
        "finalizacoes_gol_visitante": partida.finalizacoes_gol_c2,
        "escanteios_mandante": partida.escanteios_c1,
        "escanteios_visitante": partida.escanteios_c2,
        "acrescimos": partida.acrescimos,
    }
    jogo["eventos"] = [
        {k: e[k] for k in ("minuto", "tipo", "jogador", "clube", "detalhe")}
        for e in eventos
        if e["tipo"] in EVENTOS_DO_RELATORIO
    ]
    jogo["atuacoes"] = partida.resumo_escalacao()
    return partida


class _isolar_da_liga:
    """Foto dos números dos dois clubes e dos elencos antes do jogo; na
    saída devolve tudo, menos o cansaço e as lesões novas."""

    def __init__(self, *clubes):
        self.clubes = clubes

    def __enter__(self):
        self.fotos = [
            (obj, _numeros(obj))
            for clube in self.clubes
            for obj in (clube, *clube.jogadores)
        ]
        self.formas = [(c, list(c.forma)) for c in self.clubes]

    def __exit__(self, *_):
        for obj, foto in self.fotos:
            lesao = getattr(obj, "rodadas_lesao", 0)
            for campo, valor in foto.items():
                if campo not in FICA_DA_COPA:
                    setattr(obj, campo, valor)
            # a lesão nova fica; a recuperação não anda (não é rodada da liga)
            if "rodadas_lesao" in foto:
                obj.rodadas_lesao = max(foto["rodadas_lesao"], lesao)
        for clube, forma in self.formas:
            clube.forma = forma


def _numeros(obj):
    return {
        k: v for k, v in vars(obj).items()
        if isinstance(v, (int, float, bool))
    }


def disputa_de_penaltis(partida):
    """5 cobranças para cada lado, alternadas, e depois uma a uma até
    alguém errar. Cobra quem terminou em campo, dos melhores finalizadores
    para os piores, e volta ao primeiro se precisar. Devolve [c1, c2]; as
    cobranças, uma a uma, ficam em `partida.cobrancas`."""

    filas = [_cobradores(partida, c) for c in (partida.clube1, partida.clube2)]
    goleiros = [partida._goleiro(partida.clube2), partida._goleiro(partida.clube1)]
    placar = [0, 0]
    cobradas = [0, 0]
    # a sequência, para a transmissão: [{lado (1 mandante, 2 visitante),
    # jogador, gol}]
    partida.cobrancas = []

    def cobrar(lado):
        fila = filas[lado]
        cobrador = fila[cobradas[lado] % len(fila)]
        cobradas[lado] += 1
        gol = random.random() < _chance_de_converter(partida, cobrador, goleiros[lado])
        if gol:
            placar[lado] += 1
        partida.cobrancas.append({"lado": lado + 1, "jogador": cobrador.nome, "gol": gol})

    for _ in range(COBRANCAS):
        for lado in (0, 1):
            cobrar(lado)
            if _decidido(placar, cobradas):
                return placar

    while placar[0] == placar[1]:
        cobrar(0)
        cobrar(1)
    return placar


def _decidido(placar, cobradas):
    """Nas 5 primeiras: alguém já não alcança o outro."""
    restam = [COBRANCAS - c for c in cobradas]
    return placar[0] + restam[0] < placar[1] or placar[1] + restam[1] < placar[0]


def _cobradores(partida, clube):
    em_campo = [j for j in clube.titulares if not j.expulso] or clube.titulares
    return sorted(em_campo, key=_finalizacao, reverse=True)


def _finalizacao(jogador):
    """O goleiro não tem finalização: bate por último, e mal."""
    return jogador.atributos.get("finalizacao", 0)


def _chance_de_converter(partida, cobrador, goleiro):
    """A conta do pênalti no jogo (`Partida.simular_penalti_minuto`)."""
    diferenca = _finalizacao(cobrador) - (
        partida.nivel_goleiro(goleiro) if goleiro else partida.REF_FINALIZACAO
    ) - partida.VANTAGEM_COBRADOR
    return max(0.62, min(0.88, 0.76 + diferenca * 0.003))
