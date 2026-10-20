"""Ofertas da CPU (v1.7) de ponta a ponta: quando chegam, quando caem e a
resposta do técnico."""

import json

import pytest

from app.db.conexao import conectar
from app.domain import ofertas
from app.domain.mercado import TransferenciaInvalida
from app.repositories import mensagem_repository as mensagem_repo
from app.repositories import simulacao_repository as simulacao_repo
from app.services import mercado_service, temporada_service
from tests.negociar import oferecer

CLUBE = "Real Taldo"


@pytest.fixture(autouse=True)
def _sem_sonho(monkeypatch, request):
    """O chamado do clube do sonho (v1.9) traria ofertas a mais: tem os
    testes dele no fim do arquivo."""
    if "sonho" not in request.node.name:
        monkeypatch.setattr(ofertas, "CHANCE_SONHO", 0.0)


@pytest.fixture
def sem_assedio(monkeypatch):
    monkeypatch.setattr(ofertas, "CHANCE_ASSEDIO", 0.0)


@pytest.fixture
def sempre_interessa(monkeypatch):
    """Quem está à venda sempre recebe ao menos uma oferta."""
    monkeypatch.setattr(ofertas, "CHANCE_NENHUMA", 0.0)


def _iniciar(seed=11):
    return temporada_service.iniciar(seed=seed, clube_usuario=CLUBE)


def _assuntos(sid):
    conn = conectar()
    try:
        return [m["assunto"] for m in mensagem_repo.listar(conn, sid)]
    finally:
        conn.close()


def _rng(sid):
    conn = conectar()
    try:
        return json.loads(simulacao_repo.buscar(conn, sid)["estado_json"])["rng"]
    finally:
        conn.close()


def _reserva(m):
    return min(
        (f for f in m["elenco"] if f["posicao"] != "Goleiro"),
        key=lambda f: f["overall"],
    )


def test_assedio_chega_na_pre_temporada(monkeypatch):
    monkeypatch.setattr(ofertas, "CHANCE_ASSEDIO", 1.0)
    sid = _iniciar()
    m = mercado_service.ver_mercado(sid)
    (o,) = m["ofertas_recebidas"]
    assert o["espontanea"] and o["status"] == "aberta"
    melhores = sorted(m["elenco"], key=lambda f: -f["overall"])[: ofertas.CRAQUES_ASSEDIADOS]
    assert o["jogador"] in {f["nome"] for f in melhores}
    assert o["valor"] >= o["valor_mercado"] * 1.2 - 10_000
    assert f"O {o['clube']} quer {o['jogador']}" in _assuntos(sid)
    ficha = next(f for f in m["elenco"] if f["nome"] == o["jogador"])
    assert ficha["ofertas"] == 1


def test_por_na_lista_com_a_janela_aberta_traz_ofertas_na_hora(sem_assedio, sempre_interessa):
    sid = _iniciar()
    alvo = _reserva(mercado_service.ver_mercado(sid))

    r = mercado_service.marcar_a_venda(sid, alvo["jogador_id"], True)
    assert r["ofertas"] >= 1
    lista = mercado_service.ofertas(sid, alvo["jogador_id"])["ofertas"]
    assert len(lista) == r["ofertas"]
    assert all(not o["espontanea"] and o["valor"] < alvo["valor_mercado"] * 1.15 for o in lista)
    assert any("pela lista de transferências" in a for a in _assuntos(sid))

    # tirar e pôr de novo não sorteia outra vez
    mercado_service.marcar_a_venda(sid, alvo["jogador_id"], False)
    assert mercado_service.marcar_a_venda(sid, alvo["jogador_id"], True)["ofertas"] == 0
    assert len(mercado_service.ofertas(sid, alvo["jogador_id"])["ofertas"]) == r["ofertas"]


def test_fora_da_janela_a_lista_espera_a_proxima(sem_assedio, sempre_interessa):
    sid = _iniciar()
    temporada_service.avancar(sid)
    alvo = _reserva(mercado_service.ver_mercado(sid))
    assert mercado_service.marcar_a_venda(sid, alvo["jogador_id"], True)["ofertas"] == 0

    while mercado_service.ver_mercado(sid)["rodada"] < 20:
        temporada_service.avancar(sid)
    m = mercado_service.ver_mercado(sid)
    assert m["janela_aberta"]
    abertas = [o for o in m["ofertas_recebidas"] if o["jogador_id"] == alvo["jogador_id"]]
    assert abertas and all(o["status"] == "aberta" for o in abertas)

    # jogar a rodada sem responder: elas caem
    temporada_service.avancar(sid)
    conn = conectar()
    try:
        status = {r["status"] for r in conn.execute(
            "SELECT status FROM oferta_recebida WHERE simulacao_id = ?", (sid,))}
    finally:
        conn.close()
    assert status == {"expirada"}


def test_contraproposta_dentro_do_teto_fecha_pelo_pedido():
    sid = _iniciar()
    m = mercado_service.ver_mercado(sid)
    alvo = _reserva(m)
    clube = next(f["clube"] for f in m["disponiveis"] if not f["rival"])
    oid = oferecer(sid, alvo["jogador_id"], clube, 1_000_000, teto=1_200_000)

    r = mercado_service.contrapropor_oferta(sid, oid, 1_200_000)
    assert r["resposta"] == "aceita"
    assert r["transferencia"]["valor"] == 1_200_000
    assert r["caixa"] == m["caixa"] + 1_200_000


def test_contraproposta_acima_do_teto_faz_o_clube_retirar():
    sid = _iniciar()
    m = mercado_service.ver_mercado(sid)
    alvo = _reserva(m)
    clube = next(f["clube"] for f in m["disponiveis"] if not f["rival"])
    oid = oferecer(sid, alvo["jogador_id"], clube, 1_000_000, teto=1_100_000)

    r = mercado_service.contrapropor_oferta(sid, oid, 1_500_000)
    assert r == {"resposta": "retirada", "transferencia": None, "caixa": m["caixa"]}
    o = next(o for o in mercado_service.ver_mercado(sid)["ofertas_recebidas"] if o["oferta_id"] == oid)
    assert o["status"] == "retirada" and o["pedido"] == 1_500_000
    assert f"O {clube} desistiu de {alvo['nome']}" in _assuntos(sid)
    # uma vez só
    with pytest.raises(TransferenciaInvalida):
        mercado_service.contrapropor_oferta(sid, oid, 1_050_000)


def test_dispensar_derruba_as_ofertas_por_ele():
    sid = _iniciar()
    m = mercado_service.ver_mercado(sid)
    alvo = _reserva(m)
    clube = next(f["clube"] for f in m["disponiveis"] if not f["rival"])
    oid = oferecer(sid, alvo["jogador_id"], clube, 1_000_000)
    mercado_service.dispensar(sid, alvo["jogador_id"])
    o = next(o for o in mercado_service.ver_mercado(sid)["ofertas_recebidas"] if o["oferta_id"] == oid)
    assert o["status"] == "retirada"


def test_ofertas_nao_mexem_na_sorte_da_temporada(monkeypatch, sempre_interessa):
    monkeypatch.setattr(ofertas, "CHANCE_ASSEDIO", 1.0)
    sem = _iniciar(seed=21)
    com = _iniciar(seed=21)
    alvo = _reserva(mercado_service.ver_mercado(com))
    mercado_service.marcar_a_venda(com, alvo["jogador_id"], True)
    assert _rng(sem) == _rng(com)


# --- o chamado do clube do sonho (v1.9) --------------------------------------

def _oferta_do_sonho(monkeypatch):
    monkeypatch.setattr(ofertas, "CHANCE_ASSEDIO", 0.0)
    monkeypatch.setattr(ofertas, "CHANCE_SONHO", 1.0)
    sid = _iniciar()
    m = mercado_service.ver_mercado(sid)
    (o,) = [o for o in m["ofertas_recebidas"] if o["sonho"]]
    return sid, o


def _humor(sid, nome):
    m = mercado_service.ver_mercado(sid)
    return next(f for f in m["elenco"] if f["nome"] == nome)["humor"]


def test_sonho_chega_na_pre_temporada(monkeypatch):
    sid, o = _oferta_do_sonho(monkeypatch)
    ficha = next(f for f in mercado_service.ver_mercado(sid)["elenco"] if f["nome"] == o["jogador"])
    assert ficha["sonho"] == o["clube"]
    assert f"O {o['clube']}, clube do sonho de {o['jogador']}" in _assuntos(sid)


def test_sonho_recusado_deixa_o_jogador_incomodado(monkeypatch):
    sid, o = _oferta_do_sonho(monkeypatch)
    assert _humor(sid, o["jogador"]) == "contente"
    mercado_service.recusar_oferta(sid, o["oferta_id"])
    assert _humor(sid, o["jogador"]) == "incomodado"
    assert f"{o['jogador']} queria o {o['clube']}" in _assuntos(sid)


def test_sonho_que_expira_tambem_chateia(monkeypatch):
    sid, o = _oferta_do_sonho(monkeypatch)
    temporada_service.avancar(sid)
    assert _humor(sid, o["jogador"]) == "incomodado"
