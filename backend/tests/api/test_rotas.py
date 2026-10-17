from fastapi.testclient import TestClient

from app.main import app

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
    assert len(clubes) == 20
    assert {"nome", "pais", "forca", "ranking_forca", "meta_posicao", "meta",
            "dinheiro", "torcedores", "identidade"} == set(clubes[0])


def test_listar_clubes_ranking_segue_a_forca():
    clubes = sorted(client.get("/clubes").json(), key=lambda c: c["ranking_forca"])
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
    assert r.json()["transferencia"]["para_clube"] == "Real Taldo"

    # o mesmo jogador de novo: agora é do seu elenco -> 400
    assert client.post(f"/simulacoes/{sid}/propostas",
                       json={"jogador_id": alvo["jogador_id"], "valor": 1}).status_code == 400

    # venda: lista de ofertas e aceite
    meu = next(f for f in corpo["elenco"] if f["bloqueio"] is None)
    ofertas = client.get(f"/simulacoes/{sid}/jogadores/{meu['jogador_id']}/ofertas")
    assert ofertas.status_code == 200
    clube = ofertas.json()["ofertas"][0]["clube"]
    venda = client.post(f"/simulacoes/{sid}/vendas",
                        json={"jogador_id": meu["jogador_id"], "clube": clube})
    assert venda.status_code == 200 and venda.json()["para_clube"] == clube

    assert client.get("/simulacoes/999999/mercado").status_code == 404


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


def test_proxima_temporada_cria_e_lista_a_carreira():
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
    assert len(av["partidas"]) == len(jogada["resultados"])
    pid = av["partidas"][0]["partida_id"]
    assert client.get(f"/simulacoes/{sid}/partidas/{pid}").json()["partida"]["acrescimos"] in range(1, 6)
