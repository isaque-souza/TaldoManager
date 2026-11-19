"""Identidade do jogador (v2.7, fase 2): nos mundos da API a chave é
"apif:<id>" e o nome é só de exibição. Dois "João Silva" são dois
jogadores; trocar o nome não troca a identidade; a chave nunca aparece para
o técnico; o v1 não muda nada."""

import json
import re

import pytest
from fastapi.testclient import TestClient

from app.db.conexao import conectar
from app.main import app
from app.services import carreira_service, simulacao_service, temporada_service
from scripts import data_loader, mundos
from tests.conftest import HOMONIMO, converter_para_api

client = TestClient(app)
DUAS = ["taldo", "premier"]


@pytest.fixture(autouse=True)
def _sem_demissao(cargo_garantido):
    """Não é sobre a diretoria."""


def _linhas(sql, *args):
    conn = conectar()
    try:
        return [dict(r) for r in conn.execute(sql, args)]
    finally:
        conn.close()


def _novo_save(clube="Chelsea", mundo="api", seed=3):
    r = client.post("/simulacoes", json={"seed": seed, "clube": clube, "modo": "rodada_a_rodada",
                                         "mundo": mundo, "ligas": DUAS})
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ---------------------------------------------------------------------------
# o detector de vazamento
# ---------------------------------------------------------------------------

def vazamentos(dado, caminho="", achados=None):
    """Onde "apif:" aparece para o técnico: todo texto e todo campo, menos
    os de identidade (`chave`, `*_chave`, `*_chaves`), que o frontend só
    devolve ao servidor e nunca mostra."""
    achados = [] if achados is None else achados
    if isinstance(dado, dict):
        for campo, valor in dado.items():
            if "apif:" in campo:
                achados.append(f"{caminho} (nome de campo) {campo}")
            if campo == "chave" or campo.endswith(("_chave", "_chaves")):
                continue
            vazamentos(valor, f"{caminho}.{campo}", achados)
    elif isinstance(dado, list):
        for valor in dado:
            vazamentos(valor, f"{caminho}[]", achados)
    elif isinstance(dado, str) and "apif:" in dado:
        achados.append(f"{caminho} = {dado[:80]}")
    return achados


def percorrer(sid):
    """Todas as telas do save (GET) — o que o frontend recebe. Devolve os
    vazamentos e quantas respostas foram olhadas."""
    achados, vistas = [], 0
    jogadores = [r["id"] for r in _linhas(
        "SELECT id FROM jogador WHERE simulacao_id = ? AND nome LIKE 'apif:%' LIMIT 4", sid)]
    partidas = [r["id"] for r in _linhas(
        "SELECT id FROM partida WHERE simulacao_id = ? LIMIT 3", sid)]
    clubes = [r["id"] for r in _linhas(
        "SELECT id FROM clube WHERE simulacao_id = ? AND liga = 'premier' LIMIT 3", sid)]
    negociacoes = [r["id"] for r in _linhas(
        "SELECT id FROM negociacao WHERE simulacao_id = ?", sid)]
    sim = _linhas("SELECT carreira_id, rodada_atual FROM simulacao WHERE id = ?", sid)[0]
    rotas = [f"/simulacoes/{sid}{r}" for r in (
        "", "/rodadas/proxima", "/calendario", "/pre-jogo", "/pos-jogo", "/mercado",
        "/historico-transferencias", "/observados", "/marketing", "/copa", "/estadio",
        "/olheiro", "/base", "/planos", "/mensagens", "/transmissao",
        "/transmissao/estado?minuto=45",
        *(f"/rodadas/{n}/ao-vivo" for n in range(1, (sim["rodada_atual"] or 1))),
        *(f"/jogadores/{j}" for j in jogadores),
        *(f"/jogadores/{j}/contrato" for j in jogadores),
        *(f"/jogadores/{j}/ofertas" for j in jogadores),
        *(f"/partidas/{p}" for p in partidas),
        *(f"/clubes/{c}" for c in clubes),
        *(f"/negociacoes/{n}" for n in negociacoes),
    )]
    rotas += ["/simulacoes", "/clubes?mundo=api", f"/clubes/Chelsea?mundo=api"]
    if sim["carreira_id"]:
        rotas.append(f"/carreiras/{sim['carreira_id']}")
    for rota in rotas:
        resp = client.get(rota)
        if resp.headers.get("content-type", "").startswith("application/json"):
            vistas += 1
            vazamentos(resp.json(), re.sub(r"/\d+", "/N", rota), achados)
    return achados, vistas


# ---------------------------------------------------------------------------
# o v1 não muda
# ---------------------------------------------------------------------------

def test_v1_nao_ganha_chave_nem_exibicao():
    sid = _novo_save(clube="Liverpool", mundo="v1")
    client.post(f"/simulacoes/{sid}/rodadas", json={})
    mercado = client.get(f"/simulacoes/{sid}/mercado").text
    assert '"chave"' not in mercado and "_chave" not in mercado
    snapshot = json.loads(_linhas("SELECT estado_json FROM simulacao WHERE id = ?", sid)[0]["estado_json"])
    assert all("exibicao" not in campos
               for c in snapshot["clubes"].values() for campos in c["jogadores"].values())
    assert _linhas("SELECT COUNT(*) n FROM jogador WHERE simulacao_id = ? AND exibicao IS NOT NULL",
                   sid)[0]["n"] == 0


# ---------------------------------------------------------------------------
# homônimos
# ---------------------------------------------------------------------------

def test_dois_joao_silva_sao_dois_jogadores(mundo_api):
    do_chelsea, do_arsenal = mundo_api["homonimos"]
    campeonato = data_loader.carregar_campeonato(tuple(DUAS), "api")
    joaos = {j.nome: (c.nome, j.nome_exibicao)
             for c in campeonato.clubes for j in c.jogadores if j.nome_exibicao == HOMONIMO}
    assert joaos == {do_chelsea: ("Chelsea", HOMONIMO), do_arsenal: ("Arsenal", HOMONIMO)}

    sid = _novo_save()
    disponiveis = client.get(f"/simulacoes/{sid}/mercado").json()["disponiveis"]
    elenco = client.get(f"/simulacoes/{sid}/mercado").json()["elenco"]
    meu = [j for j in elenco if j["nome"] == HOMONIMO]
    dele = [j for j in disponiveis if j["nome"] == HOMONIMO]
    assert [j["chave"] for j in meu] == [do_chelsea]
    assert [j["chave"] for j in dele] == [do_arsenal]


def test_escalacao_pela_chave(mundo_api):
    """O XI vai pela chave: tirar o João Silva do Chelsea não mexe no do
    Arsenal; o nome sozinho (ambíguo) é recusado, nunca vira o jogador errado."""
    do_chelsea, do_arsenal = mundo_api["homonimos"]
    sid = _novo_save()
    proxima = client.get(f"/simulacoes/{sid}/rodadas/proxima").json()
    titulares = [j["chave"] for j in proxima["escalacao"]["titulares"]]
    banco = [j for j in proxima["escalacao"]["banco"] if j["posicao"] != "Goleiro"]
    assert do_chelsea in titulares
    xi = [banco[0]["chave"] if c == do_chelsea else c for c in titulares]

    r = client.patch(f"/simulacoes/{sid}/decisao", json={"xi": xi})
    assert r.status_code == 200, r.text
    assert client.post(f"/simulacoes/{sid}/rodadas", json={}).status_code == 200

    atuou = {r["nome"]: r["titular"] for r in _linhas(
        "SELECT j.nome, a.titular FROM atuacao a JOIN jogador j ON j.id = a.jogador_id"
        " JOIN partida p ON p.id = a.partida_id WHERE p.simulacao_id = ? AND p.rodada = 1", sid)}
    assert atuou.get(do_chelsea) != 1
    assert atuou[banco[0]["chave"]] == 1

    # o nome de exibição sozinho não identifica ninguém
    r = client.patch(f"/simulacoes/{sid}/decisao", json={"xi": [HOMONIMO, *xi[1:]]})
    assert r.status_code >= 400 or HOMONIMO not in json.dumps(
        _linhas("SELECT xi_preferido FROM simulacao WHERE id = ?", sid)[0])


def test_substituicao_na_transmissao_pela_chave(mundo_api):
    do_chelsea, _ = mundo_api["homonimos"]
    sid = _novo_save()
    t = client.post(f"/simulacoes/{sid}/transmissao", json={})
    assert t.status_code == 200, t.text
    assert not vazamentos(t.json())
    meu = t.json()["mandante"] if t.json()["mandante"]["clube"] == "Chelsea" else t.json()["visitante"]
    texto = json.dumps(meu, ensure_ascii=False)
    assert do_chelsea in texto and HOMONIMO in texto     # a chave vai, ao lado do nome

    proxima = client.get(f"/simulacoes/{sid}/rodadas/proxima").json()
    entra = next(j for j in proxima["escalacao"]["banco"] if j["posicao"] != "Goleiro")
    r = client.post(f"/simulacoes/{sid}/transmissao/decisoes",
                    json={"minuto": 30, "sai": do_chelsea, "entra": entra["chave"]})
    assert r.status_code == 200, r.text
    decisao = r.json()["decisoes"][-1]
    assert decisao["sai"] == HOMONIMO and decisao["sai_chave"] == do_chelsea
    assert decisao["entra"] == entra["nome"]

    ambiguo = client.post(f"/simulacoes/{sid}/transmissao/decisoes",
                          json={"minuto": 40, "sai": HOMONIMO, "entra": entra["chave"]})
    assert ambiguo.status_code >= 400

    assert client.post(f"/simulacoes/{sid}/rodadas", json={}).status_code == 200
    saiu = _linhas(
        "SELECT a.saiu_min FROM atuacao a JOIN jogador j ON j.id = a.jogador_id"
        " JOIN partida p ON p.id = a.partida_id"
        " WHERE p.simulacao_id = ? AND p.rodada = 1 AND j.nome = ?", sid, do_chelsea)
    assert saiu and saiu[0]["saiu_min"] is not None and saiu[0]["saiu_min"] <= 31


def test_mercado_pela_chave(mundo_api):
    _, do_arsenal = mundo_api["homonimos"]
    sid = _novo_save()
    mercado = client.get(f"/simulacoes/{sid}/mercado").json()

    obs = client.put(f"/simulacoes/{sid}/observados", json={"nome": do_arsenal})
    assert obs.status_code == 200, obs.text
    assert obs.json()["nome"] == HOMONIMO and obs.json()["chave"] == do_arsenal
    lista = client.get(f"/simulacoes/{sid}/observados").json()
    assert do_arsenal in json.dumps(lista) and not vazamentos(lista)

    rel = client.post(f"/simulacoes/{sid}/relatorios", json={"nome": do_arsenal})
    assert rel.status_code == 201, rel.text
    assert rel.json()["nome"] == HOMONIMO

    livre = mercado["livres"][0]
    assert livre["chave"].startswith("apif:") and not livre["nome"].startswith("apif:")
    contratado = client.post(f"/simulacoes/{sid}/livres/contratar", json={"nome": livre["chave"]})
    assert contratado.status_code in (200, 400, 409), contratado.text
    assert not vazamentos(contratado.json())

    alvo = next(j for j in mercado["disponiveis"] if j.get("chave") == do_arsenal)
    proposta = client.post(f"/simulacoes/{sid}/propostas",
                           json={"jogador_id": alvo["jogador_id"], "valor": 200_000_000})
    assert proposta.status_code in (200, 400, 409), proposta.text
    assert not vazamentos(proposta.json())


# ---------------------------------------------------------------------------
# nome que muda, chave que fica
# ---------------------------------------------------------------------------

def test_trocar_o_nome_nao_troca_a_identidade(mundo_api, tmp_path):
    do_chelsea, _ = mundo_api["homonimos"]
    ident = int(do_chelsea.split(":")[1])
    obra = tmp_path / "obra-api2" / "premier"
    obra.mkdir(parents=True)
    for nome in mundos.ARQUIVOS_DA_LIGA:
        origem = mundos.pasta_da_liga("api", "premier") / nome
        if origem.is_file():
            (obra / nome).write_bytes(origem.read_bytes())
    # o mesmo arquivo da API, com o nome trocado: a chave é a mesma
    jogadores = json.loads((obra / "jogadores.json").read_text(encoding="utf-8"))
    next(j for j in jogadores if j["id"] == ident)["nome"] = "João Silva Santos"
    (obra / "jogadores.json").write_text(json.dumps(jogadores, ensure_ascii=False), encoding="utf-8")
    m = mundos.criar_mundo("api2", "Nome novo", base="api", trocar={"premier": obra})
    assert m["alteracoes"]["jogadores"] == {"entraram": 0, "sairam": 0}

    velho, novo = _novo_save(mundo="api"), _novo_save(mundo="api2")
    for sid, esperado in ((velho, HOMONIMO), (novo, "João Silva Santos")):
        elenco = client.get(f"/simulacoes/{sid}/mercado").json()["elenco"]
        assert next(j["nome"] for j in elenco if j.get("chave") == do_chelsea) == esperado
        assert client.post(f"/simulacoes/{sid}/rodadas", json={}).status_code == 200
    assert mundos.exibicoes("api")[do_chelsea] == HOMONIMO


# ---------------------------------------------------------------------------
# virada, snapshot e o passeio por todas as telas
# ---------------------------------------------------------------------------

def test_virada_e_snapshot_guardam_a_chave(mundo_api):
    do_chelsea, do_arsenal = mundo_api["homonimos"]
    sid = simulacao_service.salvar_temporada(seed=4, clube_usuario="Chelsea",
                                             ligas=tuple(DUAS), mundo="api")
    nomes = {r["nome"]: r["exibicao"] for r in _linhas(
        "SELECT nome, exibicao FROM jogador WHERE simulacao_id = ?", sid)}
    assert nomes[do_chelsea] == nomes[do_arsenal] == HOMONIMO

    nova = carreira_service.proxima_temporada(sid)["simulacao_id"]
    temporada_service.avancar(nova)
    snapshot = json.loads(_linhas("SELECT estado_json FROM simulacao WHERE id = ?", nova)[0]["estado_json"])
    todos = {n: c for clube in snapshot["clubes"].values() for n, c in clube["jogadores"].items()}
    # quem saiu na virada (aposentadoria, venda) pode não estar; quem está tem a chave
    assert all(n.startswith("apif:") or not c.get("exibicao") for n, c in todos.items())
    achados, vistas = percorrer(nova)
    assert vistas > 20
    assert achados == []


def test_nenhuma_chave_aparece_em_tela_alguma(mundo_api):
    """O passeio completo: rodadas, transmissão, mercado, mensagens, e cada
    GET que o frontend usa — nenhum "apif:" fora dos campos de chave."""
    do_chelsea, do_arsenal = mundo_api["homonimos"]
    sid = _novo_save()
    client.put(f"/simulacoes/{sid}/observados", json={"nome": do_arsenal})
    client.post(f"/simulacoes/{sid}/relatorios", json={"nome": do_arsenal})
    client.post(f"/simulacoes/{sid}/planos", json={"nome": "Teste", "formacao": "4-3-3",
                                                   "tatica": "equilibrado"})
    client.post(f"/simulacoes/{sid}/transmissao", json={})
    for _ in range(5):
        client.post(f"/simulacoes/{sid}/rodadas", json={})
    assert _linhas("SELECT COUNT(*) n FROM mensagem WHERE simulacao_id = ? AND corpo LIKE '%apif:%'",
                   sid)[0]["n"] > 0, "o teste precisa de mensagem com chave gravada"
    achados, vistas = percorrer(sid)
    assert vistas > 25
    assert achados == []
