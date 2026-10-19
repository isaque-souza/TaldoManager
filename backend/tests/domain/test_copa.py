"""Copa entre as ligas (v1.6)."""

import contextlib
import io
import json
import random

import pytest

from app.domain import copa
from app.domain.partida import Partida
from scripts.data_loader import carregar_campeonato

DUAS = ("taldo", "premier")


def _classificados(camp):
    """Os 8 primeiros de cada liga na ordem da seed (basta para testar)."""
    return {liga: [c.nome for c in camp.clubes_da_liga(liga)][:8] for liga in camp.ligas}


def _quieto(func, *args):
    with contextlib.redirect_stdout(io.StringIO()):
        return func(*args)


@pytest.fixture(scope="module")
def temporada_com_copa():
    random.seed(5)
    camp = carregar_campeonato(DUAS)
    camp.iniciar_copa(_classificados(camp))
    premios_antes = {c.nome: c.receita_premiacao for c in camp.clubes}
    jogos_por_rodada = {}
    while camp.rodada <= len(camp.calendario):
        rodada = camp.rodada
        # a premiação da liga só sai no fim: até a 35, o que entra é da copa
        if rodada == 36:
            premios_copa = {
                c.nome: c.receita_premiacao - premios_antes[c.nome] for c in camp.clubes
            }
        _quieto(camp.jogar_rodada)
        jogos_por_rodada[rodada] = sum(
            1 for fase, r in copa.DATAS.items() if r == rodada
            for _ in camp.copa.fases[fase]
        )
    return camp, premios_copa, jogos_por_rodada


def test_com_uma_liga_nao_tem_copa():
    camp = carregar_campeonato()
    assert camp.iniciar_copa({"taldo": ["a"] * 8, "x": ["b"] * 8}) is None
    assert _quieto(camp.jogar_rodada) is None and camp.copa is None


def test_oitavas_sempre_entre_as_ligas_e_os_primeiros_so_na_final():
    camp = carregar_campeonato(DUAS)
    c = camp.iniciar_copa(_classificados(camp))
    liga = {cl.nome: cl.liga for cl in camp.clubes}
    oitavas = c.fases["oitavas"]
    times = [n for j in oitavas for n in (j["mandante"], j["visitante"])]
    assert len(set(times)) == 16
    assert all(liga[j["mandante"]] != liga[j["visitante"]] for j in oitavas)
    # quem foi melhor na liga joga em casa
    assert all(c.seed[j["mandante"]] < c.seed[j["visitante"]] for j in oitavas)
    # os dois 1º em metades diferentes da chave
    primeiros = {n for n, s in c.seed.items() if s == 1}
    metade = [{n for j in oitavas[i:i + 4] for n in (j["mandante"], j["visitante"])}
              for i in (0, 4)]
    assert all(len(primeiros & m) == 1 for m in metade)


def test_a_copa_joga_nas_datas_e_tem_campeao(temporada_com_copa):
    camp, _, jogos_por_rodada = temporada_com_copa
    assert len(camp.calendario) == 38          # a liga não muda
    assert {r: n for r, n in jogos_por_rodada.items() if n} == {8: 8, 17: 4, 26: 2, 35: 1}
    final = camp.copa.fases["final"][0]
    assert camp.copa.campeao == final["vencedor"]
    for fase in copa.FASES:
        for jogo in camp.copa.fases[fase]:
            assert jogo["vencedor"] in (jogo["mandante"], jogo["visitante"])
            if jogo["penaltis"]:
                assert jogo["gols_mandante"] == jogo["gols_visitante"]
                assert jogo["penaltis"][0] != jogo["penaltis"][1]
            gols = jogo["gols_mandante"] + jogo["gols_visitante"]
            assert len(jogo["gols"]) == gols


def test_cada_vitoria_paga_o_premio_da_fase(temporada_com_copa):
    camp, premios_copa, _ = temporada_com_copa
    assert premios_copa[camp.copa.campeao] == sum(copa.PREMIOS.values())
    assert sum(premios_copa.values()) == sum(
        copa.PREMIOS[f] * len(camp.copa.fases[f]) for f in copa.FASES
    )


def test_a_liga_nao_ve_a_copa(temporada_com_copa):
    camp, _, _ = temporada_com_copa
    for clube in camp.clubes:
        assert clube.vitorias + clube.empates + clube.derrotas == 38
        assert sum(j.gols for j in clube.jogadores) <= clube.gols_marcados


def test_o_jogo_de_copa_devolve_os_numeros_menos_cansaco_e_lesao():
    random.seed(3)
    camp = carregar_campeonato(DUAS)
    a, b = camp.clubes_da_liga("taldo")[0], camp.clubes_da_liga("premier")[0]
    alvo = a.jogadores[0]
    alvo.jogos_suspensao = 0
    alvo.amarelos_ciclo = 4
    antes_clube = (a.pontos, a.vitorias, a.gols_marcados, list(a.forma))

    for _ in range(6):   # alguns jogos, para alguém se machucar e cansar
        jogo = copa._jogo(a.nome, b.nome)
        _quieto(copa._disputar, jogo, a, b)

    assert (a.pontos, a.vitorias, a.gols_marcados, list(a.forma)) == antes_clube
    assert all(j.gols == 0 and j.partidas == 0 and j.amarelos == 0 for j in a.jogadores)
    assert alvo.amarelos_ciclo == 4 and alvo.jogos_suspensao == 0
    assert any(j.energia < 100 for j in a.jogadores + b.jogadores)


def test_lesao_da_copa_fica_e_a_de_antes_nao_anda():
    random.seed(8)
    camp = carregar_campeonato(DUAS)
    a, b = camp.clubes_da_liga("taldo")[0], camp.clubes_da_liga("premier")[0]
    lesionado = a.jogadores[-1]
    lesionado.rodadas_lesao = 3
    for _ in range(10):
        _quieto(copa._disputar, copa._jogo(a.nome, b.nome), a, b)
    assert lesionado.rodadas_lesao == 3
    assert any(j.rodadas_lesao for j in a.jogadores + b.jogadores if j is not lesionado)


def test_penaltis_param_quando_nao_da_mais_para_alcancar():
    random.seed(1)
    camp = carregar_campeonato(DUAS)
    a, b = camp.clubes_da_liga("taldo")[0], camp.clubes_da_liga("premier")[0]
    partida = Partida(a, b)
    _quieto(partida.simular_partida)
    for _ in range(300):
        c1, c2 = copa.disputa_de_penaltis(partida)
        assert c1 != c2
        if max(c1, c2) > 5:          # alternadas: diferença de 1
            assert abs(c1 - c2) == 1
        else:
            assert min(c1, c2) <= 5 and abs(c1 - c2) <= 3


def test_a_copa_vai_e_volta_em_json(temporada_com_copa):
    camp, _, _ = temporada_com_copa
    dados = json.loads(json.dumps(camp.copa.para_dict()))
    volta = copa.Copa.de_dict(dados)
    assert volta.para_dict() == camp.copa.para_dict()
    assert volta.campeao == camp.copa.campeao


def test_a_fase_seguinte_e_montada_ao_terminar_a_anterior():
    random.seed(2)
    camp = carregar_campeonato(DUAS)
    c = camp.iniciar_copa(_classificados(camp))
    _quieto(c.jogar_fase, "oitavas", {cl.nome: cl for cl in camp.clubes})
    quartas = c.fases["quartas"]
    vencedores = [j["vencedor"] for j in c.fases["oitavas"]]
    assert [{j["mandante"], j["visitante"]} for j in quartas] == [
        set(vencedores[i:i + 2]) for i in range(0, 8, 2)
    ]
    assert all(j["vencedor"] is None for j in quartas)
    # jogar de novo a mesma fase não faz nada
    assert _quieto(c.jogar_fase, "oitavas", {cl.nome: cl for cl in camp.clubes}) == []
