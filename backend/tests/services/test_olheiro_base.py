"""Olheiros da base (v2.0, passo 5): as regiões, mandar um olheiro, os
relatórios mensais, os indicados (trazer e descartar) e a virada."""

import random
from datetime import date, timedelta
from statistics import mean

import pytest
from fastapi.testclient import TestClient

from app.db.conexao import conectar
from app.domain import base, calendario, olheiro_base
from app.domain.base import Jovem
from app.main import app
from app.repositories import jovem_base_repository as jovem_repo
from app.repositories import olheiro_base_repository as repo
from app.repositories import simulacao_repository as simulacao_repo
from app.services import (
    base_service, calendario_service, carreira_service, mensagem_service,
    olheiro_base_service, temporada_service,
)
from app.services.base_service import AcaoInvalida

client = TestClient(app)

# a rodada 1 da temporada 1 é no sábado 8/8/2026: mandar o olheiro antes
# dela faz o primeiro relatório cair antes do jogo
ANTES_DO_JOGO = date(2026, 7, 1)


def _iniciar(seed=11):
    sid = temporada_service.iniciar(seed=seed, clube_usuario="Real Taldo")
    _no_dia(sid, ANTES_DO_JOGO)
    return sid


def _no_dia(sid, dia):
    conn = conectar()
    try:
        with conn:
            simulacao_repo.definir_data(conn, sid, dia)
    finally:
        conn.close()


def _entregar(sid, dia, rodada=1):
    conn = conectar()
    try:
        with conn:
            simulacao_repo.definir_data(conn, sid, dia)
            return olheiro_base_service.entregar(conn, sid, dia, rodada)
    finally:
        conn.close()


def _olheiros(sid):
    return base_service.ver(sid)["olheiros"]


# --- domínio ---

def _amostra(regiao, n=300, nivel=3):
    rng = random.Random(f"amostra:{regiao}")
    proibidos = set()
    return [olheiro_base.gerar_indicado(regiao, 80, nivel, proibidos, rng) for _ in range(n)]


def test_cada_regiao_tem_o_seu_perfil():
    europa, africa = _amostra("europa"), _amostra("africa")
    # a Europa manda jovens mais prontos; a África, mais espaço para crescer
    assert mean(j.overall for j in europa) > mean(j.overall for j in africa) + 4
    assert (mean(j.potencial - j.overall for j in africa)
            > mean(j.potencial - j.overall for j in europa) + 4)
    # posições típicas: a Europa manda mais goleiros que a média
    goleiros = sum(j.funcao == "Goleiro" for j in europa) / len(europa)
    assert goleiros > base.COMPOSICAO_IDEAL["Goleiro"] / sum(base.COMPOSICAO_IDEAL.values())


def test_nome_pais_e_idade_vem_da_regiao():
    for rid, r in olheiro_base.REGIOES.items():
        for j in _amostra(rid, n=40):
            nome, _, sobrenome = j.nome.partition(" ")
            assert nome in r["nomes"] and sobrenome in r["sobrenomes"]
            assert j.pais in r["paises"]
            assert r["idades"][0] <= j.idade <= r["idades"][1]
            assert j.overall <= j.potencial <= 99


def test_quantos_olheiros_pelo_nivel_da_base():
    assert [olheiro_base.limite(n) for n in range(1, 6)] == [1, 1, 2, 2, 3]
    bloqueio = olheiro_base.motivo_envio_bloqueado
    assert bloqueio("brasil", 1, [], 1, 10**9) is None
    assert "em missão" in bloqueio("europa", 1, ["brasil"], 1, 10**9)
    assert bloqueio("europa", 1, ["brasil"], 3, 10**9) is None
    assert "Já há um olheiro" in bloqueio("brasil", 1, ["brasil"], 3, 10**9)
    assert "caixa" in bloqueio("europa", 6, [], 1, 1000)
    assert olheiro_base.custo("europa", 6) == 6 * olheiro_base.REGIOES["europa"]["custo_mes"]


def test_regiao_e_duracao_invalidas():
    sid = _iniciar()
    with pytest.raises(AcaoInvalida, match="região"):
        olheiro_base_service.enviar(sid, "lua", 1)
    with pytest.raises(AcaoInvalida, match="1, 3 ou 6"):
        olheiro_base_service.enviar(sid, "brasil", 2)


# --- missões e relatórios ---

def test_enviar_cobra_a_missao_e_marca_o_primeiro_relatorio():
    sid = _iniciar()
    caixa = base_service.ver(sid)["caixa"]
    visao = olheiro_base_service.enviar(sid, "europa", 3)
    custo = olheiro_base.custo("europa", 3)
    assert visao["caixa"] == caixa - custo
    assert visao["gasto_temporada"] == custo
    [m] = visao["olheiros"]["missoes"]
    assert m["regiao"] == "Europa" and m["meses"] == 3 and m["relatorios_feitos"] == 0
    assert m["proximo_relatorio"] == (ANTES_DO_JOGO + timedelta(days=30)).isoformat()
    # nível 1 da base: um olheiro só
    with pytest.raises(AcaoInvalida, match="em missão"):
        olheiro_base_service.enviar(sid, "brasil", 1)


def test_continuar_para_no_dia_do_relatorio_e_chega_mensagem():
    sid = _iniciar()
    olheiro_base_service.enviar(sid, "brasil", 3)
    r = calendario_service.continuar(sid)
    assert r["data"] == (ANTES_DO_JOGO + timedelta(days=30)).isoformat()
    assert r["chegou_mensagem"]
    olheiros = _olheiros(sid)
    assert 1 <= len(olheiros["indicados"]) <= 3
    assert olheiros["missoes"][0]["relatorios_feitos"] == 1
    msg = mensagem_service.listar(sid)["mensagens"][0]
    assert msg["setor"] == "Olheiro da base" and msg["assunto"] == "Relatório do Brasil"
    assert "Mês 1 de 3" in msg["corpo"]


def test_indicados_somem_no_relatorio_seguinte_e_a_missao_acaba():
    sid = _iniciar()
    olheiro_base_service.enviar(sid, "asia", 3)
    primeiro = ANTES_DO_JOGO + timedelta(days=30)
    _entregar(sid, primeiro)
    nomes_1 = {i["nome"] for i in _olheiros(sid)["indicados"]}
    _entregar(sid, primeiro + timedelta(days=30))
    nomes_2 = {i["nome"] for i in _olheiros(sid)["indicados"]}
    assert nomes_1 and nomes_2 and not nomes_1 & nomes_2
    _entregar(sid, primeiro + timedelta(days=60))
    olheiros = _olheiros(sid)
    assert olheiros["missoes"] == []          # 3 relatórios: acabou
    assert "A missão acabou" in mensagem_service.listar(sid)["mensagens"][0]["corpo"]
    # o último relatório também vale 30 dias
    _entregar(sid, primeiro + timedelta(days=90))
    assert _olheiros(sid)["indicados"] == []


def test_relatorio_atrasado_entrega_todos_os_meses():
    sid = _iniciar()
    olheiro_base_service.enviar(sid, "africa", 3)
    entregues = _entregar(sid, ANTES_DO_JOGO + timedelta(days=75))
    assert entregues == ["África", "África"]
    assert _olheiros(sid)["missoes"][0]["relatorios_feitos"] == 2


def test_indicado_mostra_a_faixa_do_olheiro_profissional():
    sid = _iniciar()
    olheiro_base_service.enviar(sid, "brasil", 1)
    _entregar(sid, ANTES_DO_JOGO + timedelta(days=30))
    conn = conectar()
    try:
        reais = {j.nome: j.potencial for j, _ in repo.listar_indicados(conn, sid)}
    finally:
        conn.close()
    for i in _olheiros(sid)["indicados"]:
        minimo, maximo = i["potencial_faixa"]
        assert minimo <= reais[i["nome"]] <= maximo
        assert i["regiao"] == "Brasil" and i["pais"] == "Brasil"
        assert i["dias_restantes"] == 30


def test_trazer_leva_a_base_com_o_potencial_exato_e_o_pais():
    sid = _iniciar()
    olheiro_base_service.enviar(sid, "europa", 1)
    _entregar(sid, ANTES_DO_JOGO + timedelta(days=30))
    indicado = _olheiros(sid)["indicados"][0]
    r = olheiro_base_service.trazer(sid, indicado["id"])
    assert r["jovem"] == indicado["nome"]
    jovem = next(j for j in r["base"]["jovens"] if j["nome"] == indicado["nome"])
    assert jovem["pais"] == indicado["pais"]
    assert indicado["id"] not in {i["id"] for i in r["base"]["olheiros"]["indicados"]}


def test_trazer_com_a_base_cheia_e_recusado_e_descartar_tira_da_lista():
    sid = _iniciar()
    olheiro_base_service.enviar(sid, "asia", 1)
    _entregar(sid, ANTES_DO_JOGO + timedelta(days=30))
    conn = conectar()
    try:
        with conn:
            jovem_repo.inserir(conn, sid, [
                Jovem(f"Enchedor {i}", 16, "Zagueiro", 60.0, 70)
                for i in range(base.VAGAS - jovem_repo.contar(conn, sid))
            ], "2026-07-11")
    finally:
        conn.close()
    olheiros = _olheiros(sid)
    assert olheiros["bloqueio_trazer"]
    indicado = olheiros["indicados"][0]
    with pytest.raises(AcaoInvalida, match="cheia"):
        olheiro_base_service.trazer(sid, indicado["id"])
    visao = olheiro_base_service.descartar(sid, indicado["id"])
    assert indicado["id"] not in {i["id"] for i in visao["olheiros"]["indicados"]}


def test_indicado_de_outro_save_nao_atravessa():
    a, b = _iniciar(), _iniciar(seed=12)
    olheiro_base_service.enviar(a, "brasil", 1)
    _entregar(a, ANTES_DO_JOGO + timedelta(days=30))
    indicado = _olheiros(a)["indicados"][0]
    assert olheiro_base_service.trazer(b, indicado["id"]) is None
    assert olheiro_base_service.descartar(b, indicado["id"]) is None


def test_jogar_a_rodada_entrega_o_relatorio():
    sid = _iniciar()
    _no_dia(sid, date(2026, 7, 5))
    olheiro_base_service.enviar(sid, "brasil", 1)   # relatório em 4/8
    temporada_service.avancar(sid)                   # jogo em 8/8
    assert _olheiros(sid)["indicados"]


def test_olheiros_nao_mexem_no_random_e_repetem_no_mesmo_seed():
    a, b = _iniciar(seed=5), _iniciar(seed=5)
    estado = random.getstate()
    for sid in (a, b):
        olheiro_base_service.enviar(sid, "africa", 1)
        _entregar(sid, ANTES_DO_JOGO + timedelta(days=30))
    assert random.getstate() == estado
    nomes = [[i["nome"] for i in _olheiros(s)["indicados"]] for s in (a, b)]
    assert nomes[0] == nomes[1]


def test_virada_leva_missoes_e_indicados_sem_contar_as_ferias():
    sid = temporada_service.iniciar(seed=4, clube_usuario="Real Taldo")
    while not temporada_service.avancar(sid)["concluida"]:
        pass
    conn = conectar()
    try:
        sim = simulacao_repo.buscar(conn, sid)
        fim = calendario.data_atual(sim["temporada"], sim["rodadas"], sim["data_atual"])
        with conn:
            repo.inserir_missao(conn, sid, "europa", 3, fim.isoformat(),
                                (fim + timedelta(days=10)).isoformat(), 0)
            repo.inserir_indicados(conn, sid, "europa", [
                Jovem("Indicado Velho", 16, "Zagueiro", 60.0, 75, pais="França"),
            ], fim.isoformat(), (fim + timedelta(days=20)).isoformat())
    finally:
        conn.close()
    nova = carreira_service.proxima_temporada(sid)["simulacao_id"]
    inicio = calendario.inicio(2)
    olheiros = _olheiros(nova)
    assert olheiros["missoes"][0]["proximo_relatorio"] == (inicio + timedelta(days=10)).isoformat()
    [indicado] = olheiros["indicados"]
    assert indicado["nome"] == "Indicado Velho"
    assert indicado["expira_em"] == (inicio + timedelta(days=20)).isoformat()


def test_rotas_dos_olheiros_da_base():
    sid = _iniciar()
    url = f"/simulacoes/{sid}/base"
    assert client.post(f"{url}/olheiros", json={"regiao": "lua", "meses": 1}).status_code == 400
    resp = client.post(f"{url}/olheiros", json={"regiao": "brasil", "meses": 1})
    assert resp.status_code == 200 and resp.json()["olheiros"]["missoes"]
    assert client.post(f"{url}/olheiros", json={"regiao": "asia", "meses": 1}).status_code == 400
    _entregar(sid, ANTES_DO_JOGO + timedelta(days=30))
    a = client.get(url).json()["olheiros"]["indicados"][0]
    resp = client.post(f"{url}/indicados/{a['id']}")
    assert resp.status_code == 200 and resp.json()["jovem"] == a["nome"]
    assert client.post(f"{url}/indicados/{a['id']}").status_code == 404
    assert client.delete(f"{url}/indicados/{a['id']}").status_code == 404
