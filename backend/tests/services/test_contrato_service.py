"""Renovação de contrato de ponta a ponta: serviço + banco + snapshot."""

import pytest

from app.db.conexao import conectar
from app.domain import contrato
from app.domain.contrato import ContratoInvalido
from app.services import contrato_service, mercado_service, simulacao_service, temporada_service
from app.services.temporada_service import TemporadaConcluida


def _iniciar(seed=11):
    sid = temporada_service.iniciar(seed=seed, clube_usuario="Real Taldo")
    elenco = mercado_service.ver_mercado(sid)["elenco"]
    return sid, elenco


def _pedido(sid, jogador_id, multa):
    conn = conectar()
    try:
        ctx = mercado_service._carregar(conn, sid)
        jogador, _ = ctx.jogador(jogador_id)
        return contrato.salario_pedido(jogador, ctx.alvo, multa)
    finally:
        conn.close()


def _jovem(elenco):
    return next(f for f in elenco if f["idade"] < contrato.IDADE_VETERANO)


def test_ver_contrato_mostra_opcoes_sem_revelar_o_pedido():
    sid, elenco = _iniciar()
    f = _jovem(elenco)
    c = contrato_service.ver_contrato(sid, f["jogador_id"])
    assert c["salario"] == f["salario"]
    assert c["duracao_max"] == contrato.DURACAO_MAX
    assert [o["opcao"] for o in c["opcoes_multa"]] == ["sem", "2x", "3x", "5x"]
    assert c["opcoes_multa"][0]["valor"] is None
    assert "salario_pedido" not in c
    assert c["tentativas_restantes"] == contrato.MAX_TENTATIVAS


def test_renovacao_aceita_muda_contrato_e_folha_e_sobrevive_a_rodada():
    sid, elenco = _iniciar()
    f = _jovem(elenco)
    pedido = _pedido(sid, f["jogador_id"], "5x")

    r = contrato_service.renovar(sid, f["jogador_id"], pedido, 5, "5x")
    assert r["resposta"] == "aceita"
    assert r["contrato"]["salario"] == pedido
    assert r["contrato"]["contrato_anos"] == 5

    temporada_service.avancar(sid)
    c = contrato_service.ver_contrato(sid, f["jogador_id"])
    assert c["salario"] == pedido and c["contrato_anos"] == 5
    assert c["multa_rescisoria"] == r["contrato"]["multa_rescisoria"]


def test_contraproposta_e_aceite_mesmo_no_limite():
    sid, elenco = _iniciar()
    f = _jovem(elenco)
    pedido = _pedido(sid, f["jogador_id"], "3x")

    contrato_service.renovar(sid, f["jogador_id"], pedido // 3, 3, "3x")   # recusa
    contrato_service.renovar(sid, f["jogador_id"], pedido // 3, 3, "3x")   # recusa
    contra = contrato_service.renovar(sid, f["jogador_id"], int(pedido * 0.95), 3, "3x")
    assert contra["resposta"] == "contraproposta"
    assert contra["salario_pedido"] == pedido
    assert contra["tentativas_restantes"] == 0

    # nova proposta qualquer: bloqueada; aceitar a contraproposta: vale
    with pytest.raises(ContratoInvalido, match="não quer mais"):
        contrato_service.renovar(sid, f["jogador_id"], pedido, 4, "3x")
    ok = contrato_service.renovar(sid, f["jogador_id"], pedido, 3, "3x")
    assert ok["resposta"] == "aceita"


def test_tentativas_renovam_a_cada_rodada():
    sid, elenco = _iniciar()
    f = _jovem(elenco)
    for _ in range(contrato.MAX_TENTATIVAS):
        contrato_service.renovar(sid, f["jogador_id"], 1_000, 3, "3x")
    assert contrato_service.ver_contrato(sid, f["jogador_id"])["tentativas_restantes"] == 0
    temporada_service.avancar(sid)
    assert contrato_service.ver_contrato(sid, f["jogador_id"])["tentativas_restantes"] == contrato.MAX_TENTATIVAS


def test_renovar_fora_da_janela_de_transferencias():
    sid, elenco = _iniciar()
    temporada_service.avancar(sid)   # rodada 2: janela fechada
    f = _jovem(elenco)
    pedido = _pedido(sid, f["jogador_id"], "3x")
    assert contrato_service.renovar(sid, f["jogador_id"], pedido, 2, "3x")["resposta"] == "aceita"


def test_proposta_invalida_nao_gasta_tentativa():
    sid, elenco = _iniciar()
    f = _jovem(elenco)
    with pytest.raises(ContratoInvalido):
        contrato_service.renovar(sid, f["jogador_id"], 100_000, 9, "3x")
    assert contrato_service.ver_contrato(sid, f["jogador_id"])["tentativas_restantes"] == contrato.MAX_TENTATIVAS


def test_nao_renova_jogador_de_outro_clube():
    sid, _ = _iniciar()
    outro = mercado_service.ver_mercado(sid)["disponiveis"][0]
    with pytest.raises(ContratoInvalido, match="não é do seu elenco"):
        contrato_service.renovar(sid, outro["jogador_id"], 100_000, 3, "3x")


def test_sem_renovacao_em_temporada_concluida_e_inexistentes():
    sid = simulacao_service.salvar_temporada(seed=3)
    with pytest.raises(TemporadaConcluida):
        contrato_service.ver_contrato(sid, 1)
    assert contrato_service.ver_contrato(999_999, 1) is None
    sid2, _ = _iniciar()
    assert contrato_service.renovar(sid2, 999_999, 1_000, 3, "3x") is None
