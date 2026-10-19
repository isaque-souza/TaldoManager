"""Mercado de ponta a ponta: negociação + banco + snapshot."""

import json

import pytest

from app.db.conexao import conectar
from app.domain import mercado, torcida
from app.domain.mercado import TransferenciaInvalida
from app.repositories import simulacao_repository as simulacao_repo
from app.services import mercado_service, simulacao_service, temporada_service
from app.services.temporada_service import TemporadaConcluida


def _iniciar(seed=11, clube="Real Taldo"):
    # Real Taldo: caixa grande, dá para comprar quase qualquer um
    return temporada_service.iniciar(seed=seed, clube_usuario=clube), clube


def _alvo(m, com_multa=None, rival=False):
    """Um jogador negociável de outro clube."""
    return next(
        f for f in m["disponiveis"]
        if f["bloqueio"] is None
        and f["rival"] == rival
        and (com_multa is None or (f["multa_rescisoria"] is not None) == com_multa)
        and f["valor_mercado"] < m["caixa"] / 4
    )


def _preco_pedido(sid, jogador_id):
    conn = conectar()
    try:
        ctx = mercado_service._carregar(conn, sid)
        jogador, vendedor = ctx.jogador(jogador_id)
        return mercado.preco_pedido(jogador, vendedor, ctx.alvo)
    finally:
        conn.close()


def _rng(sid):
    conn = conectar()
    try:
        return json.loads(simulacao_repo.buscar(conn, sid)["estado_json"])["rng"]
    finally:
        conn.close()


def test_mercado_abre_antes_da_rodada_1_e_mostra_os_rivais():
    sid, clube = _iniciar()
    m = mercado_service.ver_mercado(sid)
    assert m["janela_aberta"] and m["rodada"] == 1
    assert m["rivais"] == ["Taldo City"]
    assert len(m["elenco"]) == 23
    assert all(f["clube"] != clube for f in m["disponiveis"])
    assert all(f["rival"] == (f["clube"] == "Taldo City") for f in m["disponiveis"])


def test_filtros_de_posicao_e_valor():
    sid, _ = _iniciar()
    m = mercado_service.ver_mercado(sid, posicao="Goleiro", valor_max=2_000_000)
    assert m["disponiveis"]
    assert all(f["posicao"] == "Goleiro" for f in m["disponiveis"])
    assert all(f["valor_mercado"] <= 2_000_000 for f in m["disponiveis"])


def test_proposta_baixa_e_recusada_sem_revelar_o_preco():
    sid, _ = _iniciar()
    alvo = _alvo(mercado_service.ver_mercado(sid), com_multa=False)
    r = mercado_service.propor(sid, alvo["jogador_id"], 10_000)
    assert r["resposta"] == "recusada"
    assert r["valor_pedido"] is None
    assert r["propostas_restantes"] == mercado.MAX_PROPOSTAS - 1


def test_contraproposta_pode_ser_aceita_e_o_jogador_vem():
    sid, clube = _iniciar()
    m = mercado_service.ver_mercado(sid)
    alvo = _alvo(m, com_multa=False)

    # 90% do preço pedido (calculado pelo próprio domínio) = contraproposta
    pedido = _preco_pedido(sid, alvo["jogador_id"])
    r = mercado_service.propor(sid, alvo["jogador_id"], int(pedido * 0.9))
    assert r["resposta"] == "contraproposta"
    assert r["valor_pedido"] == pedido

    # aceitar a contraproposta funciona mesmo que as tentativas acabem
    aceita = mercado_service.propor(sid, alvo["jogador_id"], r["valor_pedido"])
    assert aceita["resposta"] == "aceita"
    assert aceita["transferencia"]["para_clube"] == clube
    assert aceita["transferencia"]["caixa"] == m["caixa"] - r["valor_pedido"]

    # o reforço sobrevive ao snapshot e entra em campo pelo clube novo
    temporada_service.avancar(sid)
    detalhe = simulacao_service.game_log_jogador(sid, alvo["jogador_id"])
    assert detalhe["jogador"]["clube"] == clube


def test_limite_de_propostas_por_janela():
    sid, _ = _iniciar()
    alvo = _alvo(mercado_service.ver_mercado(sid), com_multa=False)
    for _ in range(mercado.MAX_PROPOSTAS):
        mercado_service.propor(sid, alvo["jogador_id"], 10_000)
    with pytest.raises(TransferenciaInvalida, match="encerrou"):
        mercado_service.propor(sid, alvo["jogador_id"], 10_000)
    m = mercado_service.ver_mercado(sid)
    ficha = next(f for f in m["disponiveis"] if f["jogador_id"] == alvo["jogador_id"])
    assert ficha["propostas_restantes"] == 0


def test_pagar_a_multa_do_rival_traz_o_jogador():
    # o "caso Figo": rival não negocia barato, mas multa paga é multa paga
    sid, clube = _iniciar()
    m = mercado_service.ver_mercado(sid)
    alvo = next(
        f for f in m["disponiveis"]
        if f["rival"] and f["multa_rescisoria"] and f["bloqueio"] is None
        and f["multa_rescisoria"] <= m["caixa"]
    )
    r = mercado_service.propor(sid, alvo["jogador_id"], alvo["multa_rescisoria"])
    assert r["resposta"] == "multa"
    assert r["transferencia"]["valor"] == alvo["multa_rescisoria"]
    assert r["transferencia"]["de_clube"] == "Taldo City"


def test_proposta_acima_do_caixa_nao_gasta_tentativa():
    sid, _ = _iniciar()
    m = mercado_service.ver_mercado(sid)
    alvo = _alvo(m)
    with pytest.raises(TransferenciaInvalida, match="caixa"):
        mercado_service.propor(sid, alvo["jogador_id"], m["caixa"] + 1)
    m2 = mercado_service.ver_mercado(sid)
    ficha = next(f for f in m2["disponiveis"] if f["jogador_id"] == alvo["jogador_id"])
    assert ficha["propostas_restantes"] == mercado.MAX_PROPOSTAS


def test_venda_aceita_a_oferta_escolhida():
    sid, clube = _iniciar()
    m = mercado_service.ver_mercado(sid)
    vendido = next(f for f in m["elenco"] if f["bloqueio"] is None)

    lista = mercado_service.ofertas(sid, vendido["jogador_id"])
    assert lista["ofertas"]
    valores = [o["valor"] for o in lista["ofertas"]]
    assert valores == sorted(valores, reverse=True)

    escolhida = lista["ofertas"][-1]   # não precisa ser a maior
    feita = mercado_service.vender(sid, vendido["jogador_id"], escolhida["clube"])
    assert feita["para_clube"] == escolhida["clube"]
    assert feita["valor"] == escolhida["valor"]
    assert feita["caixa"] == m["caixa"] + escolhida["valor"]


def test_venda_para_clube_sem_oferta_e_recusada():
    sid, _ = _iniciar()
    vendido = mercado_service.ver_mercado(sid)["elenco"][0]
    with pytest.raises(TransferenciaInvalida, match="não tem oferta"):
        mercado_service.vender(sid, vendido["jogador_id"], "Clube Inventado")


def test_janela_fecha_depois_da_rodada_1():
    sid, _ = _iniciar()
    temporada_service.avancar(sid)
    m = mercado_service.ver_mercado(sid)
    assert not m["janela_aberta"]
    assert all(f["bloqueio"] for f in m["disponiveis"])
    with pytest.raises(TransferenciaInvalida, match="fechada"):
        mercado_service.propor(sid, m["disponiveis"][0]["jogador_id"], 1_000_000)


def test_nao_negocia_jogador_do_proprio_elenco():
    sid, _ = _iniciar()
    meu = mercado_service.ver_mercado(sid)["elenco"][0]
    with pytest.raises(TransferenciaInvalida):
        mercado_service.propor(sid, meu["jogador_id"], 1_000_000)


def test_negociacao_nao_mexe_na_sorte_da_temporada():
    # negociar não pode consumir números aleatórios: a corrente de RNG
    # gravada tem que ser a mesma de um save idêntico sem negociação
    sem, _ = _iniciar(seed=21)
    com, _ = _iniciar(seed=21)
    m = mercado_service.ver_mercado(com)
    alvo = _alvo(m)
    mercado_service.propor(com, alvo["jogador_id"], 10_000)
    mercado_service.propor(com, alvo["jogador_id"], alvo["valor_mercado"] * 3)
    assert _rng(sem) == _rng(com)


def test_sem_mercado_em_temporada_concluida():
    sid = simulacao_service.salvar_temporada(seed=3)
    with pytest.raises(TemporadaConcluida):
        mercado_service.ver_mercado(sid)


def test_simulacao_ou_jogador_inexistente():
    assert mercado_service.ver_mercado(999_999) is None
    sid, _ = _iniciar()
    assert mercado_service.propor(sid, 999_999, 1_000) is None
    assert mercado_service.ofertas(sid, 999_999) is None


def test_compra_aparece_no_historico_do_caixa():
    sid, clube = _iniciar()
    m = mercado_service.ver_mercado(sid)
    alvo = _alvo(m)
    r = mercado_service.propor(sid, alvo["jogador_id"], alvo["valor_mercado"] * 3)
    assert r["transferencia"]
    temporada_service.avancar(sid)

    visao = simulacao_service.carregar_temporada(sid)
    cid = next(c["id"] for c in visao["classificacao"] if c["clube"] == clube)
    hist = simulacao_service.detalhe_clube(sid, cid)["clube"]["historico_caixa"]
    assert len(hist) == 1
    # caixa após a R1 = antes da compra - compra + finanças da rodada
    assert hist[0] < m["caixa"] - r["transferencia"]["valor"] + 2_000_000


def _torcidas(sid):
    return {
        f["clube"]: f["torcedores"]
        for f in simulacao_service.carregar_temporada(sid)["financas"]
    }


def test_vender_para_o_rival_irrita_a_torcida():
    """Torcida (v1.4): a oferta do rival avisa o estrago, e a venda cobra."""
    sid, clube = _iniciar()
    m = mercado_service.ver_mercado(sid)
    antes = _torcidas(sid)
    for f in m["elenco"]:
        if f["bloqueio"] is not None:
            continue
        lista = mercado_service.ofertas(sid, f["jogador_id"])
        rival = next((o for o in lista["ofertas"] if o["rival"]), None)
        if rival:
            break
    else:
        pytest.skip("o rival não fez oferta por ninguém")
    assert rival["revolta_torcida"] < 0
    assert all(o["revolta_torcida"] is None for o in lista["ofertas"] if not o["rival"])

    mercado_service.vender(sid, f["jogador_id"], rival["clube"])

    depois = _torcidas(sid)
    assert depois[clube] == round(antes[clube] * (1 + rival["revolta_torcida"] / 100))
    assert depois[rival["clube"]] > antes[rival["clube"]]

    conn = conectar()
    try:
        from app.repositories import mensagem_repository
        assuntos = [r["assunto"] for r in mensagem_repository.listar(conn, sid)]
    finally:
        conn.close()
    assert "A torcida não perdoou" in assuntos


def test_vender_para_outro_clube_nao_mexe_na_torcida():
    sid, clube = _iniciar()
    m = mercado_service.ver_mercado(sid)
    antes = _torcidas(sid)
    # ídolo é outra história (v1.4): ver o teste abaixo
    vendido, oferta = next(
        (f, o)
        for f in m["elenco"] if f["bloqueio"] is None and not f["idolo"]
        for o in mercado_service.ofertas(sid, f["jogador_id"])["ofertas"]
        if not o["rival"]
    )
    mercado_service.vender(sid, vendido["jogador_id"], oferta["clube"])
    assert _torcidas(sid)[clube] == antes[clube]


def test_vender_idolo_revolta_a_torcida_e_avisa():
    sid, clube = _iniciar()
    m = mercado_service.ver_mercado(sid)
    antes = _torcidas(sid)
    idolo = next(
        (f for f in m["elenco"] if f["bloqueio"] is None and f["idolo"]), None
    )
    assert idolo is not None, "o clube da seed precisa ter um ídolo vendável"
    oferta = next(
        o for o in mercado_service.ofertas(sid, idolo["jogador_id"])["ofertas"]
        if not o["rival"]
    )
    assert oferta["revolta_torcida"] == round(100 * torcida.VENDA_IDOLO, 1)
    mercado_service.vender(sid, idolo["jogador_id"], oferta["clube"])
    assert _torcidas(sid)[clube] == round(antes[clube] * (1 + torcida.VENDA_IDOLO))
