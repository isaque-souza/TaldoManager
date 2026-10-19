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
from app.services import (
    estadio_service, mensagem_service, simulacao_service, temporada_service,
)
from app.services.estadio_service import IngressoInvalido, ObraInvalida
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


# ---------------------------------------------------------------------------
# ampliação
# ---------------------------------------------------------------------------

def test_custo_da_obra_segue_o_preco_do_ingresso():
    # a obra se paga no mesmo número de jogos lotados em qualquer clube
    for tipo, o in estadio.OBRAS.items():
        jogos = [
            estadio.custo_da_obra(tipo, t) / (o["lugares"] * estadio.preco_normal(t))
            for t in (500_000, 3_000_000, 12_000_000)
        ]
        assert jogos == pytest.approx([o["jogos"]] * 3, rel=0.01)
    # obra maior: mais cara no total, mais barata por lugar
    custo = {t: estadio.custo_da_obra(t, 3_000_000) for t in estadio.OBRAS}
    assert custo["pequena"] < custo["media"] < custo["grande"]
    assert (custo["grande"] / 20_000 < custo["media"] / 10_000
            < custo["pequena"] / 5_000)


def test_obra_bloqueada():
    casa = _clube()
    assert estadio.motivo_obra_bloqueada(casa, "gigante") == "Obra desconhecida"
    casa.dinheiro = 0
    assert "caixa" in estadio.motivo_obra_bloqueada(casa, "pequena")
    casa.dinheiro = 10**9
    assert estadio.motivo_obra_bloqueada(casa, "pequena") is None
    estadio.iniciar_obra(casa, "pequena")
    assert "andamento" in estadio.motivo_obra_bloqueada(casa, "media")


def test_obra_paga_a_vista_e_fica_pronta_no_prazo():
    casa = _clube(capacidade=30_000)
    custo = estadio.iniciar_obra(casa, "pequena")
    assert casa.dinheiro == 10_000_000 - custo
    assert casa.despesa_estadio == custo

    for _ in range(estadio.OBRAS["pequena"]["rodadas"] - 1):
        assert estadio.avancar_obra(casa) == 0
    assert casa.capacidade == 30_000           # ainda no canteiro
    assert estadio.avancar_obra(casa) == 5_000
    assert casa.capacidade == 35_000 and casa.lugares_ampliados == 5_000
    assert (casa.obra_lugares, casa.obra_rodadas) == (0, 0)
    assert estadio.avancar_obra(casa) == 0     # sem obra, nada muda


def test_manutencao_so_dos_lugares_ampliados():
    casa, fora = _clube(capacidade=30_000), _clube("Fora")
    assert estadio.manutencao(casa) == 0
    financas.processar_rodada([(casa, fora)], 38)
    assert casa.despesa_estadio == 0

    casa.lugares_ampliados = 10_000
    esperado = round(10_000 * estadio.preco_normal(casa.torcedores)
                     * estadio.MANUTENCAO_POR_LUGAR)
    assert estadio.manutencao(casa) == esperado
    financas.processar_rodada([(casa, fora)], 38)
    assert casa.despesa_estadio == esperado
    financas.processar_rodada([(fora, casa)], 38)   # fora de casa não paga
    assert casa.despesa_estadio == esperado


def test_obra_anda_a_cada_rodada_jogada():
    random.seed(5)
    camp = carregar_campeonato()
    clube = camp.clubes[0]
    clube.dinheiro = 10**9
    capacidade = clube.capacidade
    estadio.iniciar_obra(clube, "pequena")
    with redirect_stdout(io.StringIO()):
        for _ in range(estadio.OBRAS["pequena"]["rodadas"]):
            camp.jogar_rodada()
    assert clube.capacidade == capacidade + 5_000
    assert clube.obra_lugares == 0


def test_snapshot_guarda_a_obra():
    camp = carregar_campeonato()
    c = camp.clubes[0]
    c.obra_lugares, c.obra_rodadas, c.lugares_ampliados, c.despesa_estadio = (
        10_000, 7, 5_000, 123
    )
    blob = snapshot_estado(camp)
    estado = random.getstate()
    try:
        novo = carregar_campeonato()
        restaurar_estado(novo, blob)
    finally:
        random.setstate(estado)
    n = novo.clubes[0]
    assert (n.obra_lugares, n.obra_rodadas, n.lugares_ampliados, n.despesa_estadio) == (
        10_000, 7, 5_000, 123
    )


def test_obra_segue_na_temporada_seguinte():
    from app.domain.carreira import preparar_nova_temporada

    camp = carregar_campeonato()
    finais = [{
        "nome": c.nome, "dinheiro": c.dinheiro, "torcedores": c.torcedores,
        "capacidade": c.capacidade + 5_000, "ingresso": "normal",
        "obra_lugares": 20_000, "obra_rodadas": 12, "lugares_ampliados": 5_000,
    } for c in camp.clubes]
    jogadores = [{
        "nome": j.nome, "clube": c.nome, "idade": j.idade, "overall": j.overall,
        "potencial": j.potencial, "salario": j.salario,
        "contrato_anos": j.contrato_anos, "multa_rescisoria": j.multa_rescisoria,
    } for c in camp.clubes for j in c.jogadores]
    novo = preparar_nova_temporada(carregar_campeonato(), finais, jogadores)
    c = novo.clubes[0]
    assert (c.obra_lugares, c.obra_rodadas, c.lugares_ampliados) == (20_000, 12, 5_000)
    assert c.despesa_estadio == 0              # a despesa é da temporada


def test_iniciar_obra_pelo_servico():
    sid = _iniciar()
    e = estadio_service.ver(sid)
    assert [o["tipo"] for o in e["obras"]] == list(estadio.OBRAS)
    assert e["obra"] is None and e["lugares_ampliados"] == 0
    capacidade, caixa = e["capacidade"], e["caixa"]
    custo = e["obras"][0]["custo"]

    e = estadio_service.iniciar_obra(sid, "pequena")
    assert e["caixa"] == caixa - custo
    assert e["obra"] == {"tipo": "pequena", "nome": estadio.OBRAS["pequena"]["nome"],
                         "lugares": 5_000, "rodadas": 10, "faltam": 10}
    assert all(o["bloqueio"] for o in e["obras"])
    with pytest.raises(ObraInvalida):
        estadio_service.iniciar_obra(sid, "media")

    for _ in range(10):
        temporada_service.avancar(sid)
    e = estadio_service.ver(sid)
    assert e["obra"] is None
    assert e["capacidade"] == capacidade + 5_000
    assert e["lugares_ampliados"] == 5_000 and e["manutencao"] > 0

    assuntos = [m["assunto"] for m in mensagem_service.listar(sid)["mensagens"]]
    assert "Obra concluída" in assuntos
    assert any("obra começou" in a for a in assuntos)


def test_rota_da_obra():
    sid = _iniciar()
    r = client.post(f"/simulacoes/{sid}/estadio/obra", json={"tipo": "media"})
    assert r.status_code == 200 and r.json()["obra"]["faltam"] == 19

    r = client.post(f"/simulacoes/{sid}/estadio/obra", json={"tipo": "pequena"})
    assert r.status_code == 400 and "andamento" in r.json()["detail"]

    r = client.post(f"/simulacoes/{sid}/estadio/obra", json={"tipo": "gigante"})
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# a CPU amplia (virada)
# ---------------------------------------------------------------------------

def _clube_cpu(capacidade=20_000, dinheiro=50_000_000, torcedores=3_000_000):
    clube = _clube(capacidade=capacidade, torcedores=torcedores)
    clube.dinheiro = dinheiro
    return clube


def test_cpu_so_amplia_quando_lota():
    clube = _clube_cpu()
    assert estadio.obra_da_cpu(clube, estadio.LOTADOS_PARA_AMPLIAR - 1) is None
    assert estadio.obra_da_cpu(clube, estadio.LOTADOS_PARA_AMPLIAR) is not None
    assert estadio.obra_da_cpu(_clube_cpu(capacidade=0), 19) is None   # sem estádio
    estadio.iniciar_obra(clube, "pequena")
    assert estadio.obra_da_cpu(clube, 19) is None                       # já em obra


def test_cpu_constroi_o_que_falta_para_o_classico():
    classico = estadio.demanda_base(3_000_000) * estadio.MULT_CLASSICO
    assert estadio.obra_da_cpu(_clube_cpu(capacidade=round(classico) - 25_000), 19) == "grande"
    assert estadio.obra_da_cpu(_clube_cpu(capacidade=round(classico) - 12_000), 19) == "media"
    # falta pouco: ainda lota, então a pequena
    assert estadio.obra_da_cpu(_clube_cpu(capacidade=round(classico) - 1_000), 19) == "pequena"


def test_cpu_nao_se_endivida_com_obra():
    classico = estadio.demanda_base(3_000_000) * estadio.MULT_CLASSICO
    clube = _clube_cpu(capacidade=round(classico) - 25_000)
    custo = {t: estadio.custo_da_obra(t, clube.torcedores) for t in estadio.OBRAS}
    # sem folha: dá para a média, não para a grande → faz a média
    clube.dinheiro = custo["media"] + 1
    assert estadio.obra_da_cpu(clube, 19) == "media"
    clube.dinheiro = custo["pequena"] - 1
    assert estadio.obra_da_cpu(clube, 19) is None


def test_cpu_amplia_menos_o_clube_do_tecnico():
    camp = carregar_campeonato()
    lotados = {c.nome: 19 for c in camp.clubes}
    usuario = camp.clubes[0].nome
    obras = estadio.cpu_amplia(camp, lotados, usuario)
    assert obras and usuario not in {c.nome for c, _ in obras}
    assert camp.clubes[0].obra_lugares == 0
    for clube, tipo in obras:
        assert clube.obra_lugares == estadio.OBRAS[tipo]["lugares"]
        assert clube.despesa_estadio == estadio.custo_da_obra(tipo, clube.torcedores)


def test_virada_poe_a_cpu_para_ampliar(cargo_garantido):
    from app.services import carreira_service

    sid = simulacao_service.salvar_temporada(seed=3, clube_usuario="Real Taldo")
    nova = carreira_service.proxima_temporada(sid)["simulacao_id"]
    from app.db.conexao import conectar
    from app.repositories import clube_repository

    conn = conectar()
    try:
        clubes = [dict(c) for c in clube_repository.listar_por_simulacao(conn, nova)]
    finally:
        conn.close()
    em_obra = [c for c in clubes if c["obra_lugares"]]
    assert em_obra, "nenhum clube da CPU ampliou"
    assert "Real Taldo" not in {c["nome"] for c in em_obra}
    assuntos = [m["assunto"] for m in mensagem_service.listar(nova)["mensagens"]]
    assert "Obras na liga" in assuntos
