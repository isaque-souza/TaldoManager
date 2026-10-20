"""Central de Transferências (v1.7): busca nas duas ligas, observados e o
histórico do técnico na carreira."""

import pytest

from app.domain.mercado import TransferenciaInvalida
from app.services import (
    carreira_service, mercado_service, observado_service, temporada_service,
)
from scripts.data_loader import TODAS_AS_LIGAS
from tests.negociar import fechar, oferecer

CLUBE = "Real Taldo"


def _iniciar(seed=11):
    return temporada_service.iniciar(seed=seed, clube_usuario=CLUBE)


def _jogar_ate_o_fim(sid):
    while temporada_service.avancar(sid)["concluida"] is False:
        pass


def _compravel(m):
    return next(
        f for f in m["disponiveis"]
        if f["bloqueio"] is None and not f["rival"] and f["valor_mercado"] * 3 < m["caixa"]
    )


def _comprar(sid, ficha):
    r = mercado_service.propor(sid, ficha["jogador_id"], ficha["valor_mercado"] * 3)
    return fechar(sid, r["negociacao_id"])


def _reserva(m):
    """Um jogador do elenco que dá para dispensar."""
    return min(
        (f for f in m["elenco"] if f["posicao"] != "Goleiro" and f["dispensa_bloqueada"] is None),
        key=lambda f: f["overall"],
    )


# ---------------------------------------------------------------------------
# buscar
# ---------------------------------------------------------------------------

def test_lista_de_compra_traz_as_duas_ligas_com_a_liga_de_cada_um():
    sid = temporada_service.iniciar(seed=11, clube_usuario=CLUBE, ligas=TODAS_AS_LIGAS)
    m = mercado_service.ver_mercado(sid)
    assert m["liga_usuario"] == "taldo"
    assert {f["liga"] for f in m["disponiveis"]} == {"taldo", "premier"}
    assert all(f["liga"] == "taldo" for f in m["elenco"])
    assert all(f["liga"] is None for f in m["livres"])


def test_com_a_janela_fechada_a_busca_segue_so_a_proposta_trava():
    sid = _iniciar()
    temporada_service.avancar(sid)
    m = mercado_service.ver_mercado(sid)
    assert m["janela_aberta"] is False
    assert m["disponiveis"] and m["livres"]
    assert {f["bloqueio"] for f in m["disponiveis"]} == {"Janela de transferências fechada"}


# ---------------------------------------------------------------------------
# observados
# ---------------------------------------------------------------------------

def test_observar_guarda_como_ele_estava_e_marca_na_lista_de_compra():
    sid = _iniciar()
    m = mercado_service.ver_mercado(sid)
    alvo, livre = m["disponiveis"][0], m["livres"][0]

    r = observado_service.observar(sid, alvo["nome"])
    assert r == {"nome": alvo["nome"], "observado": True, "total": 1,
                 "limite": observado_service.LIMITE}
    observado_service.observar(sid, livre["nome"])

    v = observado_service.ver(sid)
    um, outro = v["observados"]
    assert um["nome"] == alvo["nome"] and um["situacao"] == "clube"
    assert um["clube_inicial"] == alvo["clube"]
    assert (um["overall_inicial"], um["valor_inicial"]) == (alvo["overall"], alvo["valor_mercado"])
    assert (um["desde_temporada"], um["desde_rodada"]) == (1, 1)
    assert um["avisos"] == [] and um["jogador"]["liga"] == alvo["liga"]
    assert outro["situacao"] == "livre" and outro["clube_inicial"] is None
    assert outro["jogador"]["luvas"] == livre["luvas"]

    m = mercado_service.ver_mercado(sid)
    assert next(f for f in m["disponiveis"] if f["nome"] == alvo["nome"])["observado"]
    assert next(f for f in m["livres"] if f["nome"] == livre["nome"])["observado"]


def test_observar_de_novo_nao_muda_o_desde_e_tirar_remove():
    sid = _iniciar()
    alvo = mercado_service.ver_mercado(sid)["disponiveis"][0]
    observado_service.observar(sid, alvo["nome"])
    temporada_service.avancar(sid)

    assert observado_service.observar(sid, alvo["nome"])["total"] == 1
    assert observado_service.ver(sid)["observados"][0]["desde_rodada"] == 1

    r = observado_service.observar(sid, alvo["nome"], False)
    assert r["observado"] is False and r["total"] == 0
    assert observado_service.ver(sid)["observados"] == []


def test_observa_com_a_janela_fechada():
    sid = _iniciar()
    temporada_service.avancar(sid)
    alvo = mercado_service.ver_mercado(sid)["disponiveis"][0]
    assert observado_service.observar(sid, alvo["nome"])["observado"] is True
    assert observado_service.ver(sid)["observados"][0]["desde_rodada"] == 2


def test_lista_tem_limite_e_nao_aceita_o_proprio_elenco_nem_quem_nao_existe():
    sid = _iniciar()
    m = mercado_service.ver_mercado(sid)
    for f in m["disponiveis"][: observado_service.LIMITE]:
        observado_service.observar(sid, f["nome"])
    extra = m["disponiveis"][observado_service.LIMITE]
    with pytest.raises(TransferenciaInvalida, match="cheia"):
        observado_service.observar(sid, extra["nome"])
    with pytest.raises(TransferenciaInvalida, match="já é do seu elenco"):
        observado_service.observar(sid, m["elenco"][0]["nome"])
    assert observado_service.observar(sid, "Ninguém Com Este Nome") is None


def test_observado_contratado_sai_sozinho_da_lista():
    sid = _iniciar()
    m = mercado_service.ver_mercado(sid)
    alvo, livre, outro = _compravel(m), m["livres"][0], m["livres"][1]
    for nome in (alvo["nome"], livre["nome"], outro["nome"]):
        observado_service.observar(sid, nome)

    _comprar(sid, alvo)
    fechar(sid, mercado_service.contratar_livre(sid, livre["nome"])["negociacao_id"])

    assert [o["nome"] for o in observado_service.ver(sid)["observados"]] == [outro["nome"]]


def test_observados_seguem_na_virada(cargo_garantido):
    sid = _iniciar()
    alvo = mercado_service.ver_mercado(sid)["disponiveis"][0]
    observado_service.observar(sid, alvo["nome"])
    _jogar_ate_o_fim(sid)

    nova = carreira_service.proxima_temporada(sid)["simulacao_id"]
    (o,) = observado_service.ver(nova)["observados"]
    assert o["nome"] == alvo["nome"] and o["desde_temporada"] == 1
    assert o["overall_inicial"] == alvo["overall"]
    if o["situacao"] == "clube":
        assert o["jogador"]["idade"] == alvo["idade"] + 1


def test_avisos_contam_o_que_mudou():
    assert observado_service._avisos("A", None, None, None) == ["Aposentou"]

    class C:
        def __init__(self, nome):
            self.nome = nome

    a, b, meu = C("A"), C("B"), C("Meu")
    assert observado_service._avisos("A", object(), a, meu) == []
    assert observado_service._avisos("A", object(), b, meu) == ["Mudou de clube: A → B"]
    assert observado_service._avisos("A", object(), None, meu) == ["Ficou sem clube (estava no A)"]
    assert observado_service._avisos(None, object(), b, meu) == ["Assinou com o B"]
    assert observado_service._avisos("A", object(), meu, meu) == ["Já é do seu elenco"]


# ---------------------------------------------------------------------------
# histórico
# ---------------------------------------------------------------------------

def test_historico_tem_compra_venda_livre_e_dispensa_com_o_saldo():
    sid = _iniciar()
    m = mercado_service.ver_mercado(sid)
    comprado, livre, dispensado = _compravel(m), m["livres"][0], _reserva(m)

    compra = _comprar(sid, comprado)["transferencia"]
    fechar(sid, mercado_service.contratar_livre(sid, livre["nome"])["negociacao_id"])
    rescisao = mercado_service.dispensar(sid, dispensado["jogador_id"])["rescisao"]
    vendido = next(
        f for f in mercado_service.ver_mercado(sid)["elenco"] if f["bloqueio"] is None
    )
    comprador = next(f["clube"] for f in m["disponiveis"] if not f["rival"])
    oferta = {"clube": comprador, "valor": 1_000_000}
    mercado_service.aceitar_oferta(
        sid, oferecer(sid, vendido["jogador_id"], comprador, oferta["valor"])
    )

    h = mercado_service.historico(sid)
    por_tipo = {mv["tipo"]: mv for mv in h["movimentos"]}
    assert [mv["tipo"] for mv in h["movimentos"]] == ["venda", "dispensa", "livre", "compra"]

    assert por_tipo["compra"]["jogador"] == comprado["nome"]
    assert por_tipo["compra"]["de_clube"] == comprado["clube"]
    assert por_tipo["compra"]["valor"] == compra["valor"]
    assert por_tipo["livre"]["de_clube"] is None and por_tipo["livre"]["para_clube"] == CLUBE
    assert por_tipo["livre"]["valor"] == livre["luvas"]
    assert por_tipo["dispensa"]["para_clube"] is None
    assert por_tipo["dispensa"]["valor"] == rescisao
    assert por_tipo["venda"]["para_clube"] == oferta["clube"]

    gasto = compra["valor"] + livre["luvas"] + rescisao
    (t,) = h["temporadas"]
    assert t == {"temporada": 1, "gasto": gasto, "arrecadado": oferta["valor"],
                 "saldo": oferta["valor"] - gasto}
    assert h["total"] == {k: t[k] for k in ("gasto", "arrecadado", "saldo")}

    # a lista da temporada no mercado mostra os mesmos, com o tipo cru
    # (sem os negócios entre clubes da CPU, v1.7)
    tipos = [t["tipo"] for t in mercado_service.ver_mercado(sid)["transferencias"]
             if CLUBE in (t["de_clube"], t["para_clube"])]
    assert tipos == ["transferencia", "dispensa", "livre", "transferencia"]


def test_historico_junta_as_temporadas_da_carreira(cargo_garantido):
    sid = _iniciar()
    comprado = _compravel(mercado_service.ver_mercado(sid))
    _comprar(sid, comprado)
    _jogar_ate_o_fim(sid)
    # vale com a temporada concluída
    assert len(mercado_service.historico(sid)["movimentos"]) == 1

    nova = carreira_service.proxima_temporada(sid)["simulacao_id"]
    m = mercado_service.ver_mercado(nova)
    mercado_service.dispensar(nova, _reserva(m)["jogador_id"])

    h = mercado_service.historico(nova)
    assert h["temporada_atual"] == 2
    assert [(mv["temporada"], mv["tipo"]) for mv in h["movimentos"]] == [
        (2, "dispensa"), (1, "compra"),
    ]
    assert [t["temporada"] for t in h["temporadas"]] == [2, 1]


def test_historico_de_simulacao_que_nao_existe():
    assert mercado_service.historico(999) is None
