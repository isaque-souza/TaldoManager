from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_simulacao_responde_no_formato_do_schema():
    resp = client.get("/simulacao?seed=5")
    assert resp.status_code == 200

    corpo = resp.json()
    assert corpo["seed"] == 5
    assert corpo["rodadas"] == 38
    assert len(corpo["classificacao"]) == 20
    assert corpo["campeao"] == corpo["classificacao"][0]["clube"]
    assert corpo["mvp"] is not None


def test_simulacao_sem_seed_funciona():
    resp = client.get("/simulacao")
    assert resp.status_code == 200
    assert resp.json()["seed"] is None


# --- clube do usuário + tática ---

def test_listar_clubes():
    resp = client.get("/clubes")
    assert resp.status_code == 200
    clubes = resp.json()
    assert len(clubes) == 20
    assert {"nome", "pais"} == set(clubes[0])


def test_criar_simulacao_com_clube_e_tatica():
    criada = client.post("/simulacoes", json={"seed": 7, "clube": "Taldo City", "tatica": "ofensivo"})
    assert criada.status_code == 201
    sid = criada.json()["id"]

    corpo = client.get(f"/simulacoes/{sid}").json()
    assert corpo["clube_usuario"] == "Taldo City"
    assert corpo["tatica"] == "ofensivo"

    resumo = client.get("/simulacoes").json()[0]
    assert resumo["clube_usuario"] == "Taldo City"


def test_clube_inexistente_da_400():
    resp = client.post("/simulacoes", json={"clube": "Inexistente FC"})
    assert resp.status_code == 400


def test_tatica_invalida_da_422():
    resp = client.get("/simulacao?clube=Taldo City&tatica=maluco")
    assert resp.status_code == 422


# --- formação + XI preferido ---

def test_elenco_de_um_clube_do_seed():
    resp = client.get("/clubes/Taldo City")
    assert resp.status_code == 200
    corpo = resp.json()
    assert len(corpo["elenco"]) == 18
    assert "4-3-3" in corpo["formacoes"]

    assert client.get("/clubes/Nao Existe").status_code == 404


def test_criar_simulacao_com_formacao_e_xi():
    el = client.get("/clubes/Taldo City").json()["elenco"]
    por = lambda p: [j["nome"] for j in el if j["posicao"] == p]
    xi = por("Goleiro")[:1] + por("Defesa")[:4] + por("Meio-Campo")[:4] + por("Atacante")[:2]

    criada = client.post("/simulacoes", json={
        "seed": 7, "clube": "Taldo City", "formacao": "4-4-2", "xi": xi,
    })
    assert criada.status_code == 201
    corpo = client.get(f"/simulacoes/{criada.json()['id']}").json()
    assert corpo["formacao"] == "4-4-2"
    assert corpo["xi_preferido"] == xi


def test_post_simulacoes_sem_corpo_funciona():
    resp = client.post("/simulacoes")
    assert resp.status_code == 201


def test_formacao_invalida_da_400():
    resp = client.post("/simulacoes", json={"clube": "Taldo City", "formacao": "9-0-0"})
    assert resp.status_code == 400


# --- simulações persistidas ---

def test_fluxo_criar_listar_obter_apagar():
    assert client.get("/simulacoes").json() == []

    criada = client.post("/simulacoes", json={"seed": 42})
    assert criada.status_code == 201
    sid = criada.json()["id"]

    lista = client.get("/simulacoes").json()
    assert len(lista) == 1
    assert lista[0]["id"] == sid
    assert lista[0]["campeao"]

    obtida = client.get(f"/simulacoes/{sid}")
    assert obtida.status_code == 200
    corpo = obtida.json()
    assert len(corpo["classificacao"]) == 20
    assert corpo["classificacao"][0]["id"] is not None

    assert client.delete(f"/simulacoes/{sid}").status_code == 204
    assert client.get("/simulacoes").json() == []


def test_obter_simulacao_inexistente_404():
    assert client.get("/simulacoes/999").status_code == 404
    assert client.delete("/simulacoes/999").status_code == 404


def test_detalhe_do_clube():
    sid = client.post("/simulacoes", json={"seed": 42}).json()["id"]
    campeao = client.get(f"/simulacoes/{sid}").json()["classificacao"][0]
    cid = campeao["id"]

    resp = client.get(f"/simulacoes/{sid}/clubes/{cid}")
    assert resp.status_code == 200

    corpo = resp.json()
    assert corpo["clube"]["nome"] == campeao["clube"]
    assert len(corpo["elenco"]) == 18
    assert len(corpo["jogos"]) == 38

    assert client.get(f"/simulacoes/{sid}/clubes/9999").status_code == 404


# --- navegação por partida / jogador (fase 2b) ---

def test_detalhe_de_partida_e_game_log():
    sid = client.post("/simulacoes", json={"seed": 42}).json()["id"]
    campeao = client.get(f"/simulacoes/{sid}").json()["classificacao"][0]["id"]
    clube = client.get(f"/simulacoes/{sid}/clubes/{campeao}").json()

    pid = clube["jogos"][0]["partida_id"]
    partida = client.get(f"/simulacoes/{sid}/partidas/{pid}")
    assert partida.status_code == 200
    corpo = partida.json()
    assert sum(1 for a in corpo["escalacao_mandante"] if a["titular"]) == 11
    assert isinstance(corpo["eventos"], list)

    jid = clube["elenco"][0]["id"]
    jogador = client.get(f"/simulacoes/{sid}/jogadores/{jid}")
    assert jogador.status_code == 200
    log = jogador.json()
    assert log["jogador"]["id"] == jid
    assert len(log["jogos"]) == log["jogador"]["partidas"]
    # dados de mercado (v0.7) chegam até a API
    assert log["jogador"]["valor_mercado"] > 0
    assert log["jogador"]["salario"] > 0
    assert log["jogador"]["potencial"] >= log["jogador"]["overall"]

    assert client.get(f"/simulacoes/{sid}/partidas/999999").status_code == 404
    assert client.get(f"/simulacoes/{sid}/jogadores/999999").status_code == 404


# --- temporada rodada a rodada ---

def _clube_qualquer():
    return client.get("/clubes").json()[0]["nome"]


def test_criar_temporada_rodada_a_rodada_exige_clube():
    resp = client.post("/simulacoes", json={"seed": 1, "modo": "rodada_a_rodada"})
    assert resp.status_code == 400


def test_fluxo_rodada_a_rodada():
    clube = _clube_qualquer()
    criada = client.post(
        "/simulacoes",
        json={"seed": 8, "clube": clube, "tatica": "ofensivo",
              "modo": "rodada_a_rodada"},
    )
    assert criada.status_code == 201
    sid = criada.json()["id"]

    resumo = client.get("/simulacoes").json()[0]
    assert resumo["estado"] == "em_andamento"
    assert resumo["rodada_atual"] == 1

    pr = client.get(f"/simulacoes/{sid}/rodadas/proxima")
    assert pr.status_code == 200
    corpo = pr.json()
    assert corpo["rodada"] == 1
    assert corpo["clube_usuario"] == clube
    assert len(corpo["confrontos"]) == 10

    jogou = client.post(f"/simulacoes/{sid}/rodadas", json={"tatica": "defensivo"})
    assert jogou.status_code == 200
    r = jogou.json()
    assert r["rodada_jogada"] == 1
    assert r["concluida"] is False
    assert len(r["resultados"]) == 10
    assert r["tatica"] == "defensivo"


def test_rodada_a_rodada_ate_o_fim_via_api():
    clube = _clube_qualquer()
    sid = client.post(
        "/simulacoes",
        json={"seed": 9, "clube": clube, "modo": "rodada_a_rodada"},
    ).json()["id"]

    while not client.get(f"/simulacoes/{sid}/rodadas/proxima").json()["concluida"]:
        assert client.post(f"/simulacoes/{sid}/rodadas").status_code == 200

    final = client.get(f"/simulacoes/{sid}").json()
    assert final["estado"] == "concluida"
    assert final["campeao"] == final["classificacao"][0]["clube"]

    # não dá pra avançar depois de concluída
    assert client.post(f"/simulacoes/{sid}/rodadas").status_code == 409


def test_proxima_rodada_de_simulacao_inexistente_404():
    assert client.get("/simulacoes/99999/rodadas/proxima").status_code == 404
    assert client.post("/simulacoes/99999/rodadas").status_code == 404
