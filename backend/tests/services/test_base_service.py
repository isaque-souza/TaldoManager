"""Categorias de base do técnico (v2.0): a base inicial, a peneira que o
técnico faz a cada 90 dias, o treino a cada rodada, promover, dispensar, o
nível e a virada."""

import random
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.db.conexao import conectar
from app.domain import base
from app.domain.base import Jovem
from app.main import app
from app.repositories import jovem_base_repository as jovem_repo
from app.repositories import simulacao_repository as simulacao_repo
from app.services import base_service, mensagem_service, temporada_service
from app.services.base_service import AcaoInvalida

client = TestClient(app)


def _iniciar(seed=11):
    return temporada_service.iniciar(seed=seed, clube_usuario="Real Taldo")


def _no_dia(sid, dia):
    conn = conectar()
    try:
        with conn:
            simulacao_repo.definir_data(conn, sid, dia)
    finally:
        conn.close()


# --- domínio ---

def test_crescer_soma_na_temporada_a_fracao_do_nivel():
    for nivel in base.NIVEIS:
        j = Jovem("X", 16, "Zagueiro", 60.0, 80)
        for _ in range(38):
            base.crescer(j, nivel, 38)
        esperado = 60 + 20 * base.CRESCIMENTO_TEMPORADA * base.NIVEIS[nivel][2]
        assert j.overall == pytest.approx(esperado)
    # e nunca passa do potencial
    j = Jovem("Y", 16, "Zagueiro", 79.9, 80)
    base.crescer(j, 5, 1)
    assert j.overall <= 80


def test_nivel_maior_cresce_mais():
    finais = []
    for nivel in base.NIVEIS:
        j = Jovem("X", 16, "Ponta", 60.0, 85)
        for _ in range(38):
            base.crescer(j, nivel, 38)
        finais.append(j.overall)
    assert finais == sorted(finais) and finais[0] < finais[-1]


def test_peneira_respeita_as_vagas_e_o_nivel():
    rng = random.Random(1)
    for _ in range(50):
        ficam, de_fora = base.quantos_na_peneira(13, 5, rng)
        assert ficam <= 2 and ficam + de_fora >= base.NIVEIS[5][4][0]
    assert base.quantos_na_peneira(base.VAGAS, 1, rng)[0] == 0
    for nivel, (*_, (minimo, maximo)) in base.NIVEIS.items():
        for _ in range(30):
            assert minimo <= base.quantos_na_peneira(0, nivel, rng)[0] <= maximo


def test_peneira_bloqueada_ate_passarem_90_dias_ou_com_a_base_cheia():
    hoje = date(2026, 9, 1)
    assert base.motivo_peneira_bloqueada(None, hoje, 0) is None
    assert "89 dias" in base.motivo_peneira_bloqueada(date(2026, 8, 31), hoje, 0)
    assert base.motivo_peneira_bloqueada(hoje - timedelta(days=90), hoje, 0) is None
    assert "cheia" in base.motivo_peneira_bloqueada(None, hoje, base.VAGAS)


def test_clube_do_tecnico_so_ganha_jovens_gerados_abaixo_do_minimo():
    from scripts.data_loader import carregar_campeonato
    clube = carregar_campeonato().clubes[0]
    del clube.jogadores[20:]
    assert base.quantos_sobem(clube) == 3                   # a CPU completa até 23
    assert base.quantos_sobem(clube, do_tecnico=True) == 0
    del clube.jogadores[14:]
    assert base.quantos_sobem(clube, do_tecnico=True) == 2  # até ELENCO_MIN (16)


def test_ultimo_ano_e_envelhecer():
    j = Jovem("X", 19, "Volante", 70.5, 80)
    assert base.ultimo_ano(j)
    base.envelhecer(j, random.Random(3))
    assert j.idade == 20 and j.overall <= j.potencial


# --- serviço ---

def test_jogo_novo_comeca_com_a_base_inicial_e_a_peneira_liberada():
    dados = base_service.ver(_iniciar())
    assert len(dados["jovens"]) == base.JOVENS_INICIAIS
    assert all(base.IDADE_INICIAL[0] <= j["idade"] <= base.IDADE_INICIAL[1] for j in dados["jovens"])
    assert dados["nivel"] == 1
    assert dados["peneira"]["bloqueio"] is None and dados["peneira"]["liberada_em"] is None
    assert dados["peneira"]["por_peneira"] == list(base.NIVEIS[1][4])


def test_fazer_peneira_e_esperar_90_dias_pela_proxima():
    sid = _iniciar()
    feita = base_service.fazer_peneira(sid)
    minimo, maximo = base.NIVEIS[1][4]
    assert minimo <= len(feita["novos"]) <= maximo
    dados = feita["base"]
    assert len(dados["jovens"]) == base.JOVENS_INICIAIS + len(feita["novos"])
    novos = [j for j in dados["jovens"] if j["nome"] in feita["novos"]]
    assert all(base.IDADE_PENEIRA[0] <= j["idade"] <= base.IDADE_PENEIRA[1] for j in novos)
    assert "90 dias" in dados["peneira"]["bloqueio"]
    assert dados["peneira"]["liberada_fmt"]

    with pytest.raises(AcaoInvalida, match="só em"):
        base_service.fazer_peneira(sid)
    inicio = date.fromisoformat(dados["peneira"]["liberada_em"]) - timedelta(days=90)
    _no_dia(sid, inicio + timedelta(days=89))
    with pytest.raises(AcaoInvalida):
        base_service.fazer_peneira(sid)
    _no_dia(sid, inicio + timedelta(days=90))
    assert base_service.fazer_peneira(sid)["novos"]

    assuntos = [m["assunto"] for m in mensagem_service.listar(sid)["mensagens"]
                if m["setor"] == "Categorias de base"]
    assert assuntos == ["Peneira: jovens novos na base"] * 2


def test_nivel_alto_traz_mais_jovens_na_peneira():
    sid = _iniciar()
    base_service.trocar_nivel(sid, 5)
    assert len(base_service.fazer_peneira(sid)["novos"]) >= base.NIVEIS[5][4][0]


def test_peneira_com_a_base_cheia_e_recusada():
    sid = _iniciar()
    conn = conectar()
    try:
        with conn:
            jovem_repo.inserir(conn, sid, [
                Jovem(f"Enchedor {i}", 16, "Zagueiro", 60.0, 70)
                for i in range(base.VAGAS - base.JOVENS_INICIAIS)
            ], "2026-07-11")
    finally:
        conn.close()
    with pytest.raises(AcaoInvalida, match="cheia"):
        base_service.fazer_peneira(sid)


def test_peneira_e_a_base_nao_mexem_no_random_das_partidas():
    sid = _iniciar()
    estado = random.getstate()
    base_service.fazer_peneira(sid)
    base_service.promover(sid, base_service.ver(sid)["jovens"][0]["id"])
    assert random.getstate() == estado


def test_peneira_e_a_mesma_se_o_save_for_recarregado():
    a, b = _iniciar(seed=5), _iniciar(seed=5)
    assert base_service.fazer_peneira(a)["novos"] == base_service.fazer_peneira(b)["novos"]


def test_jovens_treinam_a_cada_rodada():
    sid = _iniciar()
    antes = {j["id"]: j["overall"] + j["progresso"] for j in base_service.ver(sid)["jovens"]}
    for _ in range(3):
        temporada_service.avancar(sid)
    depois = {j["id"]: j["overall"] + j["progresso"] for j in base_service.ver(sid)["jovens"]}
    assert all(depois[i] > antes[i] for i in antes)


def test_promover_leva_ao_elenco_com_contrato():
    sid = _iniciar()
    jovem = base_service.ver(sid)["jovens"][0]
    r = base_service.promover(sid, jovem["id"])
    assert r["jogador"] == jovem["nome"]
    assert jovem["id"] not in {j["id"] for j in r["base"]["jovens"]}

    conn = conectar()
    try:
        linha = conn.execute(
            "SELECT * FROM jogador WHERE simulacao_id = ? AND nome = ?", (sid, jovem["nome"]),
        ).fetchone()
    finally:
        conn.close()
    assert linha is not None and linha["livre"] == 0
    assert linha["contrato_anos"] == 3 and linha["formador"] == "Real Taldo"
    assert linha["overall"] == jovem["overall"] and linha["potencial"] == jovem["potencial"]


def test_promover_com_elenco_cheio_e_recusado(monkeypatch):
    sid = _iniciar()
    monkeypatch.setattr(base.mercado, "ELENCO_MAX", 1)
    with pytest.raises(AcaoInvalida, match="já tem"):
        base_service.promover(sid, base_service.ver(sid)["jovens"][0]["id"])


def test_dispensar_tira_da_base():
    sid = _iniciar()
    jovem = base_service.ver(sid)["jovens"][0]
    dados = base_service.dispensar(sid, jovem["id"])
    assert len(dados["jovens"]) == base.JOVENS_INICIAIS - 1
    assert base_service.dispensar(sid, jovem["id"]) is None


def test_jovem_de_outro_save_nao_atravessa():
    a, b = _iniciar(), _iniciar(seed=12)
    jovem_de_a = base_service.ver(a)["jovens"][0]["id"]
    assert base_service.promover(b, jovem_de_a) is None
    assert base_service.dispensar(b, jovem_de_a) is None
    assert client.post(f"/simulacoes/{b}/base/{jovem_de_a}/promover").status_code == 404
    assert client.delete(f"/simulacoes/{b}/base/{jovem_de_a}").status_code == 404


def test_trocar_nivel_cobra_a_diferenca():
    sid = _iniciar()
    caixa = base_service.ver(sid)["caixa"]
    dados = base_service.trocar_nivel(sid, 3)
    assert dados["nivel"] == 3
    assert dados["gasto_temporada"] == base.custo_temporada(3)   # rodada 1: a temporada toda
    assert dados["caixa"] == caixa - base.custo_temporada(3)
    # descer é de graça
    assert base_service.trocar_nivel(sid, 1)["caixa"] == dados["caixa"]
    with pytest.raises(AcaoInvalida):
        base_service.trocar_nivel(sid, 1)
    with pytest.raises(AcaoInvalida):
        base_service.trocar_nivel(sid, 9)


def test_virar_envelhece_e_quem_faz_20_vai_embora():
    de, para = _iniciar(), _iniciar(seed=12)
    conn = conectar()
    try:
        with conn:
            conn.execute("DELETE FROM jovem_base WHERE simulacao_id IN (?, ?)", (de, para))
            jovem_repo.inserir(conn, de, [
                Jovem("Velho Demais", 19, "Zagueiro", 70.0, 80),
                Jovem("Quase La", 18, "Ponta", 68.3, 82),
                Jovem("Novinho", 15, "Goleiro", 60.0, 78),
            ], "2027-03-01")
            msg = base_service.virar(conn, de, para, 11, 2)
        ficaram = {j.nome: j for j, _ in jovem_repo.listar(conn, para)}
    finally:
        conn.close()
    assert set(ficaram) == {"Quase La", "Novinho"}
    assert ficaram["Quase La"].idade == 19 and ficaram["Novinho"].idade == 16
    assert "Velho Demais" in msg["corpo"] and "Último ano na base: Quase La" in msg["corpo"]


def test_rotas_da_base():
    sid = _iniciar()
    assert client.get(f"/simulacoes/{sid}/base").status_code == 200
    assert client.post(f"/simulacoes/{sid}/base/peneira").status_code == 200
    assert client.post(f"/simulacoes/{sid}/base/peneira").status_code == 400
    assert client.post(f"/simulacoes/{sid}/base/nivel", json={"nivel": 7}).status_code == 400
    jovem = client.get(f"/simulacoes/{sid}/base").json()["jovens"][0]
    resp = client.post(f"/simulacoes/{sid}/base/{jovem['id']}/promover")
    assert resp.status_code == 200 and resp.json()["jogador"] == jovem["nome"]
    assert client.get("/simulacoes/9999/base").status_code == 404
