"""Negociação em duas etapas (v1.7) de ponta a ponta."""

import pytest

from app.db.conexao import conectar
from app.domain import contrato
from app.domain.mercado import TransferenciaInvalida
from app.repositories import mensagem_repository as mensagem_repo
from app.services import mercado_service, temporada_service

CLUBE = "Real Taldo"


def _acordo(seed=11):
    """Um acordo com o clube (etapa 1 fechada): (sid, ficha do alvo, caixa
    antes, resposta da proposta)."""
    sid = temporada_service.iniciar(seed=seed, clube_usuario=CLUBE)
    m = mercado_service.ver_mercado(sid)
    alvo = next(
        f for f in m["disponiveis"]
        if f["bloqueio"] is None and not f["rival"] and f["valor_mercado"] * 3 < m["caixa"]
    )
    r = mercado_service.propor(sid, alvo["jogador_id"], alvo["valor_mercado"] * 3)
    assert r["resposta"] in ("aceita", "multa") and r["negociacao_id"]
    return sid, alvo, m["caixa"], r


def _assuntos(sid):
    conn = conectar()
    try:
        return [m["assunto"] for m in mensagem_repo.listar(conn, sid)]
    finally:
        conn.close()


def test_acordo_com_o_clube_trava_o_valor_mas_nao_paga_nada():
    sid, alvo, caixa, r = _acordo()
    m = mercado_service.ver_mercado(sid)
    assert m["caixa"] == caixa
    assert alvo["nome"] not in {f["nome"] for f in m["elenco"]}
    (neg,) = m["negociacoes"]
    assert neg["status"] == "aberta" and neg["clube"] == alvo["clube"]
    assert neg["tentativas_restantes"] == contrato.MAX_TENTATIVAS
    ficha = next(f for f in m["disponiveis"] if f["nome"] == alvo["nome"])
    assert ficha["negociacao"]["negociacao_id"] == r["negociacao_id"]
    # com acordo aberto, não dá para propor de novo pelo mesmo jogador
    with pytest.raises(TransferenciaInvalida, match="falta o contrato"):
        mercado_service.propor(sid, alvo["jogador_id"], alvo["valor_mercado"] * 4)


def test_contraproposta_do_jogador_e_aceita_com_o_papel_combinado():
    sid, alvo, caixa, r = _acordo()
    neg_id = r["negociacao_id"]
    d = mercado_service.ver_negociacao(sid, neg_id)
    pedido = _pedido(sid, neg_id, "titular")

    contra = mercado_service.propor_contrato(sid, neg_id, int(pedido * 0.95), 2, "3x", "titular")
    assert contra["resposta"] == "contraproposta" and contra["salario_pedido"] == pedido
    assert contra["status"] == "aberta"
    assert mercado_service.ver_negociacao(sid, neg_id)["contraproposta"]["papel"] == "titular"

    fechou = mercado_service.propor_contrato(sid, neg_id, pedido, 2, "3x", "titular")
    assert fechou["status"] == "fechada"
    assert fechou["transferencia"]["valor"] == d["valor"]
    assert fechou["caixa"] == caixa - d["valor"]
    meu = next(f for f in mercado_service.ver_mercado(sid)["elenco"] if f["nome"] == alvo["nome"])
    assert meu["salario"] == pedido and meu["contrato_anos"] == 2 and meu["papel"] == "titular"
    assert f"Contratado: {alvo['nome']}" in _assuntos(sid)


def _pedido(sid, neg_id, papel):
    conn = conectar()
    try:
        ctx = mercado_service._carregar(conn, sid)
        neg = mercado_service._buscar_negociacao(ctx, neg_id)
        jogador, vendedor = mercado_service._partes(ctx, neg)
        interesse = mercado_service._interesse(ctx, jogador, vendedor)   # v1.9
        return contrato.salario_pedido_chegada(
            jogador, ctx.alvo, vendedor, "3x", papel, interesse,
        )
    finally:
        conn.close()


def test_tres_recusas_e_ele_desiste_e_nao_volta_na_janela():
    sid, alvo, caixa, r = _acordo()
    neg_id = r["negociacao_id"]
    for i in range(contrato.MAX_TENTATIVAS):
        resp = mercado_service.propor_contrato(sid, neg_id, 1_000, 1, "3x")
        assert resp["resposta"] == "recusada"
    assert resp["status"] == "desistiu"
    assert f"{alvo['nome']} desistiu" in _assuntos(sid)
    with pytest.raises(TransferenciaInvalida, match="já terminou"):
        mercado_service.propor_contrato(sid, neg_id, 10**9, 1, "3x")
    with pytest.raises(TransferenciaInvalida, match="desistiu"):
        mercado_service.propor(sid, alvo["jogador_id"], alvo["valor_mercado"] * 5)
    assert mercado_service.ver_mercado(sid)["caixa"] == caixa


def test_acordo_sem_contrato_cai_quando_a_rodada_e_jogada():
    sid, alvo, caixa, r = _acordo()
    temporada_service.avancar(sid)
    assert "Acordos que caíram" in _assuntos(sid)
    d = mercado_service.ver_negociacao(sid, r["negociacao_id"])
    assert d["status"] == "expirada"


def test_contrato_invalido_nao_gasta_tentativa():
    sid, alvo, caixa, r = _acordo()
    with pytest.raises(contrato.ContratoInvalido):
        mercado_service.propor_contrato(sid, r["negociacao_id"], 1_000_000, 9, "3x")
    d = mercado_service.ver_negociacao(sid, r["negociacao_id"])
    assert d["tentativas_restantes"] == contrato.MAX_TENTATIVAS


def test_negociacao_de_outra_simulacao_e_none():
    sid, alvo, caixa, r = _acordo()
    outra = temporada_service.iniciar(seed=2, clube_usuario=CLUBE)
    assert mercado_service.ver_negociacao(outra, r["negociacao_id"]) is None
    assert mercado_service.propor_contrato(outra, r["negociacao_id"], 1, 1, "3x") is None
