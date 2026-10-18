"""Planos de jogo (v1.2): escalações com nome, o padrão carregado a cada
rodada e mudanças só para um jogo."""

import pytest

from app.db.conexao import conectar
from app.repositories import plano_repository as plano_repo
from app.services import (
    carreira_service, escalacao_service, plano_service, simulacao_service,
    temporada_service, transmissao_service,
)
from app.services.plano_service import PlanoInvalido
from app.services.temporada_service import PartidaEmAndamento


def _clube():
    return simulacao_service.listar_clubes()[0]["nome"]


def _save():
    return temporada_service.iniciar(seed=5, clube_usuario=_clube())


def _elenco(sid):
    return temporada_service.proxima_rodada(sid)["elenco"]


def _xi(sid, formacao="4-3-3"):
    """Um XI completo e válido para a formação (os melhores de cada posição)."""
    vagas = dict(zip(("Defesa", "Meio-Campo", "Atacante"), map(int, formacao.split("-"))))
    vagas["Goleiro"] = 1
    xi = []
    for pos, n in vagas.items():
        da_posicao = sorted((j for j in _elenco(sid) if j["posicao"] == pos),
                            key=lambda j: -j["overall"])
        xi += [j["nome"] for j in da_posicao[:n]]
    return xi


def test_save_sem_plano_ganha_o_titular_com_a_escalacao_atual():
    sid = _save()
    v = plano_service.listar(sid)
    assert [p["nome"] for p in v["planos"]] == ["Titular"]
    titular = v["planos"][0]
    assert titular["padrao"] is True
    assert v["em_uso"] == titular["id"]
    assert v["modificado"] is False
    # chamar de novo não cria outro
    assert len(plano_service.listar(sid)["planos"]) == 1


def test_criar_plano_valida_e_vira_o_carregado():
    sid = _save()
    plano_service.listar(sid)
    v = plano_service.criar(sid, "Retranca", formacao="5-4-1", tatica="defensivo",
                            xi=_xi(sid, "5-4-1"))
    novo = next(p for p in v["planos"] if p["nome"] == "Retranca")
    assert (novo["formacao"], novo["tatica"], novo["padrao"]) == ("5-4-1", "defensivo", False)
    assert len(novo["xi"]) == 11
    assert v["em_uso"] == novo["id"]

    with pytest.raises(PlanoInvalido):          # nome repetido (sem ligar pra caixa)
        plano_service.criar(sid, "retranca")
    with pytest.raises(PlanoInvalido):          # nome vazio
        plano_service.criar(sid, "   ")
    with pytest.raises(PlanoInvalido):          # quem não é do elenco
        plano_service.criar(sid, "Fantasma", xi=["Ninguém da Silva"])
    goleiros = [j["nome"] for j in _elenco(sid) if j["posicao"] == "Goleiro"][:2]
    with pytest.raises(PlanoInvalido):          # dois goleiros não cabem
        plano_service.criar(sid, "Dois goleiros", xi=goleiros)


def test_mexer_antes_do_jogo_marca_modificado_e_usar_volta_ao_plano():
    sid = _save()
    v = plano_service.listar(sid)
    titular = v["planos"][0]
    nova = "ofensivo" if titular["tatica"] != "ofensivo" else "defensivo"

    escalacao_service.salvar_decisao(sid, tatica=nova)
    assert plano_service.listar(sid)["modificado"] is True

    v = plano_service.usar(sid, titular["id"])
    assert v["modificado"] is False
    assert temporada_service.proxima_rodada(sid)["tatica"] == titular["tatica"]


def test_rodada_nova_volta_para_o_plano_padrao():
    sid = _save()
    plano_service.listar(sid)
    v = plano_service.criar(sid, "Fechado", formacao="5-3-2", tatica="defensivo",
                            xi=_xi(sid, "5-3-2"), padrao=True)
    fechado = next(p for p in v["planos"] if p["nome"] == "Fechado")
    assert fechado["padrao"] and sum(p["padrao"] for p in v["planos"]) == 1

    # só neste jogo: ofensivo no 4-3-3
    escalacao_service.salvar_decisao(sid, tatica="ofensivo", formacao="4-3-3", xi_preferido=_xi(sid))
    temporada_service.avancar(sid)

    pr = temporada_service.proxima_rodada(sid)
    assert (pr["tatica"], pr["formacao"]) == ("defensivo", "5-3-2")
    assert set(pr["xi_preferido"]) == set(fechado["xi"])
    v = plano_service.listar(sid)
    assert v["em_uso"] == fechado["id"] and v["modificado"] is False


def test_editar_plano_nao_mexe_na_proxima_partida():
    sid = _save()
    titular = plano_service.listar(sid)["planos"][0]
    antes = temporada_service.proxima_rodada(sid)["tatica"]
    nova = "ofensivo" if titular["tatica"] != "ofensivo" else "defensivo"

    v = plano_service.atualizar(sid, titular["id"], nome="Principal", tatica=nova)
    assert v["planos"][0]["nome"] == "Principal"
    assert v["planos"][0]["tatica"] == nova
    assert temporada_service.proxima_rodada(sid)["tatica"] == antes
    assert v["modificado"] is True   # a partida ficou diferente do plano


def test_apagar_padrao_passa_o_padrao_adiante_e_o_ultimo_fica():
    sid = _save()
    titular = plano_service.listar(sid)["planos"][0]
    plano_service.criar(sid, "Reserva")
    v = plano_service.apagar(sid, titular["id"])
    assert [p["nome"] for p in v["planos"]] == ["Reserva"]
    assert v["planos"][0]["padrao"] is True
    with pytest.raises(PlanoInvalido):
        plano_service.apagar(sid, v["planos"][0]["id"])


def test_limite_de_planos():
    sid = _save()
    plano_service.listar(sid)
    for i in range(plano_service.MAX_PLANOS - 1):
        plano_service.criar(sid, f"Plano {i}")
    with pytest.raises(PlanoInvalido):
        plano_service.criar(sid, "Um a mais")


def test_usar_ignora_quem_saiu_do_clube():
    sid = _save()
    plano_service.listar(sid)
    xi = _xi(sid)
    conn = conectar()
    with conn:
        pid = plano_repo.criar(conn, sid, "Antigo", "4-3-3", "equilibrado",
                               xi[:10] + ["Vendido Faz Tempo"])
    conn.close()
    plano_service.usar(sid, pid)
    assert set(temporada_service.proxima_rodada(sid)["xi_preferido"]) == set(xi[:10])


def test_nao_da_para_trocar_de_plano_com_a_partida_rolando():
    sid = _save()
    titular = plano_service.listar(sid)["planos"][0]
    transmissao_service.iniciar(sid)
    with pytest.raises(PartidaEmAndamento):
        plano_service.usar(sid, titular["id"])
    # editar o molde pode (não mexe na partida)
    assert plano_service.atualizar(sid, titular["id"], nome="Durante")["planos"][0]["nome"] == "Durante"


def test_planos_seguem_para_a_proxima_temporada_e_ela_comeca_no_padrao(cargo_garantido):
    sim = simulacao_service.salvar_temporada(seed=3, clube_usuario=_clube())
    sid = sim["id"] if isinstance(sim, dict) else sim
    conn = conectar()
    with conn:
        plano_repo.criar(conn, sid, "Base", "4-4-2", "equilibrado", [])
        plano_repo.criar(conn, sid, "Ataque total", "3-4-3", "ofensivo", [], padrao=True)
    conn.close()

    nova = carreira_service.proxima_temporada(sid)["simulacao_id"]
    v = plano_service.listar(nova)
    assert [p["nome"] for p in v["planos"]] == ["Base", "Ataque total"]
    padrao = next(p for p in v["planos"] if p["padrao"])
    assert padrao["nome"] == "Ataque total" and v["em_uso"] == padrao["id"]
    pr = temporada_service.proxima_rodada(nova)
    assert (pr["tatica"], pr["formacao"]) == ("ofensivo", "3-4-3")
