"""As copas (v1.6; v2.6, a continental com as 4 ligas e as nacionais)."""

import contextlib
import io
import json
import random

import pytest

from app.domain import copa
from app.domain.partida import Partida
from scripts.data_loader import TODAS_AS_LIGAS, carregar_campeonato

DUAS = ("taldo", "premier")
C = copa.CONTINENTAL


def _classificados(camp):
    """Cada liga na ordem da seed (basta para testar)."""
    return {liga: [c.nome for c in camp.clubes_da_liga(liga)] for liga in camp.ligas}


def _continental(camp):
    return camp.copa.copa(C)


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
        c = _continental(camp)
        jogos_por_rodada[rodada] = sum(
            len(c.fases[fase]) for fase in c.ordem if c.datas[fase] == rodada
        )
    return camp, premios_copa, jogos_por_rodada


def test_com_uma_liga_nao_tem_copa():
    camp = carregar_campeonato()
    assert camp.iniciar_copa({"taldo": ["a"] * 8, "x": ["b"] * 8}) is None
    assert _quieto(camp.jogar_rodada) is None and camp.copa is None


def test_oitavas_sempre_entre_as_ligas_e_os_primeiros_so_na_final():
    camp = carregar_campeonato(DUAS)
    c = camp.iniciar_copa(_classificados(camp)).copa(C)
    assert len(camp.copa) == 1 and c.ordem == ["oitavas", "quartas", "semi", "final"]
    liga = {cl.nome: cl.liga for cl in camp.clubes}
    oitavas = c.fases["oitavas"]
    times = [n for j in oitavas for n in (j["mandante"], j["visitante"])]
    assert len(set(times)) == 16
    assert all(liga[j["mandante"]] != liga[j["visitante"]] for j in oitavas)
    # quem foi melhor na liga joga em casa
    assert all(c.seed[j["mandante"]] < c.seed[j["visitante"]] for j in oitavas)
    # os dois 1º (seeds 1 e 2) em metades diferentes da chave
    primeiros = {n for n, s in c.seed.items() if s <= 2}
    metade = [{n for j in oitavas[i:i + 4] for n in (j["mandante"], j["visitante"])}
              for i in (0, 4)]
    assert all(len(primeiros & m) == 1 for m in metade)


def test_a_copa_joga_nas_datas_e_tem_campeao(temporada_com_copa):
    camp, _, jogos_por_rodada = temporada_com_copa
    assert len(camp.calendario) == 38          # a liga não muda
    assert {r: n for r, n in jogos_por_rodada.items() if n} == {12: 8, 19: 4, 26: 2, 34: 1}
    c = _continental(camp)
    final = c.fases["final"][0]
    assert camp.copa.campeao == c.campeao == final["vencedor"]
    for fase in c.ordem:
        for jogo in c.fases[fase]:
            assert jogo["vencedor"] in (jogo["mandante"], jogo["visitante"])
            if jogo["penaltis"]:
                assert jogo["gols_mandante"] == jogo["gols_visitante"]
                assert jogo["penaltis"][0] != jogo["penaltis"][1]
            gols = jogo["gols_mandante"] + jogo["gols_visitante"]
            assert len(jogo["gols"]) == gols


def test_cada_vitoria_paga_o_premio_da_fase(temporada_com_copa):
    camp, premios_copa, _ = temporada_com_copa
    c = _continental(camp)
    valores = copa.PREMIOS[C]
    assert premios_copa[c.campeao] == sum(valores[f] for f in c.ordem)
    assert sum(premios_copa.values()) == sum(valores[f] * len(c.fases[f]) for f in c.ordem)


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
    volta = copa.Copas.de_dict(dados)
    assert volta.para_dict() == camp.copa.para_dict()
    assert volta.campeao == camp.copa.campeao


def test_a_fase_seguinte_e_montada_ao_terminar_a_anterior():
    random.seed(2)
    camp = carregar_campeonato(DUAS)
    c = camp.iniciar_copa(_classificados(camp)).copa(C)
    _quieto(c.jogar_fase, "oitavas", {cl.nome: cl for cl in camp.clubes})
    quartas = c.fases["quartas"]
    vencedores = [j["vencedor"] for j in c.fases["oitavas"]]
    assert [{j["mandante"], j["visitante"]} for j in quartas] == [
        set(vencedores[i:i + 2]) for i in range(0, 8, 2)
    ]
    assert all(j["vencedor"] is None for j in quartas)
    # jogar de novo a mesma fase não faz nada
    assert _quieto(c.jogar_fase, "oitavas", {cl.nome: cl for cl in camp.clubes}) == []


def test_snapshot_leva_a_copa_e_save_antigo_fica_sem():
    from app.domain.temporada import restaurar_estado, snapshot_estado

    random.seed(4)
    camp = carregar_campeonato(DUAS)
    camp.iniciar_copa(copa.classificados_de_inicio(camp))
    for _ in range(8):
        _quieto(camp.jogar_rodada)
    blob = json.loads(json.dumps(snapshot_estado(camp)))

    volta = carregar_campeonato(DUAS)
    restaurar_estado(volta, blob)
    assert volta.copa.para_dict() == camp.copa.para_dict()

    del blob["copa"]
    antigo = carregar_campeonato(DUAS)
    restaurar_estado(antigo, blob)
    assert antigo.copa is None


def test_classificados_de_inicio_premier_pela_tabela_real_taldo_pela_forca():
    from app.domain import diretoria

    camp = carregar_campeonato(DUAS)
    c = copa.classificados_de_inicio(camp)
    assert c["premier"][:4] == ["Manchester City", "Arsenal", "Liverpool", "Aston Villa"]
    forca = diretoria.ranking_de_forca(camp.clubes_da_liga("taldo"))
    assert [forca[n] for n in c["taldo"]] == list(range(1, 21))


def test_ate_onde_cada_clube_foi(temporada_com_copa):
    camp, _, _ = temporada_com_copa
    dados = camp.copa.para_dict()
    fases = copa.copa_de(dados, C)["fases"]
    campeao = copa.campeao_de(dados)
    assert copa.ate_onde(dados, campeao) == "campeao"
    vice = next(n for n in (fases["final"][0]["mandante"],
                            fases["final"][0]["visitante"]) if n != campeao)
    assert copa.ate_onde(dados, vice) == "final"
    caiu_nas_oitavas = next(j for j in fases["oitavas"])
    perdedor = ({caiu_nas_oitavas["mandante"], caiu_nas_oitavas["visitante"]}
                - {caiu_nas_oitavas["vencedor"]}).pop()
    assert copa.ate_onde(dados, perdedor) == "oitavas"
    fora = next(c.nome for c in camp.clubes
                if not any(c.nome in n for n in copa.copa_de(dados, C)["classificados"].values()))
    assert copa.ate_onde(dados, fora) is None
    assert copa.ate_onde(None, campeao) is None and copa.campeao_de(None) is None


def test_penaltis_guardam_as_cobrancas():
    random.seed(3)
    camp = carregar_campeonato(DUAS)
    a, b = camp.clubes_da_liga("taldo")[0], camp.clubes_da_liga("premier")[0]
    partida = Partida(a, b)
    _quieto(partida.simular_partida)
    for _ in range(50):
        placar = copa.disputa_de_penaltis(partida)
        assert [sum(c["gol"] for c in partida.cobrancas if c["lado"] == lado)
                for lado in (1, 2)] == placar
        # alternadas, começando pelo mandante
        assert [c["lado"] for c in partida.cobrancas[:2]] == [1, 2]


def test_copa_adiada_para_o_jogo_do_tecnico():
    """Com `adiar_copa`, a fase em que o técnico joga espera; jogada à
    parte, as decisões dele valem só no jogo dele."""
    random.seed(7)
    camp = carregar_campeonato(DUAS)
    c = camp.iniciar_copa(_classificados(camp)).copa(C)
    meu = c.fases["oitavas"][0]["mandante"]
    while camp.rodada < c.datas["oitavas"]:
        _quieto(camp.jogar_rodada)
    _quieto(lambda: camp.jogar_rodada(meu, adiar_copa=True))
    assert camp.copa_adiada == "continental:oitavas"
    assert all(j["vencedor"] is None for j in c.fases["oitavas"])

    from app.domain.temporada import restaurar_estado, snapshot_estado
    foto = json.loads(json.dumps(snapshot_estado(camp)))

    def jogar(decisoes):
        outro = carregar_campeonato(DUAS)
        restaurar_estado(outro, foto)
        _quieto(lambda: outro.jogar_copa_adiada("continental:oitavas", meu, decisoes))
        return outro.copa.fases["continental:oitavas"], outro.partida_usuario

    jogos, partida = jogar([])
    assert all(j["vencedor"] for j in jogos) and partida.clube1.nome == meu
    assert jogar([])[0] == jogos   # determinística a partir do snapshot
    mudou, _ = jogar([{"minuto": 1, "clube": meu, "tatica": "ofensivo"}])
    # os outros jogos da fase não mudam com a decisão do técnico
    assert mudou[1:] == jogos[1:]


def test_sem_o_tecnico_na_fase_a_copa_nao_espera():
    random.seed(8)
    camp = carregar_campeonato(DUAS)
    c = camp.iniciar_copa(_classificados(camp)).copa(C)
    fora = next(cl.nome for cl in camp.clubes
                if all(cl.nome not in (j["mandante"], j["visitante"]) for j in c.fases["oitavas"]))
    while camp.rodada <= c.datas["oitavas"]:
        _quieto(lambda: camp.jogar_rodada(fora, adiar_copa=True))
    assert camp.copa_adiada is None and all(j["vencedor"] for j in c.fases["oitavas"])



# --- v2.6: as 4 ligas e as copas nacionais -----------------------------------

@pytest.fixture(scope="module")
def oito_ligas():
    random.seed(11)
    camp = carregar_campeonato(TODAS_AS_LIGAS)
    camp.iniciar_copa(copa.classificados_de_inicio(camp))
    return camp


def test_com_as_8_ligas_sao_a_continental_e_4_nacionais(oito_ligas):
    camp = oito_ligas
    assert [c.id for c in camp.copa] == [C, "taldo", "inglaterra", "espanha", "brasil"]
    assert camp.copa.copa("brasil").nome == "Copa do Brasil"
    for c in camp.copa:
        assert len(c.seed) == 32 and c.ordem == copa.FASES_TODAS
    # as nacionais jogam juntas, em quartas sem a continental
    nacionais = {r for c in camp.copa if c.tipo == "nacional" for r in c.datas.values()}
    assert not nacionais & set(camp.copa.copa(C).datas.values())


def test_continental_tem_8_de_cada_serie_a_sem_jogo_da_mesma_liga(oito_ligas):
    camp = oito_ligas
    c = camp.copa.copa(C)
    liga = {cl.nome: cl.liga for cl in camp.clubes}
    assert {l: len(n) for l, n in c.classificados.items()} == {
        "taldo": 8, "premier": 8, "laliga": 8, "brasileirao": 8}
    assert all(liga[j["mandante"]] != liga[j["visitante"]] for j in c.fases["16-avos"])
    assert all(c.seed[j["mandante"]] < c.seed[j["visitante"]] for j in c.fases["16-avos"])


def test_nacional_tem_os_20_da_a_e_os_12_melhores_da_b(oito_ligas):
    camp = oito_ligas
    c = camp.copa.copa("brasil")
    assert len(c.classificados["brasileirao"]) == 20
    assert len(c.classificados["brasileirao_b"]) == 12
    # os da A têm seed melhor que os da B
    assert max(c.seed[n] for n in c.classificados["brasileirao"]) == 20


def test_na_virada_quem_caiu_vem_antes_dos_da_b():
    random.seed(12)
    camp = carregar_campeonato(TODAS_AS_LIGAS)
    ordem = _classificados(camp)
    # o 20º do Brasileirão cai e o 1º da B sobe
    caiu, subiu = ordem["brasileirao"][-1], ordem["brasileirao_b"][0]
    for cl in camp.clubes:
        if cl.nome == caiu:
            cl.liga = "brasileirao_b"
        elif cl.nome == subiu:
            cl.liga = "brasileirao"
    camp.reorganizar_ligas()
    c = camp.iniciar_copa(ordem).copa("brasil")
    assert subiu in c.classificados["brasileirao"]
    assert c.classificados["brasileirao_b"][0] == caiu


def test_cada_quarta_joga_as_fases_de_todas_as_copas_e_adia_so_a_do_tecnico(oito_ligas):
    from app.domain.temporada import restaurar_estado, snapshot_estado

    camp = carregar_campeonato(TODAS_AS_LIGAS)
    restaurar_estado(camp, json.loads(json.dumps(snapshot_estado(oito_ligas))))
    meu = camp.copa.copa("brasil").fases["16-avos"][0]["mandante"]
    while camp.rodada < 3:
        _quieto(camp.jogar_rodada)
    _quieto(lambda: camp.jogar_rodada(meu, adiar_copa=True))
    assert camp.copa_adiada == "brasil:16-avos"
    for c in camp.copa:
        if c.tipo == "nacional":
            jogada = all(j["vencedor"] for j in c.fases["16-avos"])
            assert jogada == (c.id != "brasil")
    _quieto(lambda: camp.jogar_copa_adiada("brasil:16-avos", meu))
    assert all(j["vencedor"] for j in camp.copa.copa("brasil").fases["16-avos"])
    assert camp.copa.fase_da_rodada(3, meu) == "brasil:16-avos"


def test_copa_de_save_antigo_vira_a_continental():
    """O dict de antes da v2.6 (uma copa, Taldo x Premier) ainda é lido."""
    antigo = {
        "classificados": {"taldo": [f"T{i}" for i in range(1, 9)],
                          "premier": [f"P{i}" for i in range(1, 9)]},
        "fases": {"oitavas": [copa._jogo("T1", "P8")]},
    }
    c = copa.Copas.de_dict(antigo).copa(C)
    assert c.datas == copa.DATAS_V1 and c.seed["T1"] == c.seed["P1"] == 1
    assert copa.rodada_da_chave(antigo, "oitavas") == 8
    assert copa.dividir("oitavas") == (C, "oitavas")
    assert copa.nome_da_chave(antigo, "oitavas") == "Copa entre as ligas · Oitavas de final"


def test_premio_da_nacional_segue_o_peso_do_pais_e_a_continental_e_igual():
    """v2.6: a nacional paga pelo peso da Série A do país, como a liga; a
    continental, igual para todos (o campeão soma 19 mi)."""
    total = lambda cid: sum(copa.premios(2, "nacional", cid).values())
    assert total("inglaterra") == 8_100_000
    assert total("brasil") == 3_240_000 and total("taldo") == 6_480_000
    assert sum(copa.premios(2).values()) == 19_000_000
