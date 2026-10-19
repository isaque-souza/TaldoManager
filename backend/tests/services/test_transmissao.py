"""Simulação interativa (v1.2): a partida do técnico transmitida, com
mudanças de tática e substituições durante o jogo."""

import pytest

from app.domain.clube import Clube
from app.services import (
    escalacao_service, simulacao_service, temporada_service, transmissao_service,
)
from app.services.temporada_service import PartidaEmAndamento
from app.services.transmissao_service import TransmissaoInvalida


def _clube():
    return simulacao_service.listar_clubes()[0]["nome"]


def _meu_time(t):
    return t["mandante"] if t["mandante"]["clube"] == t["clube_usuario"] else t["visitante"]


def _minha_partida(res):
    meu = res["clube_usuario"]
    return next(r for r in res["resultados"] if meu in (r["mandante"], r["visitante"]))


def _iniciada(seed=5):
    sid = temporada_service.iniciar(seed=seed, clube_usuario=_clube())
    return sid, transmissao_service.iniciar(sid)


def _troca_valida(t):
    """Um titular de linha e um reserva da mesma posição."""
    meu = _meu_time(t)
    for entra in meu["banco"]:
        sai = next(
            (j for j in meu["titulares"]
             if j["posicao"] == entra["posicao"] and j["posicao"] != "Goleiro"),
            None,
        )
        if sai:
            return sai["nome"], entra["nome"]
    raise AssertionError("elenco sem troca possível")


def test_sem_decisoes_a_transmissao_e_exatamente_a_partida_que_vale():
    sid, t = _iniciada()
    res = temporada_service.avancar(sid)
    minha = _minha_partida(res)

    assert t["minutos"][-1]["placar"] == [minha["gols_mandante"], minha["gols_visitante"]]
    assert len(t["minutos"]) == 90 + t["acrescimos"]

    det = simulacao_service.detalhe_partida(sid, minha["partida_id"])
    assert det["partida"]["acrescimos"] == t["acrescimos"]
    assert [(e["minuto"], e["tipo"], e["jogador"]) for e in det["eventos"]] == [
        (e["minuto"], e["tipo"], e["jogador"]) for e in t["eventos"]
    ]


def test_outros_jogos_da_transmissao_batem_com_a_rodada_gravada():
    sid, t = _iniciada()
    res = temporada_service.avancar(sid)
    gravados = {
        p["mandante"]: [(g["minuto"], g["clube"]) for g in p["gols"]]
        for p in simulacao_service.ao_vivo(sid, 1)["partidas"]
    }
    assert len(t["outros"]) == len(res["resultados"]) - 1
    for jogo in t["outros"]:
        assert sorted((g["minuto"], g["clube"]) for g in jogo["gols"]) == sorted(gravados[jogo["mandante"]])


def test_decisao_nao_muda_o_passado_nem_os_outros_jogos():
    sid, t = _iniciada()
    sai, entra = _troca_valida(t)
    depois = transmissao_service.decidir(sid, 46, sai=sai, entra=entra)

    assert depois["minutos"][:45] == t["minutos"][:45]
    assert [e for e in depois["eventos"] if e["minuto"] < 46] == [
        e for e in t["eventos"] if e["minuto"] < 46
    ]
    assert depois["outros"] == t["outros"]
    assert depois["decisoes"] == [
        {"minuto": 46, "clube": t["clube_usuario"], "sai": sai, "entra": entra}
    ]


def test_substituicao_do_tecnico_vale_na_rodada_gravada():
    sid, t = _iniciada()
    sai, entra = _troca_valida(t)
    final = transmissao_service.decidir(sid, 30, sai=sai, entra=entra)

    troca = next(e for e in final["eventos"] if e["tipo"] == "substituicao" and e["minuto"] == 30)
    assert (troca["jogador"], troca["detalhe"]) == (entra, f"sai {sai}")

    res = temporada_service.avancar(sid)
    minha = _minha_partida(res)
    assert final["minutos"][-1]["placar"] == [minha["gols_mandante"], minha["gols_visitante"]]
    det = simulacao_service.detalhe_partida(sid, minha["partida_id"])
    assert any(e["tipo"] == "substituicao" and e["minuto"] == 30 and e["jogador"] == entra
               for e in det["eventos"])


def test_tatica_mudada_no_jogo_nao_fica_para_a_proxima_rodada():
    sid, t = _iniciada()
    original = _meu_time(t)["tatica"]
    nova = "ofensivo" if original != "ofensivo" else "defensivo"

    transmissao_service.decidir(sid, 10, tatica=nova)
    assert transmissao_service.estado(sid, 10)["clubes"][
        0 if t["mandante"]["clube"] == t["clube_usuario"] else 1
    ]["tatica"] == nova

    temporada_service.avancar(sid)
    assert temporada_service.proxima_rodada(sid)["tatica"] == original


def test_estado_mostra_quem_esta_em_campo_e_o_banco():
    sid, t = _iniciada()
    lado = 0 if t["mandante"]["clube"] == t["clube_usuario"] else 1
    inicio = transmissao_service.estado(sid, 0)["clubes"][lado]
    assert len(inicio["em_campo"]) == 11
    assert inicio["substituicoes_restantes"] == 5
    assert all(j["disponivel"] for j in inicio["banco"])

    sai, entra = _troca_valida(t)
    transmissao_service.decidir(sid, 20, sai=sai, entra=entra)
    agora = transmissao_service.estado(sid, 20)["clubes"][lado]
    nomes = {j["nome"] for j in agora["em_campo"]}
    assert entra in nomes and sai not in nomes
    assert agora["substituicoes_restantes"] == 4
    assert next(j for j in agora["banco"] if j["nome"] == sai)["disponivel"] is False


def test_decisoes_invalidas_sao_recusadas():
    sid, t = _iniciada()
    sai, entra = _troca_valida(t)

    with pytest.raises(TransmissaoInvalida):   # quem entra precisa estar no banco
        transmissao_service.decidir(sid, 10, sai=sai, entra=sai)
    with pytest.raises(TransmissaoInvalida):   # nem tática nem troca
        transmissao_service.decidir(sid, 10)
    with pytest.raises(TransmissaoInvalida):
        transmissao_service.decidir(sid, 10, tatica="retranca")

    transmissao_service.decidir(sid, 40, sai=sai, entra=entra)
    with pytest.raises(TransmissaoInvalida):   # não volta no tempo
        transmissao_service.decidir(sid, 39, tatica="ofensivo")
    with pytest.raises(TransmissaoInvalida):   # quem saiu não volta
        transmissao_service.decidir(sid, 41, sai=entra, entra=sai)
    with pytest.raises(TransmissaoInvalida):   # depois do apito
        transmissao_service.decidir(sid, 200, tatica="ofensivo")


def test_elenco_fica_travado_durante_a_partida():
    sid, _ = _iniciada()
    assert temporada_service.proxima_rodada(sid)["transmissao_ativa"] is True
    with pytest.raises(PartidaEmAndamento):
        escalacao_service.salvar_decisao(sid, tatica="ofensivo")

    temporada_service.avancar(sid)
    assert temporada_service.proxima_rodada(sid)["transmissao_ativa"] is False
    assert escalacao_service.salvar_decisao(sid, tatica="ofensivo")["tatica"] == "ofensivo"


def test_iniciar_de_novo_retoma_a_mesma_partida():
    sid, t = _iniciada()
    sai, entra = _troca_valida(t)
    feita = transmissao_service.decidir(sid, 50, sai=sai, entra=entra)

    # o corpo é ignorado: o time já entrou em campo
    retomada = transmissao_service.iniciar(sid, tatica="defensivo")
    assert retomada == feita
    assert transmissao_service.atual(sid) == feita


def test_iniciar_grava_a_escalacao_do_apito():
    sid = temporada_service.iniciar(seed=5, clube_usuario=_clube())
    t = transmissao_service.iniciar(sid, tatica="defensivo")
    assert _meu_time(t)["tatica"] == "defensivo"
    assert temporada_service.proxima_rodada(sid)["tatica"] == "defensivo"


def test_sem_transmissao_atual_e_none_e_estado_recusa():
    sid = temporada_service.iniciar(seed=5, clube_usuario=_clube())
    assert transmissao_service.atual(sid) is None
    with pytest.raises(TransmissaoInvalida):
        transmissao_service.estado(sid, 10)
    assert transmissao_service.iniciar(999_999) is None


def test_formacao_mudada_no_intervalo():
    sid, t = _iniciada()
    lado = 0 if t["mandante"]["clube"] == t["clube_usuario"] else 1
    original = _meu_time(t)["formacao"]
    nova = "3-4-3" if original != "3-4-3" else "5-4-1"

    depois = transmissao_service.decidir(sid, 46, formacao=nova)
    assert depois["minutos"][:45] == t["minutos"][:45]
    assert depois["decisoes"][-1] == {"minuto": 46, "clube": t["clube_usuario"], "formacao": nova}
    assert transmissao_service.estado(sid, 46)["clubes"][lado]["formacao"] == nova
    assert transmissao_service.estado(sid, 45)["clubes"][lado]["formacao"] == original

    with pytest.raises(TransmissaoInvalida):
        transmissao_service.decidir(sid, 47, formacao="2-2-6")
    with pytest.raises(TransmissaoInvalida):   # uma mudança por vez
        transmissao_service.decidir(sid, 47, formacao="4-4-2", tatica="ofensivo")

    temporada_service.avancar(sid)
    assert temporada_service.proxima_rodada(sid)["formacao"] == original


def test_goleiro_so_sai_para_entrar_outro_goleiro():
    sid, t = _iniciada()
    meu = _meu_time(t)
    goleiro = next(j for j in meu["titulares"] if j["posicao"] == "Goleiro")
    linha = next(j for j in meu["banco"] if j["posicao"] != "Goleiro")

    with pytest.raises(TransmissaoInvalida, match="goleiro"):
        transmissao_service.decidir(sid, 30, sai=goleiro["nome"], entra=linha["nome"])

    # jogador de linha por qualquer outro de linha, de outra posição: pode
    sai = next(j for j in meu["titulares"] if j["posicao"] == "Defesa")
    entra = next(j for j in meu["banco"] if j["posicao"] == "Atacante")
    depois = transmissao_service.decidir(sid, 30, sai=sai["nome"], entra=entra["nome"])
    assert depois["decisoes"][-1]["entra"] == entra["nome"]


def test_transmissao_traz_o_desenho_de_cada_formacao():
    _, t = _iniciada()
    assert set(t["desenhos"]) == set(Clube.FORMACOES)
    vagas = t["desenhos"]["4-2-3-1"]
    assert vagas[0]["funcao"] == "Goleiro"
    assert [v["rotulo"] for v in vagas].count("VOL") == 2
    # os titulares do apito já vêm no lugar do desenho
    meu = _meu_time(t)
    assert all(j["x"] is not None and j["rotulo"] for j in meu["titulares"])


# --- a pausa (v1.7): trocar de posição, confirmar tudo junto, desfazer -------

def _dois_de_linha(sid, minuto):
    foto = transmissao_service.estado(sid, minuto)
    meu = next(c for c in foto["clubes"] if c["clube"] == foto_clube(sid))
    linha = [j for j in meu["em_campo"] if j["posicao"] != "Goleiro"]
    zag = next(j for j in linha if j["posicao"] == "Defesa")
    ata = next(j for j in linha if j["posicao"] == "Atacante")
    return meu, zag, ata


def foto_clube(sid):
    return transmissao_service.atual(sid)["clube_usuario"]


def _em_campo(sid, minuto, nome):
    foto = transmissao_service.estado(sid, minuto)
    meu = next(c for c in foto["clubes"] if c["clube"] == foto_clube(sid))
    return next((j for j in meu["em_campo"] if j["nome"] == nome), None)


def test_troca_de_posicao_inverte_as_vagas():
    sid, _ = _iniciada()
    _, zag, ata = _dois_de_linha(sid, 30)
    t = transmissao_service.pausa(sid, 31, [{"posicoes": [zag["nome"], ata["nome"]]}])
    assert t["decisoes"][-1]["posicoes"] == [zag["nome"], ata["nome"]]

    depois = _em_campo(sid, 31, zag["nome"])
    assert depois["vaga"] == ata["vaga"] and depois["slot"] == ata["slot"]
    assert _em_campo(sid, 31, ata["nome"])["vaga"] == zag["vaga"]
    # improvisado rende menos
    assert depois["overall_vaga"] < zag["overall_vaga"]


def test_goleiro_nao_troca_de_posicao():
    sid, _ = _iniciada()
    foto = transmissao_service.estado(sid, 10)
    meu = next(c for c in foto["clubes"] if c["clube"] == foto_clube(sid))
    gol = next(j for j in meu["em_campo"] if j["posicao"] == "Goleiro")
    outro = next(j for j in meu["em_campo"] if j["posicao"] != "Goleiro")
    with pytest.raises(TransmissaoInvalida, match="goleiro fica no gol"):
        transmissao_service.pausa(sid, 11, [{"posicoes": [gol["nome"], outro["nome"]]}])


def test_pausa_confirma_tudo_junto_e_lista_vazia_desfaz():
    sid, t = _iniciada()
    sai, entra = _troca_valida(t)
    feita = transmissao_service.pausa(sid, 46, [
        {"tatica": "ofensivo"}, {"sai": sai, "entra": entra},
    ])
    assert [d.get("tatica") or d.get("entra") for d in feita["decisoes"]] == ["ofensivo", entra]

    # confirmar de novo na mesma pausa troca as marcadas (sem duplicar)
    so_tatica = transmissao_service.pausa(sid, 46, [{"tatica": "defensivo"}])
    assert [d["minuto"] for d in so_tatica["decisoes"]] == [46]

    desfeita = transmissao_service.pausa(sid, 46, [])
    assert desfeita["decisoes"] == []
    assert desfeita["minutos"] == t["minutos"]   # a partida volta a ser a de antes


def test_pausa_nao_desfaz_o_que_ja_foi_jogado():
    sid, t = _iniciada()
    transmissao_service.pausa(sid, 20, [{"tatica": "ofensivo"}])
    with pytest.raises(TransmissaoInvalida, match="não volta no tempo"):
        transmissao_service.pausa(sid, 10, [])


def test_mudancas_da_pausa_sao_validadas_em_ordem():
    sid, t = _iniciada()
    sai, entra = _troca_valida(t)
    # depois de sair, ele não está mais em campo para trocar de posição
    with pytest.raises(TransmissaoInvalida, match="não está em campo"):
        transmissao_service.pausa(sid, 46, [
            {"sai": sai, "entra": entra}, {"posicoes": [sai, entra]},
        ])
    # quem entra já pode trocar de posição na mesma pausa
    _, zag, _ = _dois_de_linha(sid, 45)
    outro = zag["nome"] if zag["nome"] != sai else None
    if outro:
        transmissao_service.pausa(sid, 46, [
            {"sai": sai, "entra": entra}, {"posicoes": [entra, outro]},
        ])


def test_troca_de_posicao_e_substituicao_na_mesma_pausa():
    """O atacante vai à zaga e sai para um zagueiro do banco, que fica na
    vaga da zaga; o zagueiro que estava lá vai para o ataque."""
    sid, t = _iniciada()
    meu, zag, ata = _dois_de_linha(sid, 30)
    zag_banco = next(
        (j for j in meu["banco"] if j["posicao"] == "Defesa" and j["disponivel"]), None
    )
    if zag_banco is None:
        pytest.skip("sem zagueiro no banco nesta seed")

    t = transmissao_service.pausa(sid, 31, [
        {"posicoes": [zag["nome"], ata["nome"]]},          # o atacante vai à zaga
        {"sai": ata["nome"], "entra": zag_banco["nome"]},  # e sai para o zagueiro
    ])
    entrou = _em_campo(sid, 31, zag_banco["nome"])
    assert entrou["vaga"] == zag["vaga"]
    assert _em_campo(sid, 31, zag["nome"])["vaga"] == ata["vaga"]

    # e vale na rodada gravada
    res = temporada_service.avancar(sid)
    minha = _minha_partida(res)
    det = simulacao_service.detalhe_partida(sid, minha["partida_id"])
    assert any(e["tipo"] == "substituicao" and e["minuto"] == 31 for e in det["eventos"])


def test_expulso_pode_mudar_de_vaga_mas_nao_sai():
    """Com um zagueiro expulso, o buraco dele vai para o ataque e um zagueiro
    do banco entra na zaga, no lugar do atacante."""
    from types import SimpleNamespace

    def j(nome, posicao, vaga, slot, expulso=False):
        return {"nome": nome, "posicao": posicao, "vaga": vaga, "slot": slot, "expulso": expulso}

    foto = {"clubes": [{
        "clube": "Meu",
        "substituicoes_restantes": 5,
        "em_campo": [j("Gol", "Goleiro", "Goleiro", 0), j("Zag", "Defesa", "Zagueiro", 1, True),
                     j("Ata", "Atacante", "Centroavante", 9)],
        "banco": [{"nome": "Zag2", "posicao": "Defesa", "disponivel": True}],
    }]}
    p = SimpleNamespace(estado_capturado=foto, max_substituicoes=5)
    validar = transmissao_service._validar
    assert validar(p, "Meu", [{"sai": "Zag", "entra": "Zag2"}]).endswith("não pode ser substituído")
    assert validar(p, "Meu", [
        {"posicoes": ["Zag", "Ata"]}, {"sai": "Ata", "entra": "Zag2"},
    ]) is None
