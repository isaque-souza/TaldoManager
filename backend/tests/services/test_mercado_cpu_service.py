"""Clubes da CPU negociam entre si (v1.7) de ponta a ponta: as janelas,
o histórico e o aviso."""

from app.db.conexao import conectar
from app.repositories import mensagem_repository as mensagem_repo
from app.repositories import transferencia_repository as transferencia_repo
from app.services import mercado_service, temporada_service

CLUBE = "Real Taldo"


def _da_cpu(sid):
    conn = conectar()
    try:
        return [
            r for r in transferencia_repo.listar_por_simulacao(conn, sid)
            if CLUBE not in (r["de_clube"], r["para_clube"])
        ]
    finally:
        conn.close()


def _avisos(sid):
    conn = conectar()
    try:
        return [m for m in mensagem_repo.listar(conn, sid) if m["assunto"] == "Movimentações do mercado"]
    finally:
        conn.close()


def test_a_cpu_negocia_nas_duas_janelas():
    sid = temporada_service.iniciar(seed=11, clube_usuario=CLUBE)
    pre = _da_cpu(sid)
    assert pre and {r["rodada"] for r in pre} == {1}
    assert len(_avisos(sid)) == 1

    # o elenco gravado já é o de depois dos negócios
    m = mercado_service.ver_mercado(sid)
    r = pre[0]
    assert next(f for f in m["disponiveis"] if f["nome"] == r["jogador"])["clube"] == r["para_clube"]
    # e o histórico do técnico não mostra os negócios dos outros
    assert mercado_service.historico(sid)["movimentos"] == []

    for _ in range(19):
        temporada_service.avancar(sid)
    assert {r["rodada"] for r in _da_cpu(sid)} <= {1, 20}
    assert len(_avisos(sid)) == 1 + bool([r for r in _da_cpu(sid) if r["rodada"] == 20])


def test_mesma_seed_mesmos_negocios():
    a = temporada_service.iniciar(seed=5, clube_usuario=CLUBE)
    b = temporada_service.iniciar(seed=5, clube_usuario=CLUBE)
    chave = lambda sid: [(r["jogador"], r["de_clube"], r["para_clube"], r["valor"]) for r in _da_cpu(sid)]
    assert chave(a) == chave(b)
