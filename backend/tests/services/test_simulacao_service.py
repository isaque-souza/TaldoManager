import pytest

from app.services import simulacao_service
from app.services.simulacao_service import simular_temporada


def test_simulacao_tem_todas_as_chaves():
    r = simular_temporada(seed=1)

    esperadas = {
        "campeonato", "seed", "rodadas", "campeao", "classificacao",
        "artilharia", "assistencias", "melhores_notas", "clean_sheets",
        "hat_tricks", "mvp", "historico", "recordes",
    }
    assert esperadas <= set(r)


def test_classificacao_completa_e_ordenada():
    r = simular_temporada(seed=1)

    assert len(r["classificacao"]) == 20
    pontos = [c["pontos"] for c in r["classificacao"]]
    assert pontos == sorted(pontos, reverse=True)
    assert r["classificacao"][0]["clube"] == r["campeao"]


def test_todos_os_clubes_jogaram_todas_as_rodadas():
    r = simular_temporada(seed=1)

    assert r["rodadas"] == 38
    assert len(r["historico"]) == 380
    for clube in r["classificacao"]:
        assert clube["jogos"] == 38


def test_seed_torna_a_simulacao_reproduzivel():
    a = simular_temporada(seed=99)
    b = simular_temporada(seed=99)

    assert a["classificacao"] == b["classificacao"]
    assert a["artilharia"] == b["artilharia"]


def test_evolucao_de_pontos_fecha_com_a_classificacao():
    r = simular_temporada(seed=1)
    ev = r["evolucao"]

    assert ev["rodadas"] == list(range(1, 39))
    assert len(ev["series"]) == 20

    # a série vem na ordem da tabela e o último ponto == pontos finais
    for serie, clube in zip(ev["series"], r["classificacao"]):
        assert serie["clube"] == clube["clube"]
        assert len(serie["pontos"]) == 38
        assert serie["pontos"][-1] == clube["pontos"]
        # acumulado é monotônico e cada rodada rende 0..3
        difs = [b - a for a, b in zip(serie["pontos"], serie["pontos"][1:])]
        assert all(0 <= d <= 3 for d in difs)


def test_rankings_respeitam_os_filtros():
    r = simular_temporada(seed=1)

    assert all(j["gols"] > 0 for j in r["artilharia"])
    assert all(j["assistencias"] > 0 for j in r["assistencias"])
    assert all(j["posicao"] == "Goleiro" for j in r["clean_sheets"])


def test_ranking_de_disciplina_e_penaltis():
    r = simular_temporada(seed=1)

    # disciplina: todo mundo tem pelo menos um cartão, e vem ordenado por
    # (vermelhos, amarelos, faltas)
    disc = r["disciplina"]
    assert disc, "uma temporada inteira sem cartões?"
    assert all(j["vermelhos"] or j["amarelos"] for j in disc)
    chaves = [(j["vermelhos"], j["amarelos"], j["faltas"]) for j in disc]
    assert chaves == sorted(chaves, reverse=True)

    # pênaltis: todo mundo bateu pelo menos um
    pen = r["penaltis"]
    assert all(j["penaltis"] or j["penaltis_perdidos"] for j in pen)
    assert sum(j["penaltis"] + j["penaltis_perdidos"] for j in pen) > 0


def test_disciplina_e_penaltis_fazem_round_trip():
    sid = simulacao_service.salvar_temporada(seed=42)
    salva = simulacao_service.carregar_temporada(sid)
    fresca = simular_temporada(seed=42)

    def chave(v):
        return (
            [(j["nome"], j["vermelhos"], j["amarelos"], j["faltas"])
             for j in v["disciplina"]],
            [(j["nome"], j["penaltis"], j["penaltis_perdidos"])
             for j in v["penaltis"]],
        )

    assert chave(salva) == chave(fresca)


# --- persistência ---

def test_salvar_e_carregar_devolve_a_mesma_visao():
    sid = simulacao_service.salvar_temporada(seed=42)

    salva = simulacao_service.carregar_temporada(sid)
    fresca = simular_temporada(seed=42)

    def resumo(v):
        return (
            [(c["posicao"], c["clube"], c["pontos"], c["saldo_gols"], c["forma"])
             for c in v["classificacao"]],
            [(j["nome"], j["gols"], j["assistencias"]) for j in v["artilharia"]],
            v["campeao"],
            v["recordes"],
            v["historico"],
            [(s["clube"], s["pontos"]) for s in v["evolucao"]["series"]],
        )

    assert resumo(salva) == resumo(fresca)


def test_simulacao_salva_ganha_ids_para_navegacao():
    sid = simulacao_service.salvar_temporada(seed=42)
    salva = simulacao_service.carregar_temporada(sid)

    assert all(isinstance(c["id"], int) for c in salva["classificacao"])
    assert all(isinstance(j["id"], int) for j in salva["artilharia"])

    # modo rápido não persiste, então não tem id
    assert simular_temporada(seed=42)["classificacao"][0]["id"] is None


def test_listar_e_apagar_simulacoes():
    assert simulacao_service.listar_simulacoes() == []

    a = simulacao_service.salvar_temporada(seed=1)
    b = simulacao_service.salvar_temporada(seed=2)

    lista = simulacao_service.listar_simulacoes()
    assert {s["id"] for s in lista} == {a, b}
    assert all({"seed", "criada_em", "campeao", "rodadas"} <= set(s) for s in lista)

    assert simulacao_service.apagar_simulacao(a) is True
    assert {s["id"] for s in simulacao_service.listar_simulacoes()} == {b}
    assert simulacao_service.apagar_simulacao(a) is False


def test_carregar_simulacao_inexistente():
    assert simulacao_service.carregar_temporada(999) is None


# --- clube do usuário + tática ---

def test_temporada_neutra_nao_tem_clube_nem_tatica():
    v = simular_temporada(seed=1)
    assert v["clube_usuario"] is None
    assert v["tatica"] is None


def test_salvar_com_clube_e_tatica_faz_round_trip():
    sid = simulacao_service.salvar_temporada(
        seed=7, clube_usuario="Taldo City", tatica="ofensivo"
    )
    v = simulacao_service.carregar_temporada(sid)

    assert v["clube_usuario"] == "Taldo City"
    assert v["tatica"] == "ofensivo"

    resumo = next(
        s for s in simulacao_service.listar_simulacoes() if s["id"] == sid
    )
    assert resumo["clube_usuario"] == "Taldo City"
    assert resumo["tatica"] == "ofensivo"


def test_tatica_sem_clube_e_ignorada():
    sid = simulacao_service.salvar_temporada(seed=7, tatica="ofensivo")
    v = simulacao_service.carregar_temporada(sid)
    assert v["clube_usuario"] is None
    assert v["tatica"] is None


def test_clube_ou_tatica_invalidos_dao_erro():
    with pytest.raises(ValueError):
        simular_temporada(seed=1, clube_usuario="Inexistente FC")
    with pytest.raises(ValueError):
        simular_temporada(seed=1, clube_usuario="Taldo City", tatica="maluco")


def test_listar_clubes_traz_os_20_do_seed():
    clubes = simulacao_service.listar_clubes()
    assert len(clubes) == 20
    campos = {"nome", "pais", "forca", "ranking_forca", "meta_posicao", "meta",
              "dinheiro", "torcedores", "identidade"}
    assert all(campos == set(c) for c in clubes)
    assert "Taldo City" in {c["nome"] for c in clubes}


# --- formação + XI preferido ---

def _xi_de(nome):
    el = simulacao_service.elenco_do_clube(nome)["elenco"]
    por = lambda p: [j["nome"] for j in el if j["posicao"] == p]
    return por("Goleiro")[:1] + por("Defesa")[:4] + por("Meio-Campo")[:3] + por("Atacante")[:3]


def test_elenco_do_clube():
    el = simulacao_service.elenco_do_clube("Taldo City")
    assert el["nome"] == "Taldo City"
    assert len(el["elenco"]) == 23
    assert "4-4-2" in el["formacoes"]
    assert {"nome", "posicao", "overall"} == set(el["elenco"][0])
    assert simulacao_service.elenco_do_clube("Não Existe") is None


def test_formacao_e_xi_fazem_round_trip():
    xi = _xi_de("Taldo City")
    sid = simulacao_service.salvar_temporada(
        seed=7, clube_usuario="Taldo City", formacao="4-4-2", xi_preferido=xi
    )
    v = simulacao_service.carregar_temporada(sid)

    assert v["formacao"] == "4-4-2"
    assert v["xi_preferido"] == xi

    resumo = next(
        s for s in simulacao_service.listar_simulacoes() if s["id"] == sid
    )
    assert resumo["formacao"] == "4-4-2"


def test_formacao_e_xi_sem_clube_sao_ignorados():
    sid = simulacao_service.salvar_temporada(
        seed=7, formacao="4-4-2", xi_preferido=_xi_de("Taldo City")
    )
    v = simulacao_service.carregar_temporada(sid)
    assert v["formacao"] is None
    assert v["xi_preferido"] is None


def test_formacao_ou_xi_invalidos_dao_erro():
    with pytest.raises(ValueError):
        simular_temporada(seed=1, clube_usuario="Taldo City", formacao="9-0-0")
    with pytest.raises(ValueError):
        simular_temporada(
            seed=1, clube_usuario="Taldo City", xi_preferido=["Zé Ninguém"]
        )
    with pytest.raises(ValueError):
        simular_temporada(
            seed=1,
            clube_usuario="Taldo City",
            xi_preferido=_xi_de("Taldo City") + ["um a mais"] * 3,
        )


def test_xi_preferido_com_jogador_de_outro_clube_da_erro():
    xi_alheio = _xi_de("Real Taldo")
    with pytest.raises(ValueError):
        simular_temporada(
            seed=1, clube_usuario="Taldo City", xi_preferido=xi_alheio
        )


def test_detalhe_clube():
    sid = simulacao_service.salvar_temporada(seed=42)
    campeao_id = simulacao_service.carregar_temporada(sid)["classificacao"][0]["id"]

    det = simulacao_service.detalhe_clube(sid, campeao_id)

    assert len(det["elenco"]) == 23
    assert len(det["jogos"]) == 38
    assert det["clube"]["posicao_final"] == 1
    # pontos batem com o aproveitamento nos jogos
    v = sum(1 for j in det["jogos"] if j["resultado"] == "V")
    e = sum(1 for j in det["jogos"] if j["resultado"] == "E")
    assert det["clube"]["pontos"] == v * 3 + e


def test_detalhe_clube_de_outra_simulacao_da_none():
    sid = simulacao_service.salvar_temporada(seed=1)
    clube_id = simulacao_service.carregar_temporada(sid)["classificacao"][0]["id"]

    assert simulacao_service.detalhe_clube(999, clube_id) is None


# --- navegação por partida / jogador (fase 2b) ---

def _sid_e_clube_campeao(seed=42):
    sid = simulacao_service.salvar_temporada(seed=seed)
    campeao = simulacao_service.carregar_temporada(sid)["classificacao"][0]["id"]
    return sid, campeao


def test_detalhe_partida_traz_timeline_e_escalacoes():
    sid, campeao = _sid_e_clube_campeao()
    jogo = simulacao_service.detalhe_clube(sid, campeao)["jogos"][0]

    det = simulacao_service.detalhe_partida(sid, jogo["partida_id"])

    p = det["partida"]
    assert p["gols_mandante"] + p["gols_visitante"] >= 0
    assert p["posse_mandante"] + p["posse_visitante"] == 100

    # chutes no gol e escanteios persistem e são coerentes
    assert p["finalizacoes_gol_mandante"] <= p["finalizacoes_mandante"]
    assert p["finalizacoes_gol_visitante"] <= p["finalizacoes_visitante"]
    assert p["escanteios_mandante"] >= 0 and p["escanteios_visitante"] >= 0

    # 11 titulares por lado, mais eventuais substitutos
    for lado in ("escalacao_mandante", "escalacao_visitante"):
        assert sum(1 for a in det[lado] if a["titular"]) == 11
        assert all(0 <= a["nota"] <= 10 for a in det[lado])

    # gols dos eventos batem com o placar
    gols_evento = sum(1 for e in det["eventos"] if e["tipo"] in ("gol", "penalti"))
    assert gols_evento == p["gols_mandante"] + p["gols_visitante"]


def test_detalhe_partida_de_outra_simulacao_da_none():
    sid, campeao = _sid_e_clube_campeao(seed=1)
    pid = simulacao_service.detalhe_clube(sid, campeao)["jogos"][0]["partida_id"]

    assert simulacao_service.detalhe_partida(999, pid) is None


def test_game_log_do_jogador_bate_com_a_ficha():
    sid, campeao = _sid_e_clube_campeao()
    elenco = simulacao_service.detalhe_clube(sid, campeao)["elenco"]
    craque = max(elenco, key=lambda j: j["partidas"])

    log = simulacao_service.game_log_jogador(sid, craque["id"])

    assert log["jogador"]["nome"] == craque["nome"]
    assert len(log["jogos"]) == craque["partidas"]
    assert sum(j["gols"] for j in log["jogos"]) == craque["gols"]
    assert sum(j["assistencias"] for j in log["jogos"]) == craque["assistencias"]

    media = sum(j["nota"] for j in log["jogos"]) / len(log["jogos"])
    assert round(media, 1) == round(craque["nota_media"], 1)


def test_game_log_de_jogador_inexistente_da_none():
    sid, _ = _sid_e_clube_campeao(seed=1)
    assert simulacao_service.game_log_jogador(sid, 99999) is None
