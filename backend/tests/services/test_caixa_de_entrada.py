"""Caixa de entrada (v1.3): os setores do clube escrevem para o técnico."""

import pytest
from fastapi.testclient import TestClient

from app.db.conexao import conectar
from app.domain import caixa, mercado
from app.domain.jogador import Jogador
from app.domain.mercado import TransferenciaInvalida
from app.main import app
from app.services import mensagem_service, mercado_service, temporada_service

client = TestClient(app)


def _iniciar(clube="Real Taldo", seed=11):
    return temporada_service.iniciar(seed=seed, clube_usuario=clube)


def _alvo(m):
    return next(
        f for f in m["disponiveis"]
        if f["bloqueio"] is None and f["multa_rescisoria"] is None
        and f["valor_mercado"] < m["caixa"] / 4
    )


def _pedido(sid, jogador_id):
    conn = conectar()
    try:
        ctx = mercado_service._carregar(conn, sid)
        jogador, vendedor = ctx.jogador(jogador_id)
        return mercado.preco_pedido(jogador, vendedor, ctx.alvo)
    finally:
        conn.close()


def _do_setor(sid, setor):
    return [m for m in mensagem_service.listar(sid)["mensagens"] if m["setor"] == setor]


# ---------------------------------------------------------------------------
# diretoria e mercado
# ---------------------------------------------------------------------------

def test_temporada_nova_traz_a_meta_da_diretoria():
    sid = _iniciar()
    caixa_ = mensagem_service.listar(sid)
    assert caixa_["nao_lidas"] == 1
    (meta,) = caixa_["mensagens"]
    assert meta["setor"] == "Diretoria" and meta["rodada"] is None
    assert "Real Taldo" in meta["corpo"]


def test_proposta_recusada_explica_sem_revelar_o_pedido():
    sid = _iniciar()
    alvo = _alvo(mercado_service.ver_mercado(sid))
    pedido = _pedido(sid, alvo["jogador_id"])
    baixa = max(10_000, round(pedido * 0.5 / 10_000) * 10_000)

    r = mercado_service.propor(sid, alvo["jogador_id"], baixa)

    assert r["resposta"] == "recusada"
    (msg,) = _do_setor(sid, "Diretor de futebol")
    assert msg["assunto"] == f"Proposta recusada: {alvo['nome']}"
    assert "baixo demais" in msg["corpo"] and "85%" in msg["corpo"]
    assert caixa._dinheiro(pedido) not in msg["corpo"]
    assert "mais 2 propostas" in msg["corpo"]


def test_contraproposta_diz_quanto_faltou():
    sid = _iniciar()
    alvo = _alvo(mercado_service.ver_mercado(sid))
    pedido = _pedido(sid, alvo["jogador_id"])
    perto = round(pedido * 0.9 / 10_000) * 10_000

    r = mercado_service.propor(sid, alvo["jogador_id"], perto)

    assert r["resposta"] == "contraproposta"
    (msg,) = _do_setor(sid, "Diretor de futebol")
    assert caixa._dinheiro(pedido) in msg["corpo"]
    assert f"faltaram {caixa._dinheiro(pedido - perto)}" in msg["corpo"]


def test_compra_fechada_vira_mensagem():
    sid = _iniciar()
    alvo = _alvo(mercado_service.ver_mercado(sid))

    mercado_service.propor(sid, alvo["jogador_id"], _pedido(sid, alvo["jogador_id"]))

    (msg,) = _do_setor(sid, "Diretor de futebol")
    assert msg["assunto"] == f"Contratado: {alvo['nome']}"


def test_sem_caixa_nem_negocia_e_o_diretor_conta_o_que_faltou():
    sid = _iniciar(clube="Taldo FC")   # caixa pequeno
    m = mercado_service.ver_mercado(sid)
    caro = max(m["disponiveis"], key=lambda f: f["valor_mercado"])

    with pytest.raises(TransferenciaInvalida, match="caixa"):
        mercado_service.propor(sid, caro["jogador_id"], m["caixa"] + 1_000_000)

    (msg,) = _do_setor(sid, "Diretor de futebol")
    assert msg["assunto"] == f"Não deu para negociar {caro['nome']}"
    assert "não tem caixa" in msg["corpo"]
    assert f"Hoje temos {caixa._dinheiro(m['caixa'])} em caixa" in msg["corpo"]


# ---------------------------------------------------------------------------
# rodada: médico e auxiliar técnico
# ---------------------------------------------------------------------------

def test_rodadas_trazem_lesoes_e_cartoes_do_meu_time():
    sid = _iniciar()
    setores = set()
    for _ in range(12):
        temporada_service.avancar(sid)
        setores |= {m["setor"] for m in mensagem_service.listar(sid)["mensagens"]}
    assert {"Departamento médico", "Auxiliar técnico"} <= setores
    medicas = _do_setor(sid, "Departamento médico")
    assert all(m["rodada"] is not None for m in medicas)


def test_ler_marca_como_lida_pela_api():
    sid = _iniciar()
    caixa_ = client.get(f"/simulacoes/{sid}/mensagens").json()
    mid = caixa_["mensagens"][0]["id"]

    depois = client.post(f"/simulacoes/{sid}/mensagens/{mid}/lida").json()
    assert depois["nao_lidas"] == caixa_["nao_lidas"] - 1
    assert client.post(f"/simulacoes/{sid}/mensagens/9999/lida").status_code == 404
    assert client.post(f"/simulacoes/{sid}/mensagens/lidas").json()["nao_lidas"] == 0
    assert client.get("/simulacoes/9999/mensagens").status_code == 404


# ---------------------------------------------------------------------------
# domínio: os textos
# ---------------------------------------------------------------------------

def _foto(**muda):
    base = {
        "rodadas_lesao": 0, "jogos_suspensao": 0, "amarelos_ciclo": 0,
        "vermelhos": 0, "condicao": "Normal", "funcao": "Zagueiro",
    }
    return {"Fulano": {**base, **muda}}


def test_lesao_nova_e_recuperacao():
    (msg,) = caixa.depois_da_rodada(_foto(), _foto(rodadas_lesao=4), "Taldo FC")
    assert msg["setor"] == "Departamento médico"
    assert "Fulano (Zagueiro) sentiu contra o Taldo FC" in msg["corpo"]
    assert "próximas 4 rodadas" in msg["corpo"]

    # a lesão anda uma rodada no jogo: 3 → 2 não é lesão nova
    assert caixa.depois_da_rodada(_foto(rodadas_lesao=3), _foto(rodadas_lesao=2), "X") == []

    (msg,) = caixa.depois_da_rodada(_foto(rodadas_lesao=1), _foto(), "X")
    assert msg["assunto"] == "Liberado: Fulano"


def test_expulsao_quinto_amarelo_e_pendurado():
    (msg,) = caixa.depois_da_rodada(_foto(), _foto(jogos_suspensao=1, vermelhos=1), "X")
    assert "foi expulso" in msg["corpo"]
    (msg,) = caixa.depois_da_rodada(_foto(amarelos_ciclo=4), _foto(jogos_suspensao=1), "X")
    assert "5º amarelo" in msg["corpo"]
    (msg,) = caixa.depois_da_rodada(_foto(amarelos_ciclo=3), _foto(amarelos_ciclo=4), "X")
    assert msg["assunto"] == "Pendurado: Fulano"


def test_folga_nao_anda_lesao_nem_suspensao():
    assert caixa.depois_da_rodada(_foto(rodadas_lesao=2), _foto(rodadas_lesao=2), None) == []


def test_exaustos_numa_mensagem_so():
    antes = {**_foto(), "Beltrano": _foto()["Fulano"]}
    depois = {n: {**d, "condicao": "Exausto"} for n, d in antes.items()}
    (msg,) = caixa.depois_da_rodada(antes, depois, "X")
    assert msg["assunto"] == "Jogadores exaustos"
    assert "Beltrano, Fulano chegaram" in msg["corpo"]


def test_balanco_e_virada():
    msg = caixa.fim_de_temporada(3, 4, "Taldo City", "Real Taldo")
    assert "Meta cumprida" in msg["corpo"]
    assert caixa.fim_de_temporada(3, None, "X", "Y") is None

    j = Jogador("Jovem", 17, "Defesa", 70, funcao="Lateral")
    movs = [
        {"tipo": "subiu_da_base", "jogador": j.nome, "clube": "Real Taldo",
         "idade": 17, "overall": 70, "detalhe": "potencial 88"},
        {"tipo": "aposentou", "jogador": "Velho", "clube": "Real Taldo",
         "idade": 37, "overall": 75, "detalhe": ""},
        {"tipo": "subiu_da_base", "jogador": "Outro", "clube": "Taldo FC",
         "idade": 16, "overall": 60, "detalhe": "potencial 70"},
    ]
    base, elenco = caixa.virada("Real Taldo", movs, [("Fulano", "Zagueiro")])
    assert base["setor"] == "Categorias de base" and "Jovem" in base["corpo"]
    assert "Outro" not in base["corpo"]
    assert "Velho (aposentou)" in elenco["corpo"]
    assert "Fulano (Zagueiro)" in elenco["corpo"]
