from fastapi.testclient import TestClient

from app.main import app
from tests.negociar import oferecer

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_raiz_serve_o_frontend():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Taldo Manager" in resp.text


def test_serve_os_modulos_js_do_frontend():
    resp = client.get("/js/nucleo.js")
    assert resp.status_code == 200
    assert "javascript" in resp.headers["content-type"]


def test_frontend_pede_revalidacao_para_nao_usar_js_velho():
    assert client.get("/js/nucleo.js").headers["cache-control"] == "no-cache"


def test_rotas_da_api_tem_prioridade_sobre_o_frontend():
    resp = client.get("/clubes")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


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
    # v1.6: as duas ligas
    assert len(clubes) == 40
    assert {c["liga"] for c in clubes} == {"taldo", "premier"}
    assert {"nome", "liga", "pais", "forca", "ranking_forca", "meta_posicao", "meta",
            "dinheiro", "torcedores", "identidade"} == set(clubes[0])


def test_listar_clubes_ranking_segue_a_forca():
    todos = client.get("/clubes").json()
    for liga in ("taldo", "premier"):        # o ranking é dentro de cada liga
        clubes = sorted((c for c in todos if c["liga"] == liga),
                        key=lambda c: c["ranking_forca"])
        assert [c["ranking_forca"] for c in clubes] == list(range(1, 21))
        forcas = [c["forca"] for c in clubes]
        assert forcas == sorted(forcas, reverse=True)


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
    assert len(corpo["elenco"]) == 23
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
    assert len(corpo["elenco"]) == 23
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
    # as duas ligas jogam na mesma rodada (v1.6)
    assert len(corpo["confrontos"]) == 20
    assert sum(c["liga"] == "premier" for c in corpo["confrontos"]) == 10

    jogou = client.post(f"/simulacoes/{sid}/rodadas", json={"tatica": "defensivo"})
    assert jogou.status_code == 200
    r = jogou.json()
    assert r["rodada_jogada"] == 1
    assert r["concluida"] is False
    assert len(r["resultados"]) == 20
    assert {x["liga"] for x in r["resultados"]} == {"taldo", "premier"}
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


def test_autosave_da_escalacao_via_api():
    clube = _clube_qualquer()
    sid = client.post(
        "/simulacoes",
        json={"seed": 8, "clube": clube, "modo": "rodada_a_rodada"},
    ).json()["id"]

    salva = client.patch(f"/simulacoes/{sid}/decisao", json={"tatica": "defensivo"})
    assert salva.status_code == 200
    assert salva.json()["tatica"] == "defensivo"
    assert salva.json()["atualizada_em"]

    # reabrindo a tela, a escolha está lá — e nenhuma rodada foi jogada
    pr = client.get(f"/simulacoes/{sid}/rodadas/proxima").json()
    assert pr["rodada"] == 1
    assert pr["tatica"] == "defensivo"

    assert client.patch(
        f"/simulacoes/{sid}/decisao", json={"xi": ["Ninguém Daqui"]}
    ).status_code == 400
    assert client.patch(
        f"/simulacoes/{sid}/decisao", json={"tatica": "retranca"}
    ).status_code == 422
    assert client.patch(
        "/simulacoes/99999/decisao", json={"tatica": "ofensivo"}
    ).status_code == 404


def test_autosave_em_temporada_concluida_409():
    sid = client.post("/simulacoes", json={"seed": 2}).json()["id"]
    assert client.patch(
        f"/simulacoes/{sid}/decisao", json={"tatica": "ofensivo"}
    ).status_code == 409


def test_lista_vem_pela_ultima_jogada():
    clube = _clube_qualquer()
    antiga = client.post(
        "/simulacoes", json={"seed": 1, "clube": clube, "modo": "rodada_a_rodada"}
    ).json()["id"]
    nova = client.post(
        "/simulacoes", json={"seed": 2, "clube": clube, "modo": "rodada_a_rodada"}
    ).json()["id"]
    assert client.get("/simulacoes").json()[0]["id"] == nova

    # jogar na antiga a coloca no topo, mesmo tendo sido criada antes
    client.post(f"/simulacoes/{antiga}/rodadas")
    lista = client.get("/simulacoes").json()
    assert [s["id"] for s in lista[:2]] == [antiga, nova]
    assert lista[0]["atualizada_em"] > lista[0]["criada_em"]


def test_fluxo_do_mercado():
    sid = client.post(
        "/simulacoes", json={"seed": 4, "clube": "Real Taldo", "modo": "rodada_a_rodada"}
    ).json()["id"]

    m = client.get(f"/simulacoes/{sid}/mercado", params={"posicao": "Atacante"})
    assert m.status_code == 200
    corpo = m.json()
    assert corpo["janela_aberta"] is True and corpo["rivais"] == ["Taldo City"]
    assert all(f["posicao"] == "Atacante" for f in corpo["disponiveis"])

    # compra: proposta generosa fecha
    alvo = next(f for f in corpo["disponiveis"]
                if f["bloqueio"] is None and not f["rival"]
                and f["valor_mercado"] * 3 < corpo["caixa"])
    r = client.post(f"/simulacoes/{sid}/propostas",
                    json={"jogador_id": alvo["jogador_id"], "valor": alvo["valor_mercado"] * 3})
    assert r.status_code == 200
    assert r.json()["resposta"] in ("aceita", "multa")
    neg_id = r.json()["negociacao_id"]

    # etapa 2 (v1.7): o contrato com o jogador fecha a compra
    neg = client.get(f"/simulacoes/{sid}/negociacoes/{neg_id}").json()
    assert neg["status"] == "aberta" and neg["clube"] == alvo["clube"]
    contrato = {"salario": 5 * neg["salario_referencia"] + 2 * neg["salario_atual"],
                "anos": 1, "multa": "3x", "papel": neg["papel_esperado"]}
    r = client.post(f"/simulacoes/{sid}/negociacoes/{neg_id}/contrato", json=contrato)
    assert r.status_code == 200 and r.json()["status"] == "fechada"
    assert r.json()["transferencia"]["para_clube"] == "Real Taldo"
    # negociação fechada não recebe outro contrato
    assert client.post(f"/simulacoes/{sid}/negociacoes/{neg_id}/contrato",
                       json=contrato).status_code == 400

    # o mesmo jogador de novo: agora é do seu elenco -> 400
    assert client.post(f"/simulacoes/{sid}/propostas",
                       json={"jogador_id": alvo["jogador_id"], "valor": 1}).status_code == 400

    # venda (v1.7): a oferta da CPU e o aceite
    meu = next(f for f in corpo["elenco"] if f["bloqueio"] is None)
    clube = next(f["clube"] for f in corpo["disponiveis"] if not f["rival"])
    oid = oferecer(sid, meu["jogador_id"], clube, 1_000_000, teto=1_100_000)
    ofertas = client.get(f"/simulacoes/{sid}/jogadores/{meu['jogador_id']}/ofertas")
    assert ofertas.status_code == 200
    assert oid in [o["oferta_id"] for o in ofertas.json()["ofertas"]]
    assert client.post(f"/simulacoes/{sid}/ofertas/{oid}/contraproposta",
                       json={"valor": 500_000}).status_code == 400
    venda = client.post(f"/simulacoes/{sid}/ofertas/{oid}/aceitar")
    assert venda.status_code == 200 and venda.json()["para_clube"] == clube
    assert client.post(f"/simulacoes/{sid}/ofertas/{oid}/recusar").status_code == 400
    assert client.post(f"/simulacoes/{sid}/ofertas/999999/aceitar").status_code == 404

    assert client.get("/simulacoes/999999/mercado").status_code == 404


def test_contratar_livre_pela_api():
    sid = client.post(
        "/simulacoes", json={"seed": 4, "clube": "Real Taldo", "modo": "rodada_a_rodada"}
    ).json()["id"]
    livres = client.get(f"/simulacoes/{sid}/mercado").json()["livres"]
    assert livres and all(f["clube"] is None and f["luvas"] for f in livres)

    r = client.post(f"/simulacoes/{sid}/livres/contratar", json={"nome": livres[0]["nome"]})
    assert r.status_code == 200
    assert r.json()["jogador"] == livres[0]["nome"]
    assert r.json()["valor"] == livres[0]["luvas"]
    neg_id = r.json()["negociacao_id"]
    neg = client.get(f"/simulacoes/{sid}/negociacoes/{neg_id}").json()
    assert neg["salario_atual"] is None   # livre não tem salário hoje
    r = client.post(f"/simulacoes/{sid}/negociacoes/{neg_id}/contrato", json={
        "salario": 5 * neg["salario_referencia"], "anos": 1, "multa": "3x",
    })
    assert r.json()["status"] == "fechada"

    # já contratado: não está mais livre -> 404
    assert client.post(f"/simulacoes/{sid}/livres/contratar",
                       json={"nome": livres[0]["nome"]}).status_code == 404


def test_lista_de_transferencias_e_dispensa_pela_api():
    sid = client.post(
        "/simulacoes", json={"seed": 4, "clube": "Real Taldo", "modo": "rodada_a_rodada"}
    ).json()["id"]
    elenco = client.get(f"/simulacoes/{sid}/mercado").json()["elenco"]
    meu = next(f for f in elenco if f["posicao"] != "Goleiro")
    assert meu["rescisao"] is not None and meu["dispensa_bloqueada"] is None

    r = client.put(f"/simulacoes/{sid}/jogadores/{meu['jogador_id']}/a-venda",
                   json={"a_venda": True})
    assert r.status_code == 200 and r.json()["a_venda"] is True

    r = client.post(f"/simulacoes/{sid}/jogadores/{meu['jogador_id']}/dispensa")
    assert r.status_code == 200 and r.json()["rescisao"] == meu["rescisao"]
    # já não é do elenco: o id existe (a linha fica), mas não é dispensável
    assert client.post(
        f"/simulacoes/{sid}/jogadores/{meu['jogador_id']}/dispensa"
    ).status_code == 404
    assert client.post(f"/simulacoes/{sid}/jogadores/999999/dispensa").status_code == 404


def test_papel_pela_api():
    sid = client.post(
        "/simulacoes", json={"seed": 4, "clube": "Real Taldo", "modo": "rodada_a_rodada"}
    ).json()["id"]
    meu = client.get(f"/simulacoes/{sid}/mercado").json()["elenco"][0]
    r = client.put(f"/simulacoes/{sid}/jogadores/{meu['jogador_id']}/papel", json={"papel": "rotacao"})
    assert r.status_code == 200 and r.json()["papel"] == "rotacao"
    r = client.put(f"/simulacoes/{sid}/jogadores/{meu['jogador_id']}/papel", json={"papel": "craque"})
    assert r.status_code == 400


def test_mercado_de_temporada_concluida_da_409():
    sid = client.post("/simulacoes", json={"seed": 2}).json()["id"]
    assert client.get(f"/simulacoes/{sid}/mercado").status_code == 409


def test_fluxo_de_renovacao():
    sid = client.post(
        "/simulacoes", json={"seed": 5, "clube": "Real Taldo", "modo": "rodada_a_rodada"}
    ).json()["id"]
    meu = client.get(f"/simulacoes/{sid}/mercado").json()["elenco"][0]

    c = client.get(f"/simulacoes/{sid}/jogadores/{meu['jogador_id']}/contrato")
    assert c.status_code == 200
    ref = c.json()["salario_referencia"]

    # salário generoso fecha; multa fora do enum -> 422; duração inválida -> 400
    r = client.post(f"/simulacoes/{sid}/renovacoes",
                    json={"jogador_id": meu["jogador_id"], "salario": ref * 3, "anos": 2, "multa": "5x"})
    assert r.status_code == 200 and r.json()["resposta"] == "aceita"
    assert client.post(f"/simulacoes/{sid}/renovacoes",
                       json={"jogador_id": meu["jogador_id"], "salario": ref, "anos": 2, "multa": "9x"}).status_code == 422
    assert client.post(f"/simulacoes/{sid}/renovacoes",
                       json={"jogador_id": meu["jogador_id"], "salario": ref, "anos": 9, "multa": "3x"}).status_code == 400


def test_financas_na_temporada_e_historico_no_clube():
    sid = client.post("/simulacoes", json={"seed": 8}).json()["id"]
    visao = client.get(f"/simulacoes/{sid}").json()
    fin = visao["financas"]
    assert len(fin) == 20
    assert [f["clube"] for f in fin] == [c["clube"] for c in visao["classificacao"]]
    assert all(f["saldo"] == f["caixa"] - f["caixa_inicial"] for f in fin)
    assert all(f["folha"] > 0 for f in fin)

    clube = client.get(f"/simulacoes/{sid}/clubes/{fin[0]['id']}").json()["clube"]
    assert len(clube["historico_caixa"]) == 38
    assert clube["historico_caixa"][-1] == clube["dinheiro"]


# --- carreira (v0.8) ---

def _save_concluido_com_clube():
    clube = client.get("/clubes").json()[0]["nome"]
    return client.post("/simulacoes", json={"seed": 3, "clube": clube}).json()["id"]


def test_proxima_temporada_cria_e_lista_a_carreira(cargo_garantido):
    sid = _save_concluido_com_clube()

    resp = client.post(f"/simulacoes/{sid}/proxima-temporada")
    assert resp.status_code == 201
    corpo = resp.json()
    assert corpo["temporada"] == 2

    carreira = client.get(f"/carreiras/{corpo['carreira_id']}").json()
    assert [t["temporada"] for t in carreira["temporadas"]] == [1, 2]
    t1 = carreira["temporadas"][0]
    assert t1["vice"] and t1["artilheiro"]["valor"] > 0 and t1["mvp"]
    assert t1["posicao_usuario"] >= 1
    assert carreira["titulos"][0]["temporadas"] == [1]
    assert carreira["lideres"]["gols"]
    assert isinstance(carreira["hall_da_fama"], list)

    resumo = {s["id"]: s for s in client.get("/simulacoes").json()}
    assert resumo[corpo["simulacao_id"]]["temporada"] == 2
    assert resumo[sid]["carreira_id"] == corpo["carreira_id"]


def test_proxima_temporada_ja_continuada_da_409():
    sid = _save_concluido_com_clube()
    client.post(f"/simulacoes/{sid}/proxima-temporada")
    resp = client.post(f"/simulacoes/{sid}/proxima-temporada")
    assert resp.status_code == 409


def test_proxima_temporada_e_carreira_inexistentes_dao_404():
    assert client.post("/simulacoes/999/proxima-temporada").status_code == 404
    assert client.get("/carreiras/999").status_code == 404


def test_simulacao_salva_expoe_a_meta_da_diretoria():
    clube = client.get("/clubes").json()[0]
    sid = client.post(
        "/simulacoes", json={"clube": clube["nome"], "modo": "rodada_a_rodada"}
    ).json()["id"]

    meta = client.get(f"/simulacoes/{sid}").json()["meta"]
    assert meta["posicao"] == clube["meta_posicao"]
    assert meta["descricao"] == clube["meta"]
    assert meta["situacao"] in {"batida", "perto", "longe"}


def test_proxima_temporada_de_tecnico_demitido_da_409():
    clube = sorted(client.get("/clubes").json(), key=lambda c: c["ranking_forca"])[-1]
    sid = client.post("/simulacoes", json={"clube": clube["nome"], "seed": 3}).json()["id"]
    from app.db.conexao import conectar
    conn = conectar()
    with conn:   # meta de campeão para o mais fraco: muito abaixo → demitido
        conn.execute("UPDATE simulacao SET meta_posicao = 1 WHERE id = ?", (sid,))
    conn.close()

    visao = client.get(f"/simulacoes/{sid}").json()
    assert visao["cargo"]["estado"] == "demitido"
    assert visao["fim_de_carreira"]["temporadas"] == 1
    assert client.post(f"/simulacoes/{sid}/proxima-temporada").status_code == 409


def test_pre_jogo_pela_api():
    clube = client.get("/clubes").json()[0]["nome"]
    sid = client.post("/simulacoes", json={"clube": clube, "modo": "rodada_a_rodada", "seed": 2}).json()["id"]

    pj = client.get(f"/simulacoes/{sid}/pre-jogo").json()
    assert pj["clube_usuario"] == clube
    assert len(pj["mandante"]["titulares"]) == 11
    assert {"numero", "linha", "craque", "pendurado"} <= set(pj["mandante"]["titulares"][0])
    assert client.get("/simulacoes/999999/pre-jogo").status_code == 404


def test_rodada_ao_vivo_pela_api():
    clube = client.get("/clubes").json()[0]["nome"]
    sid = client.post("/simulacoes", json={"clube": clube, "modo": "rodada_a_rodada", "seed": 2}).json()["id"]
    jogada = client.post(f"/simulacoes/{sid}/rodadas", json={}).json()

    av = client.get(f"/simulacoes/{sid}/rodadas/1/ao-vivo").json()
    # só os jogos da liga do técnico (v1.6)
    minha = next(r["liga"] for r in jogada["resultados"] if clube in (r["mandante"], r["visitante"]))
    assert len(av["partidas"]) == sum(r["liga"] == minha for r in jogada["resultados"]) == 10
    pid = av["partidas"][0]["partida_id"]
    assert client.get(f"/simulacoes/{sid}/partidas/{pid}").json()["partida"]["acrescimos"] in range(1, 6)


# --- simulação interativa (v1.2) ---

def _transmissao_iniciada():
    clube = _clube_qualquer()
    sid = client.post(
        "/simulacoes", json={"seed": 8, "clube": clube, "modo": "rodada_a_rodada"}
    ).json()["id"]
    resp = client.post(f"/simulacoes/{sid}/transmissao", json={"tatica": "ofensivo"})
    assert resp.status_code == 200
    return sid, resp.json()


def test_transmissao_via_api_ate_o_apito():
    sid, t = _transmissao_iniciada()
    assert len(t["minutos"]) == 90 + t["acrescimos"]
    assert client.get(f"/simulacoes/{sid}/transmissao").json() == t

    meu = t["mandante"] if t["mandante"]["clube"] == t["clube_usuario"] else t["visitante"]
    assert meu["tatica"] == "ofensivo"
    momento = client.get(f"/simulacoes/{sid}/transmissao/estado?minuto=60")
    assert momento.status_code == 200
    assert momento.json()["minuto"] == 60

    mudou = client.post(f"/simulacoes/{sid}/transmissao/decisoes",
                        json={"minuto": 61, "tatica": "defensivo"})
    assert mudou.status_code == 200
    assert mudou.json()["decisoes"][-1]["tatica"] == "defensivo"

    jogou = client.post(f"/simulacoes/{sid}/rodadas")
    assert jogou.status_code == 200
    assert client.get(f"/simulacoes/{sid}/transmissao").status_code == 404


def test_transmissao_recusa_decisao_invalida_e_trava_o_elenco():
    sid, _ = _transmissao_iniciada()
    ruim = client.post(f"/simulacoes/{sid}/transmissao/decisoes",
                       json={"minuto": 10, "sai": "Ninguém", "entra": "Fulano"})
    assert ruim.status_code == 400
    assert client.post(f"/simulacoes/{sid}/transmissao/decisoes",
                       json={"minuto": 0, "tatica": "ofensivo"}).status_code == 422

    travado = client.patch(f"/simulacoes/{sid}/decisao", json={"tatica": "defensivo"})
    assert travado.status_code == 409
    assert client.get(f"/simulacoes/{sid}/rodadas/proxima").json()["transmissao_ativa"] is True


def test_transmissao_de_simulacao_inexistente_404():
    assert client.post("/simulacoes/999999/transmissao").status_code == 404
    assert client.get("/simulacoes/999999/transmissao").status_code == 404


# --- planos de jogo (v1.2) ---

def test_planos_via_api():
    clube = _clube_qualquer()
    sid = client.post(
        "/simulacoes", json={"seed": 8, "clube": clube, "modo": "rodada_a_rodada"}
    ).json()["id"]

    v = client.get(f"/simulacoes/{sid}/planos")
    assert v.status_code == 200
    titular = v.json()["planos"][0]
    assert titular["nome"] == "Titular" and titular["padrao"]

    novo = client.post(f"/simulacoes/{sid}/planos",
                       json={"nome": "Retranca", "formacao": "5-4-1", "tatica": "defensivo"})
    assert novo.status_code == 201
    retranca = next(p for p in novo.json()["planos"] if p["nome"] == "Retranca")

    assert client.post(f"/simulacoes/{sid}/planos", json={"nome": "Retranca"}).status_code == 400
    assert client.patch(f"/simulacoes/{sid}/planos/{retranca['id']}",
                        json={"padrao": True}).json()["planos"][1]["padrao"] is True

    usou = client.post(f"/simulacoes/{sid}/planos/{titular['id']}/usar")
    assert usou.status_code == 200 and usou.json()["em_uso"] == titular["id"]

    assert client.delete(f"/simulacoes/{sid}/planos/{titular['id']}").status_code == 200
    assert client.delete(f"/simulacoes/{sid}/planos/{retranca['id']}").status_code == 400
    assert client.get("/simulacoes/999999/planos").status_code == 404


def test_visao_de_cada_liga():
    """v1.6: a visão mostra uma liga — a do técnico, ou ?liga=."""
    sid = client.post("/simulacoes", json={"seed": 5, "clube": "Arsenal"}).json()["id"]

    corpo = client.get(f"/simulacoes/{sid}").json()
    assert corpo["liga"] == "premier" and corpo["campeonato"] == "Premier League"
    assert [l["id"] for l in corpo["ligas"]] == ["taldo", "premier"]
    assert len(corpo["classificacao"]) == 20
    assert "Arsenal" in {c["clube"] for c in corpo["classificacao"]}
    assert corpo["campeao"] == corpo["classificacao"][0]["clube"]
    assert corpo["meta"]["posicao_atual"] == next(
        c["posicao"] for c in corpo["classificacao"] if c["clube"] == "Arsenal"
    )

    taldo = client.get(f"/simulacoes/{sid}", params={"liga": "taldo"}).json()
    assert taldo["liga"] == "taldo" and len(taldo["classificacao"]) == 20
    assert "Arsenal" not in {c["clube"] for c in taldo["classificacao"]}
    assert taldo["campeao"] == taldo["classificacao"][0]["clube"]
    assert {j["clube"] for j in taldo["artilharia"]} <= {c["clube"] for c in taldo["classificacao"]}
    # a meta continua a do técnico, na Premier
    assert taldo["meta"] == corpo["meta"]


# --- copa entre as ligas (v1.6) ---------------------------------------------

def _mensagens(sid):
    return client.get(f"/simulacoes/{sid}/mensagens").json()["mensagens"]


def test_copa_da_temporada_e_jogo_do_tecnico():
    sid = client.post("/simulacoes", json={
        "modo": "rodada_a_rodada", "clube": "Manchester City", "seed": 6,
    }).json()["id"]

    copa = client.get(f"/simulacoes/{sid}/copa").json()["copa"]
    assert [f["fase"] for f in copa["fases"]] == ["oitavas", "quartas", "semi", "final"]
    assert len(copa["fases"][0]["jogos"]) == 8 and copa["fases"][1]["jogos"] == []
    assert copa["proxima"]["depois_da_rodada"] == 8
    # o campeão de 23/24 está na copa, em casa contra o 8º da Taldo
    assert copa["seu_clube"]["estado"] == "vivo"
    assert copa["seu_clube"]["jogo"]["mando"] == "casa"
    assert any(m["assunto"] == "Estamos na copa" for m in _mensagens(sid))

    for rodada in range(1, 9):
        res = client.post(f"/simulacoes/{sid}/rodadas").json()
        assert (res["copa"] is not None) == (rodada == 8)
    assert res["copa"]["fase"] == "oitavas" and len(res["copa"]["jogos"]) == 8
    assert all(j["vencedor"] for j in res["copa"]["jogos"])

    copa = client.get(f"/simulacoes/{sid}/copa").json()["copa"]
    assert copa["fases"][0]["jogada"] and len(copa["fases"][1]["jogos"]) == 4
    assert copa["seu_clube"]["estado"] in ("vivo", "eliminado")
    assuntos = {m["assunto"] for m in _mensagens(sid)}
    assert {"Avançamos na copa", "Fora da copa"} & assuntos


def test_save_so_da_taldo_nao_tem_copa():
    sid = client.post("/simulacoes", json={
        "modo": "rodada_a_rodada", "clube": "Real Taldo", "seed": 2, "ligas": ["taldo"],
    }).json()["id"]
    assert client.get(f"/simulacoes/{sid}/copa").json() == {"copa": None}
    assert client.get("/simulacoes/999999/copa").status_code == 404
