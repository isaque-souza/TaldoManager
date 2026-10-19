"""Empréstimos (v1.7) de ponta a ponta: pedir, a volta ao clube de origem
e a opção de compra."""

import pytest

from app.db.conexao import conectar
from app.domain import emprestimo
from app.domain.contrato import ContratoInvalido
from app.domain.mercado import TransferenciaInvalida
from app.repositories import mensagem_repository as mensagem_repo
from app.services import contrato_service, emprestimo_service, mercado_service, temporada_service
from tests.negociar import fechar

CLUBE = "Real Taldo"


def _iniciar(seed=11):
    return temporada_service.iniciar(seed=seed, clube_usuario=CLUBE)


def _assuntos(sid):
    conn = conectar()
    try:
        return [m["assunto"] for m in mensagem_repo.listar(conn, sid)]
    finally:
        conn.close()


def _emprestavel(m):
    """O melhor de outro clube que o clube aceita emprestar."""
    return next(
        f for f in m["disponiveis"]
        if f["pedir_emprestado"]["bloqueio"] is None
    )


def _no_elenco(sid, nome):
    m = mercado_service.ver_mercado(sid)
    return next((f for f in m["elenco"] if f["nome"] == nome), None), m


def _pedir_alto(sid, f, duracao="turno", parte=75, opcao=False):
    """Uma taxa que qualquer clube aceita."""
    taxa = 3 * f["pedir_emprestado"]["duracoes"][0]["taxas"]["50"]
    return emprestimo_service.pedir(sid, f["jogador_id"], duracao, parte, taxa, opcao)


def _jogar(sid, n):
    for _ in range(n):
        temporada_service.avancar(sid)


def test_a_ficha_mostra_o_que_da_para_pedir():
    sid = _iniciar()
    m = mercado_service.ver_mercado(sid)
    f = _emprestavel(m)
    p = f["pedir_emprestado"]
    assert [d["duracao"] for d in p["duracoes"]] == ["turno", "temporada"]
    assert [d["volta"] for d in p["duracoes"]] == [20, 39]
    assert p["opcao_compra"] > f["valor_mercado"]
    assert p["propostas_restantes"] == 3
    # titular lá não sai emprestado
    titulares = [x for x in m["disponiveis"] if x["pedir_emprestado"]["bloqueio"]]
    assert any("titular" in x["pedir_emprestado"]["bloqueio"] for x in titulares)


def test_pedir_com_taxa_alta_traz_o_jogador_na_hora():
    sid = _iniciar()
    m = mercado_service.ver_mercado(sid)
    f = _emprestavel(m)
    caixa = m["caixa"]

    r = _pedir_alto(sid, f)
    assert r["resposta"] == "aceita"
    e = r["emprestimo"]
    assert e["status"] == "ativo" and e["volta"] == 20 and e["de_clube"] == f["clube"]
    assert r["caixa"] == caixa - e["taxa"]

    meu, m = _no_elenco(sid, f["nome"])
    assert meu["emprestimo"]["de_clube"] == f["clube"]
    assert "emprestado" in meu["bloqueio"]
    assert m["emprestimos"][0]["emprestimo_id"] == e["emprestimo_id"]
    assert any(t["tipo"] == "emprestimo" for t in m["transferencias"])
    assert f"Emprestado: {f['nome']}" in _assuntos(sid)

    h = mercado_service.historico(sid)
    assert h["movimentos"][0]["tipo"] == "emprestimo"
    assert h["total"]["gasto"] == e["taxa"]

    # o contrato é do clube de origem
    with pytest.raises(ContratoInvalido, match="emprestado"):
        contrato_service.renovar(sid, f["jogador_id"], 10**6, 2, "sem")
    with pytest.raises(TransferenciaInvalida, match="emprestado"):
        mercado_service.marcar_a_venda(sid, f["jogador_id"], True)
    with pytest.raises(TransferenciaInvalida, match="emprestado"):
        mercado_service.dispensar(sid, f["jogador_id"])


def test_contraproposta_e_limite_de_pedidos():
    sid = _iniciar()
    f = _emprestavel(mercado_service.ver_mercado(sid))
    base = f["pedir_emprestado"]["duracoes"][1]["taxas"]["75"]

    r = None
    for fator in (0.9, 1.0, 1.1, 1.3):
        r = emprestimo_service.pedir(sid, f["jogador_id"], "temporada", 75, int(base * fator) // 10_000 * 10_000)
        if r["resposta"] == "contraproposta":
            break
    assert r["resposta"] == "contraproposta", r
    ficha = next(x for x in mercado_service.ver_mercado(sid)["disponiveis"] if x["nome"] == f["nome"])
    contra = ficha["pedir_emprestado"]["contraproposta"]
    assert contra["taxa"] == r["taxa_pedida"] and contra["duracao"] == "temporada"

    aceito = emprestimo_service.pedir(sid, f["jogador_id"], "temporada", 75, contra["taxa"])
    assert aceito["resposta"] == "aceita"


def test_tres_recusas_encerram_as_conversas():
    sid = _iniciar()
    f = _emprestavel(mercado_service.ver_mercado(sid))
    for _ in range(3):
        assert emprestimo_service.pedir(sid, f["jogador_id"], "turno", 75, 10_000)["resposta"] == "recusada"
    with pytest.raises(TransferenciaInvalida, match="encerrou as conversas"):
        emprestimo_service.pedir(sid, f["jogador_id"], "turno", 75, 10_000)


def test_fora_da_janela_nao_pede(monkeypatch):
    sid = _iniciar()
    f = _emprestavel(mercado_service.ver_mercado(sid))
    _jogar(sid, 1)
    with pytest.raises(TransferenciaInvalida, match="fechada"):
        _pedir_alto(sid, f)


def test_volta_ao_clube_de_origem_na_virada_do_turno():
    sid = _iniciar()
    f = _emprestavel(mercado_service.ver_mercado(sid))
    _pedir_alto(sid, f, duracao="turno")

    _jogar(sid, 18)
    assert _no_elenco(sid, f["nome"])[0] is not None
    _jogar(sid, 1)
    meu, m = _no_elenco(sid, f["nome"])
    assert meu is None
    origem = next(x for x in m["disponiveis"] if x["nome"] == f["nome"])
    assert origem["clube"] == f["clube"] and origem["emprestimo"] is None
    assert m["emprestimos"][0]["status"] == "encerrado"
    assert "Fim de empréstimo" in _assuntos(sid)


def test_opcao_de_compra_em_qualquer_rodada():
    sid = _iniciar()
    f = _emprestavel(mercado_service.ver_mercado(sid))
    r = _pedir_alto(sid, f, duracao="temporada", opcao=True)
    e = r["emprestimo"]
    assert e["opcao_compra"] == f["pedir_emprestado"]["opcao_compra"]

    _jogar(sid, 3)   # janela fechada: a opção é cláusula
    caixa = mercado_service.ver_mercado(sid)["caixa"]
    neg = emprestimo_service.exercer_opcao(sid, e["emprestimo_id"])
    assert neg["valor"] == e["opcao_compra"] and neg["clube"] == f["clube"]
    contrato = fechar(sid, neg["negociacao_id"])

    meu, m = _no_elenco(sid, f["nome"])
    assert meu is not None and meu["emprestimo"] is None
    assert contrato["caixa"] == caixa - e["opcao_compra"]
    assert next(x for x in m["emprestimos"] if x["emprestimo_id"] == e["emprestimo_id"])["status"] == "comprado"
    assert any(t["tipo"] == "transferencia" and t["jogador"] == f["nome"] for t in m["transferencias"])


def test_sem_opcao_nao_exerce():
    sid = _iniciar()
    f = _emprestavel(mercado_service.ver_mercado(sid))
    e = _pedir_alto(sid, f)["emprestimo"]
    with pytest.raises(TransferenciaInvalida, match="não tem opção"):
        emprestimo_service.exercer_opcao(sid, e["emprestimo_id"])


def test_aviso_da_opcao_antes_do_fim(monkeypatch):
    sid = _iniciar()
    f = _emprestavel(mercado_service.ver_mercado(sid))
    _pedir_alto(sid, f, duracao="turno", opcao=True)
    _jogar(sid, 19 - emprestimo.AVISO_OPCAO)
    assert f"O empréstimo de {f['nome']} está acabando" in _assuntos(sid)


# --- o técnico empresta os dele (parte 2) ---

def _cedivel(m):
    """Um jogador do elenco com clube interessado na temporada toda."""
    for f in sorted(m["elenco"], key=lambda f: f["overall"]):
        e = f["emprestar"]
        if e and not e["bloqueio"]:
            d = next(d for d in e["duracoes"] if d["duracao"] == "temporada")
            if d["propostas"]:
                return f, d["propostas"][0]
    raise AssertionError("ninguém quer ninguém")


def test_emprestar_um_jogador_do_tecnico():
    sid = _iniciar()
    m = mercado_service.ver_mercado(sid)
    f, proposta = _cedivel(m)
    caixa_antes = m["caixa"]

    feito = emprestimo_service.ceder(sid, f["jogador_id"], proposta["clube"], "temporada")
    e = feito["emprestimo"]
    assert e["de_clube"] == CLUBE and e["para_clube"] == proposta["clube"]
    assert e["parte_salario"] == proposta["parte_salario"] and e["status"] == "ativo"
    assert feito["caixa"] == caixa_antes + proposta["taxa"]

    m = mercado_service.ver_mercado(sid)
    assert all(x["nome"] != f["nome"] for x in m["elenco"])
    cedido = next(x for x in m["disponiveis"] if x["nome"] == f["nome"])
    assert "emprestado" in cedido["bloqueio"]
    h = mercado_service.historico(sid)
    assert [mv["tipo"] for mv in h["movimentos"]] == ["cedido"]
    assert h["total"]["arrecadado"] == proposta["taxa"]
    assert "Emprestamos: " + f["nome"] in _assuntos(sid)


def test_quem_nao_quer_nao_leva():
    sid = _iniciar()
    m = mercado_service.ver_mercado(sid)
    f, _ = _cedivel(m)
    with pytest.raises(TransferenciaInvalida, match="não está interessado"):
        emprestimo_service.ceder(sid, f["jogador_id"], "Clube Inexistente", "temporada")


def test_o_cedido_volta_na_virada_do_turno():
    sid = _iniciar()
    m = mercado_service.ver_mercado(sid)
    f = p = None
    for x in sorted(m["elenco"], key=lambda x: x["overall"]):
        e = x["emprestar"]
        if e and not e["bloqueio"] and e["duracoes"][0]["propostas"]:
            f, p = x, e["duracoes"][0]["propostas"][0]
            break
    emprestimo_service.ceder(sid, f["jogador_id"], p["clube"], "turno")
    _jogar(sid, 19)
    volta, _ = _no_elenco(sid, f["nome"])
    assert volta is not None and volta["emprestimo"] is None
    assert "Voltaram de empréstimo" in _assuntos(sid)
