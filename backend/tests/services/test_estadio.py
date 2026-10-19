"""Estádio (v1.5): capacidade, público, ingresso, bilheteria e mando."""

import io
import random
from contextlib import redirect_stdout

import pytest
from fastapi.testclient import TestClient

from app.domain import estadio, financas, torcida
from app.domain.clube import Clube
from app.domain.partida import Partida
from app.domain.temporada import restaurar_estado, snapshot_estado
from app.main import app
from app.services import estadio_service, simulacao_service, temporada_service
from app.services.estadio_service import IngressoInvalido
from app.services.temporada_service import TemporadaConcluida
from scripts.data_loader import carregar_campeonato

client = TestClient(app)


def _clube(nome="Casa", torcedores=3_000_000, capacidade=40_000, forma=()):
    clube = Clube(nome, "Brasil", 10_000_000, torcedores)
    clube.capacidade = capacidade
    clube.forma = list(forma)
    return clube


# ---------------------------------------------------------------------------
# regras (domínio)
# ---------------------------------------------------------------------------

def test_demanda_cresce_com_a_torcida_mas_com_retorno_decrescente():
    pequena = estadio.demanda_base(1_000_000)
    grande = estadio.demanda_base(10_000_000)
    assert pequena < grande < 10 * pequena
    assert estadio.demanda_base(estadio.TORCIDA_REF) == pytest.approx(estadio.PUBLICO_REF)
    assert estadio.demanda_base(0) == 0


def test_publico_nao_passa_da_capacidade():
    casa = _clube(capacidade=1_000)
    assert estadio.publico(casa, _clube("Fora")) == 1_000
    folgado = _clube(capacidade=500_000)
    assert estadio.publico(folgado, _clube("Fora")) == round(estadio.demanda_base(3_000_000))


def test_sem_estadio_nao_ha_publico():
    assert estadio.publico(_clube(capacidade=0), _clube("Fora")) == 0
    assert estadio.publico_tipico(_clube(capacidade=0)) == 0


def test_classico_e_boa_fase_enchem_o_estadio():
    casa, fora, rival = _clube(capacidade=10**6), _clube("Fora"), _clube("Rival")
    casa.rivais = {"Rival"}
    comum = estadio.demanda(casa, fora)
    assert estadio.demanda(casa, rival) == pytest.approx(comum * estadio.MULT_CLASSICO)

    embalado = _clube(capacidade=10**6, forma="VVVVV")
    em_crise = _clube(capacidade=10**6, forma="DDDDD")
    assert estadio.demanda(em_crise, fora) < comum < estadio.demanda(embalado, fora)


def test_faixas_do_ingresso():
    casa, fora = _clube(capacidade=10**6), _clube("Fora")
    publico = {f: estadio.publico(casa, fora, f) for f in estadio.FAIXAS}
    preco = {f: estadio.preco(casa, f) for f in estadio.FAIXAS}
    assert publico["popular"] > publico["normal"] > publico["premium"]
    assert preco["popular"] < preco["normal"] < preco["premium"]


def test_premium_rende_mais_quando_o_estadio_lota():
    lotado = _clube(capacidade=5_000)   # todo mundo quer entrar
    fora = _clube("Fora")
    receita = {}
    for faixa in estadio.FAIXAS:
        lotado.ingresso = faixa
        receita[faixa] = estadio.bilheteria(lotado, estadio.publico(lotado, fora))
    assert receita["premium"] > receita["normal"] > receita["popular"]


def test_clube_grande_cobra_mais_e_a_bilheteria_segue_a_torcida():
    assert estadio.preco_normal(10_000_000) > estadio.preco_normal(1_000_000)
    # sem lotar, a receita por jogo é proporcional à torcida
    por_torcedor = [
        estadio.demanda_base(t) * estadio.preco_normal(t) / t
        for t in (300_000, 3_000_000, 12_000_000)
    ]
    assert por_torcedor == pytest.approx([por_torcedor[0]] * 3)


def test_capacidade_inicial_acompanha_a_torcida_e_nao_muda_entre_execucoes():
    assert estadio.capacidade_inicial("X", 10_000_000) > estadio.capacidade_inicial("X", 500_000)
    assert estadio.capacidade_inicial("Taldo FC", 600_000) == estadio.capacidade_inicial(
        "Taldo FC", 600_000
    )
    assert estadio.capacidade_inicial("Nanico", 1_000) == estadio.CAPACIDADE_PISO


def test_mando_cresce_com_o_publico():
    assert estadio.mando_de_campo(estadio.PUBLICO_MEIO) == pytest.approx(estadio.MANDO_BASE)
    assert estadio.mando_de_campo(5_000) < estadio.MANDO_BASE < estadio.mando_de_campo(60_000)
    assert estadio.mando_de_campo(10**7) == estadio.MANDO_MAX
    assert estadio.mando_de_campo(1) == estadio.MANDO_MIN
    assert estadio.mando_de_campo(0) == estadio.MANDO_BASE   # sem estádio


def test_partida_usa_o_publico_no_mando():
    casa, fora = _clube(), _clube("Fora")
    partida = Partida(casa, fora)
    sem_publico = partida.forca_em_campo(casa) - casa.calcular_forca()
    assert sem_publico == pytest.approx(torcida.mando_de_campo(casa.torcedores))
    partida.publico = 60_000
    com_publico = partida.forca_em_campo(casa) - casa.calcular_forca()
    assert com_publico == pytest.approx(estadio.mando_de_campo(60_000))


def test_bilheteria_pelo_publico_e_sem_estadio_pela_torcida():
    casa, fora = _clube(), _clube("Fora")
    financas.processar_rodada([(casa, fora)], 38, {"Casa": 20_000})
    assert casa.receita_bilheteria == estadio.bilheteria(casa, 20_000)

    sem = _clube(capacidade=0)
    financas.processar_rodada([(sem, fora)], 38, {})
    assert sem.receita_bilheteria == round(sem.torcedores * financas.BILHETERIA_POR_TORCEDOR)


# ---------------------------------------------------------------------------
# temporada e persistência
# ---------------------------------------------------------------------------

def _temporada(seed=7):
    random.seed(seed)
    campeonato = carregar_campeonato()
    with redirect_stdout(io.StringIO()):
        while campeonato.rodada <= len(campeonato.calendario):
            campeonato.jogar_rodada()
    return campeonato


def test_temporada_registra_o_publico_de_cada_jogo():
    camp = _temporada()
    cap = {c.nome: c.capacidade for c in camp.clubes}
    assert all(0 < p["publico"] <= cap[p["mandante"]] for p in camp.partidas_jogadas)
    assert all(c.receita_bilheteria > 0 for c in camp.clubes)


def test_estadio_nao_sorteia_nada():
    """O público muda o mando (e assim os jogos), mas não consome a
    sequência aleatória: o mesmo seed dá o mesmo campeonato."""
    a = [(c.nome, c.pontos, c.receita_bilheteria) for c in _temporada(11).classificacao()]
    b = [(c.nome, c.pontos, c.receita_bilheteria) for c in _temporada(11).classificacao()]
    assert a == b


def test_snapshot_guarda_o_estadio():
    camp = carregar_campeonato()
    camp.clubes[0].capacidade, camp.clubes[0].ingresso = 77_000, "premium"
    blob = snapshot_estado(camp)
    estado = random.getstate()
    try:
        novo = carregar_campeonato()
        restaurar_estado(novo, blob)
    finally:
        random.setstate(estado)
    assert (novo.clubes[0].capacidade, novo.clubes[0].ingresso) == (77_000, "premium")


# ---------------------------------------------------------------------------
# serviço e API
# ---------------------------------------------------------------------------

def _iniciar(clube="Real Taldo"):
    return temporada_service.iniciar(seed=11, clube_usuario=clube)


def test_ver_estadio():
    sid = _iniciar()
    e = estadio_service.ver(sid)
    assert e["capacidade"] > 0 and e["ingresso"] == "normal"
    assert [f["faixa"] for f in e["faixas"]] == list(estadio.FAIXAS)
    assert e["temporada"]["jogos_em_casa"] == 0


def test_trocar_ingresso_vale_nos_jogos_seguintes():
    sid = _iniciar()
    e = estadio_service.definir_ingresso(sid, "premium")
    assert e["ingresso"] == "premium"
    temporada_service.avancar(sid)
    temporada_service.avancar(sid)
    e = estadio_service.ver(sid)
    assert e["ingresso"] == "premium"   # seguiu no snapshot
    assert e["temporada"]["jogos_em_casa"] >= 1
    assert e["temporada"]["publico_medio"] > 0

    with pytest.raises(IngressoInvalido):
        estadio_service.definir_ingresso(sid, "vip")


def test_partida_salva_mostra_o_publico():
    sid = _iniciar()
    r = temporada_service.avancar(sid)
    pid = r["resultados"][0]["partida_id"]
    assert simulacao_service.detalhe_partida(sid, pid)["partida"]["publico"] > 0


def test_temporada_concluida_nao_tem_estadio():
    sid = simulacao_service.salvar_temporada(seed=3, clube_usuario="Real Taldo")
    with pytest.raises(TemporadaConcluida):
        estadio_service.ver(sid)


def test_rotas_do_estadio():
    sid = _iniciar()
    r = client.get(f"/simulacoes/{sid}/estadio")
    assert r.status_code == 200 and r.json()["ingresso"] == "normal"

    r = client.post(f"/simulacoes/{sid}/estadio/ingresso", json={"faixa": "popular"})
    assert r.status_code == 200 and r.json()["ingresso"] == "popular"

    r = client.post(f"/simulacoes/{sid}/estadio/ingresso", json={"faixa": "vip"})
    assert r.status_code == 400 and "desconhecida" in r.json()["detail"]

    assert client.get("/simulacoes/99999/estadio").status_code == 404
