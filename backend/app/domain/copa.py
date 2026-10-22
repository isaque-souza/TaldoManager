"""Copa entre as ligas (v1.6): 16 clubes, os 8 melhores de cada liga, em
mata-mata de jogo único, no meio da semana.

As fases são jogadas depois de algumas rodadas da liga (`DATAS`), então o
calendário da liga (salários, TV, obras...) não muda. Um jogo de copa é uma
`Partida` comum, mas ela foi feita para a liga e mexe direto nos jogadores e
clubes (gols, cartões, suspensões, pontos...). Por isso a copa tira uma foto
dos números antes do apito e devolve depois: só o cansaço e as lesões novas
ficam (`_isolar_da_liga`).

O estado é um dict JSON (`para_dict` / `de_dict`), para ir no snapshot.
"""

import random

from . import diretoria, financas
from .estadio import publico
from .partida import Partida

VAGAS_POR_LIGA = 8

# a fase é jogada no meio da semana, depois desta rodada da liga
DATAS = {"oitavas": 8, "quartas": 17, "semi": 26, "final": 35}
FASES = list(DATAS)

# prêmio por vitória em cada fase: o campeão leva 7,5 mi (o da liga, 10 mi)
PREMIOS = {
    "oitavas": 500_000,
    "quartas": 1_000_000,
    "semi": 2_000_000,
    "final": 4_000_000,
}

# a ordem das oitavas monta a chave: os vencedores dos jogos 1 e 2 se
# enfrentam nas quartas, os de 3 e 4 também... O 1º de cada liga só pode
# encontrar o 1º da outra na final, e o 2º de cada uma fica no lado do 1º
# da outra. (liga, posição): 0 = a primeira liga, 1 = a segunda
CHAVE_OITAVAS = [
    ((0, 1), (1, 8)), ((1, 4), (0, 5)), ((0, 3), (1, 6)), ((1, 2), (0, 7)),
    ((1, 1), (0, 8)), ((0, 4), (1, 5)), ((1, 3), (0, 6)), ((0, 2), (1, 7)),
]

# o que um jogo de copa deixa no jogador; o resto volta ao que era
FICA_DA_COPA = {"energia", "rodadas_lesao"}

# disputa de pênaltis
COBRANCAS = 5


def classificados_de_inicio(campeonato):
    """Os classificados de um jogo novo: {liga: [nomes do 1º ao 8º]}. A
    liga com tabela do ano anterior (Premier 23/24) usa a posição nela; a
    outra, o ranking de força dos elencos."""
    classificados = {}
    for liga in campeonato.ligas:
        clubes = campeonato.clubes_da_liga(liga)
        forca = diretoria.ranking_de_forca(clubes)
        ordem = sorted(clubes, key=lambda c: (c.posicao_anterior or 99, forca[c.nome]))
        classificados[liga] = [c.nome for c in ordem][:VAGAS_POR_LIGA]
    return classificados


def classificados_pela_tabela(clubes_finais):
    """Os classificados pela tabela da temporada anterior (carreira):
    `clubes_finais` são as linhas da tabela `clube` (nome, liga,
    posicao_final)."""
    classificados = {}
    for c in sorted(clubes_finais, key=lambda c: c["posicao_final"]):
        classificados.setdefault(c["liga"], []).append(c["nome"])
    return {l: n[:VAGAS_POR_LIGA] for l, n in classificados.items()}


class Copa:

    def __init__(self, classificados):
        """`classificados`: {liga: [nomes na ordem, do 1º ao 8º]}, com duas
        ligas. O seed é a posição na liga (1 a 8)."""
        if len(classificados) != 2:
            raise ValueError("a copa é entre duas ligas")
        ligas = list(classificados)
        self.classificados = {l: list(n[:VAGAS_POR_LIGA]) for l, n in classificados.items()}
        self.seed = {
            nome: posicao
            for liga in ligas
            for posicao, nome in enumerate(self.classificados[liga], start=1)
        }
        self.fases = {
            "oitavas": [
                _jogo(*(self.classificados[ligas[l]][p - 1] for l, p in par))
                for par in CHAVE_OITAVAS
            ]
        }

    # --- estado ---------------------------------------------------------

    def para_dict(self):
        return {"classificados": self.classificados, "fases": self.fases}

    @classmethod
    def de_dict(cls, dados):
        copa = cls(dados["classificados"])
        copa.fases = dados["fases"]
        return copa

    # --- andamento ------------------------------------------------------

    def fase_da_rodada(self, rodada):
        """A fase jogada depois desta rodada da liga, ou None."""
        return next((f for f, r in DATAS.items() if r == rodada), None)

    @property
    def campeao(self):
        final = self.fases.get("final")
        return final[0]["vencedor"] if final and final[0]["vencedor"] else None

    def jogos_do_clube(self, nome):
        return [
            {"fase": fase, **jogo}
            for fase in FASES
            for jogo in self.fases.get(fase, [])
            if nome in (jogo["mandante"], jogo["visitante"])
        ]

    def jogar_fase(self, fase, clubes, ao_vivo=None):
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

        for jogo in jogos:
            dele = ao_vivo and ao_vivo["clube"] in (jogo["mandante"], jogo["visitante"])
            partida = _disputar(
                jogo, clubes[jogo["mandante"]], clubes[jogo["visitante"]],
                ao_vivo if dele else None,
            )
            if dele:
                self.partida_usuario = partida
            clubes[jogo["vencedor"]].lancar("receita_premiacao", PREMIOS[fase])

        proxima = FASES.index(fase) + 1
        if proxima < len(FASES):
            vencedores = [j["vencedor"] for j in jogos]
            self.fases[FASES[proxima]] = [
                self._confronto(vencedores[i], vencedores[i + 1])
                for i in range(0, len(vencedores), 2)
            ]
        return jogos

    def _confronto(self, a, b):
        """Joga em casa quem foi melhor na liga; empate de seed (o 1º de uma
        liga contra o 1º da outra), quem vem antes na chave."""
        return _jogo(a, b) if self.seed[a] <= self.seed[b] else _jogo(b, a)


def campeao_de(dados):
    """O campeão de uma copa (`Copa.para_dict`), ou None."""
    final = (dados or {}).get("fases", {}).get("final")
    return final[0]["vencedor"] if final and final[0]["vencedor"] else None


def ate_onde(dados, clube):
    """Até onde o clube foi na copa: "campeao", a fase em que caiu (ou a
    que vai jogar, com a copa em andamento) ou None se não entrou."""
    if not dados or not any(clube in n for n in dados["classificados"].values()):
        return None
    if campeao_de(dados) == clube:
        return "campeao"
    alcancada = "oitavas"
    for fase in FASES:
        if any(clube in (j["mandante"], j["visitante"]) for j in dados["fases"].get(fase, [])):
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
    jogo["gols"] = [
        {k: e[k] for k in ("minuto", "jogador", "clube", "tipo")}
        for e in partida.resumo_eventos()
        if e["tipo"] in ("gol", "penalti")
    ]
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
