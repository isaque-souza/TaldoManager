"""Campanhas de marketing (v1.4): gastar caixa para a torcida crescer."""

import pytest
from fastapi.testclient import TestClient

from app.db.conexao import conectar
from app.domain import torcida
from app.domain.clube import Clube
from app.main import app
from app.repositories import mensagem_repository
from app.services import marketing_service, simulacao_service, temporada_service
from app.services.marketing_service import CampanhaInvalida
from app.services.temporada_service import TemporadaConcluida

client = TestClient(app)


# ---------------------------------------------------------------------------
# regras (domínio)
# ---------------------------------------------------------------------------

def test_custo_por_torcedor_novo_sobe_com_o_tamanho_da_campanha():
    t = 5_000_000
    por_torcedor = [
        torcida.custo_da_campanha(tipo, t) / (t * c["ganho"])
        for tipo, c in torcida.CAMPANHAS.items()
    ]
    assert por_torcedor == sorted(por_torcedor)
    # torcida pequena ainda paga o mínimo
    assert torcida.custo_da_campanha("redes", 100_000) == torcida.CAMPANHA_CUSTO_MINIMO


def test_turno():
    assert torcida.turno(1, 38) == torcida.turno(19, 38) == 1
    assert torcida.turno(20, 38) == torcida.turno(38, 38) == 2


def test_bloqueios_da_campanha():
    clube = Clube("Teste", "Brasil", 10_000_000, 1_000_000)
    assert torcida.motivo_campanha_bloqueada(clube, "nacional", 0) is None
    assert "Já houve" in torcida.motivo_campanha_bloqueada(clube, "redes", 1)
    assert "desconhecida" in torcida.motivo_campanha_bloqueada(clube, "outdoor", 0)
    clube.dinheiro = 1_000
    assert "caixa" in torcida.motivo_campanha_bloqueada(clube, "redes", 0)


def test_lancar_campanha_cobra_e_traz_torcida():
    clube = Clube("Teste", "Brasil", 10_000_000, 1_000_000)
    custo, antes, depois = torcida.lancar_campanha(clube, "cidade")
    assert (antes, depois) == (1_000_000, 1_030_000)
    assert custo == torcida.custo_da_campanha("cidade", 1_000_000)
    assert clube.dinheiro == 10_000_000 - custo
    assert clube.despesa_marketing == custo


# ---------------------------------------------------------------------------
# serviço e API
# ---------------------------------------------------------------------------

def _iniciar(clube="Real Taldo"):
    return temporada_service.iniciar(seed=11, clube_usuario=clube)


def _financas(sid, clube="Real Taldo"):
    return next(
        f for f in simulacao_service.carregar_temporada(sid)["financas"]
        if f["clube"] == clube
    )


def test_ver_marketing_mostra_torcida_mando_e_campanhas():
    sid = _iniciar()
    m = marketing_service.ver(sid)
    assert m["turno"] == 1 and m["disponivel"]
    # o mando vem do público de um jogo comum (v1.5)
    assert 1.5 <= m["mando_de_campo"] <= 3.5
    assert [c["tipo"] for c in m["campanhas"]] == list(torcida.CAMPANHAS)
    assert all(c["bloqueio"] is None for c in m["campanhas"])
    assert m["feitas"] == []


def test_campanha_grava_torcida_caixa_e_mensagem():
    sid = _iniciar()
    antes = _financas(sid)
    m = marketing_service.lancar(sid, "redes")

    depois = _financas(sid)
    custo = m["feitas"][0]["custo"]
    assert depois["torcedores"] == round(antes["torcedores"] * 1.01)
    assert depois["caixa"] == antes["caixa"] - custo
    assert depois["despesas"] == antes["despesas"] + custo
    assert m["torcedores"] == depois["torcedores"]
    assert not m["disponivel"]
    assert all(c["bloqueio"] for c in m["campanhas"])

    conn = conectar()
    try:
        assuntos = [r["assunto"] for r in mensagem_repository.listar(conn, sid)]
    finally:
        conn.close()
    assert "Ação nas redes sociais: no ar" in assuntos

    # a torcida maior segue na rodada seguinte (veio do snapshot)
    temporada_service.avancar(sid)
    assert _financas(sid)["torcedores_inicial"] == antes["torcedores_inicial"]


def test_uma_campanha_por_turno():
    sid = _iniciar()
    marketing_service.lancar(sid, "redes")
    with pytest.raises(CampanhaInvalida, match="neste turno"):
        marketing_service.lancar(sid, "nacional")


def test_campanha_sem_caixa_e_recusada(monkeypatch):
    sid = _iniciar()
    monkeypatch.setattr(torcida, "CAMPANHA_CUSTO_MINIMO", 10**12)   # ninguém paga
    assert all("caixa" in c["bloqueio"] for c in marketing_service.ver(sid)["campanhas"])
    with pytest.raises(CampanhaInvalida, match="caixa"):
        marketing_service.lancar(sid, "redes")


def test_temporada_concluida_nao_tem_marketing():
    sid = simulacao_service.salvar_temporada(seed=3, clube_usuario="Real Taldo")
    with pytest.raises(TemporadaConcluida):
        marketing_service.ver(sid)


def test_rotas_de_marketing():
    sid = _iniciar()
    r = client.get(f"/simulacoes/{sid}/marketing")
    assert r.status_code == 200 and r.json()["disponivel"]

    r = client.post(f"/simulacoes/{sid}/marketing", json={"tipo": "cidade"})
    assert r.status_code == 200
    assert r.json()["feitas"][0]["nome"] == "Campanha na cidade"

    r = client.post(f"/simulacoes/{sid}/marketing", json={"tipo": "redes"})
    assert r.status_code == 400 and "turno" in r.json()["detail"]

    assert client.get("/simulacoes/99999/marketing").status_code == 404
