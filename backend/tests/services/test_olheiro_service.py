"""Olheiro profissional (v2.0) de ponta a ponta: trocar o nível, a faixa nas
fichas e na página do jogador, e a renovação na virada."""

import pytest
from fastapi.testclient import TestClient

from app.db.conexao import conectar
from app.domain import olheiro
from app.main import app
from app.services import (
    carreira_service, mercado_service, olheiro_service, simulacao_service, temporada_service,
)
from app.services.olheiro_service import TrocaInvalida

client = TestClient(app)


def _iniciar(clube="Real Taldo"):
    return temporada_service.iniciar(seed=11, clube_usuario=clube)


def _jovem_de_fora(m):
    return next(f for f in m["disponiveis"] if f["idade"] < 25)


def test_comeca_no_nivel_1_e_lista_os_niveis():
    v = olheiro_service.ver(_iniciar())
    assert v["nivel"] == 1 and v["gasto_temporada"] == 0
    assert [n["nivel"] for n in v["niveis"]] == [1, 2, 3, 4, 5]
    um, tres = v["niveis"][0], v["niveis"][2]
    assert um["bloqueio"] and um["custo_agora"] == 0
    # antes da 1ª rodada, subir custa a temporada inteira
    assert tres["custo_agora"] == olheiro.custo_temporada(3)


def test_subir_paga_e_estreita_a_faixa():
    sid = _iniciar()
    antes = mercado_service.ver_mercado(sid)
    largo = _jovem_de_fora(antes)
    assert largo["potencial_faixa"][1] - largo["potencial_faixa"][0] <= 14

    v = olheiro_service.trocar(sid, 4)
    assert v["nivel"] == 4
    assert v["gasto_temporada"] == olheiro.custo_temporada(4)
    assert v["caixa"] == antes["caixa"] - olheiro.custo_temporada(4)

    depois = mercado_service.ver_mercado(sid)
    estreito = next(f for f in depois["disponiveis"] if f["nome"] == largo["nome"])
    minimo, maximo = estreito["potencial_faixa"]
    assert maximo - minimo <= 4
    assert largo["potencial_faixa"][0] <= minimo and maximo <= largo["potencial_faixa"][1]


def test_o_proprio_elenco_e_exato():
    m = mercado_service.ver_mercado(_iniciar())
    assert all(f["potencial_faixa"] is None for f in m["elenco"])


def test_descer_e_de_graca():
    sid = _iniciar()
    olheiro_service.trocar(sid, 3)
    caixa = olheiro_service.ver(sid)["caixa"]
    v = olheiro_service.trocar(sid, 1)
    assert v["nivel"] == 1 and v["caixa"] == caixa


def test_troca_invalida():
    sid = _iniciar()
    with pytest.raises(TrocaInvalida):
        olheiro_service.trocar(sid, 1)    # já é
    with pytest.raises(TrocaInvalida):
        olheiro_service.trocar(sid, 9)


def test_api_do_olheiro():
    sid = _iniciar()
    assert client.get(f"/simulacoes/{sid}/olheiro").json()["nivel"] == 1
    r = client.post(f"/simulacoes/{sid}/olheiro", json={"nivel": 2})
    assert r.status_code == 200 and r.json()["nivel"] == 2
    assert client.post(f"/simulacoes/{sid}/olheiro", json={"nivel": 0}).status_code == 400
    assert client.get("/simulacoes/99999/olheiro").status_code == 404


def test_pagina_do_jogador_mostra_a_faixa_so_de_quem_e_de_fora():
    sid = _iniciar()
    m = mercado_service.ver_mercado(sid)
    de_fora = _jovem_de_fora(m)
    meu = m["elenco"][0]

    pagina = simulacao_service.game_log_jogador(sid, de_fora["jogador_id"])["jogador"]
    assert pagina["potencial_faixa"] == de_fora["potencial_faixa"]
    assert pagina["potencial"] == de_fora["potencial"]
    pagina = simulacao_service.game_log_jogador(sid, meu["jogador_id"])["jogador"]
    assert pagina["potencial_faixa"] is None and pagina["potencial"] == meu["potencial"]


def test_na_virada_o_olheiro_renova_pela_temporada_cheia(cargo_garantido):
    clube = simulacao_service.listar_clubes()[0]["nome"]
    sid = simulacao_service.salvar_temporada(seed=3, clube_usuario=clube)
    conn = conectar()
    try:
        with conn:
            conn.execute(
                "UPDATE clube SET nivel_olheiro = 4 WHERE simulacao_id = ? AND nome = ?",
                (sid, clube),
            )
    finally:
        conn.close()

    nova = carreira_service.proxima_temporada(sid)["simulacao_id"]
    v = olheiro_service.ver(nova)
    assert v["nivel"] == 4
    assert v["gasto_temporada"] == olheiro.custo_temporada(4)

    # as joias dos outros clubes aparecem com a faixa do olheiro
    movs = simulacao_service.carregar_temporada(nova)["movimentos_virada"]
    joias = [m for m in movs if m["tipo"] == "subiu_da_base" and m["clube"] != clube]
    assert joias and all("–" in m["detalhe"] for m in joias)
