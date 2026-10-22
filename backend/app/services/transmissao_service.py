"""Simulação interativa da partida do técnico (v1.2).

Ao apertar "Ir para o jogo", a partida começa a ser transmitida: o técnico
assiste minuto a minuto, pausa, muda a tática e faz substituições. Nada da
partida é gravado até o apito final: a rodada só é jogada de verdade (e
persistida) em `temporada_service.avancar`, que aplica as decisões
guardadas aqui.

Como funciona: o motor é determinístico a partir do snapshot da temporada
(que guarda a corrente de RNG), e a partida do técnico roda numa corrente
própria (`Campeonato.jogar_rodada(clube_usuario=...)`). Então cada pedido
restaura o snapshot e re-simula a rodada com as decisões até ali: uma
decisão muda só o jogo do técnico, e só do minuto dela em diante. Os outros
jogos da rodada saem iguais em toda transmissão.

As decisões ficam em `simulacao.ao_vivo_json` ({"rodada", "decisoes"}).
Enquanto há transmissão, o elenco fica travado (mercado, contratos e
escalação levantam PartidaEmAndamento) e ela não volta no tempo: uma decisão
nova não pode vir antes da última.
"""

import io
import json
import random
from contextlib import redirect_stdout

from app.db.conexao import conectar
from app.domain import posicoes
from app.domain.clube import Clube
from app.domain.partida import motivo_goleiro, motivo_troca_de_posicao
from app.domain.temporada import restaurar_estado
from app.repositories import simulacao_repository as simulacao_repo
from app.services import copa_service, escalacao_service
from app.services.temporada_service import (
    TemporadaConcluida, _achar_clube, _escalacao, decisoes_ao_vivo,
    proximo_confronto, transmissao_ativa,
)
from scripts.data_loader import carregar_campeonato_do_save

TIPOS_GOL = ("gol", "penalti")


class TransmissaoInvalida(Exception):
    """Pedido que não cabe na transmissão (folga, decisão inválida...)."""


# ---------------------------------------------------------------------------
# simulação
# ---------------------------------------------------------------------------

def _restaurado(sim):
    campeonato = carregar_campeonato_do_save(sim)
    restaurar_estado(campeonato, json.loads(sim["estado_json"]))
    return campeonato


def _simular(sim, decisoes, capturar_em=None):
    """Re-joga a rodada (num campeonato descartável) com as decisões. O RNG
    do processo volta ao que era: nada aqui deixa rastro."""

    estado_rng = random.getstate()
    try:
        campeonato = _restaurado(sim)
        rodada = campeonato.rodada
        with redirect_stdout(io.StringIO()):
            if sim["copa_pendente"]:   # o jogo da copa, na quarta (v2.0)
                campeonato.jogar_copa_adiada(
                    sim["copa_pendente"], sim["clube_usuario"], decisoes, capturar_em,
                )
            else:
                campeonato.jogar_rodada(
                    sim["clube_usuario"], decisoes, capturar_em, adiar_copa=True,
                )
    finally:
        random.setstate(estado_rng)
    return campeonato, rodada


def _escalacoes(sim):
    """As duas escalações no apito inicial (posição de cada um no campo)."""

    estado_rng = random.getstate()
    try:
        campeonato = _restaurado(sim)
    finally:
        random.setstate(estado_rng)
    alvo = _achar_clube(campeonato, sim["clube_usuario"])
    adversario, mando, _ = proximo_confronto(sim, campeonato, alvo.nome)
    if adversario is None:
        raise TransmissaoInvalida("O seu clube folga nesta rodada")
    rival = _achar_clube(campeonato, adversario)
    mandante, visitante = (alvo, rival) if mando == "casa" else (rival, alvo)
    return _escalacao(mandante), _escalacao(visitante)


# ---------------------------------------------------------------------------
# o que vai pra tela
# ---------------------------------------------------------------------------

def _montar(sim, campeonato, rodada, decisoes):
    p = campeonato.partida_usuario
    lado = {1: "mandante", 2: "visitante"}

    eventos = p.resumo_eventos()
    gols = [e for e in eventos if e["tipo"] in TIPOS_GOL]

    minutos = []
    placar = [0, 0]
    for registro in p.linha_do_tempo:
        m = registro["minuto"]
        for g in gols:
            if g["minuto"] == m:
                placar[0 if g["clube"] == p.clube1.nome else 1] += 1
        lance = registro["lance"]
        minutos.append({
            **registro,
            "lance": {**lance, "lado": lado[lance["lado"]]} if lance else None,
            "placar": list(placar),
        })

    # os outros jogos da liga do técnico (v1.6): a outra liga joga na mesma
    # rodada, mas não mexe na tabela dele. Na copa, os outros jogos da fase
    fase = sim["copa_pendente"]
    da_liga = {c.nome for c in campeonato.clubes_da_liga(p.clube1.liga)}
    outros = []
    for jogo in campeonato.copa.fases[fase] if fase else []:
        if jogo["mandante"] == p.clube1.nome:
            continue
        outros.append({
            "mandante": jogo["mandante"],
            "visitante": jogo["visitante"],
            "gols": [
                {"minuto": g["minuto"], "clube": g["clube"]}
                for g in jogo["gols"] if g["tipo"] in TIPOS_GOL
            ],
        })
    for jogo in [] if fase else campeonato.partidas_jogadas:
        if (jogo["rodada"] != rodada or jogo["mandante"] == p.clube1.nome
                or jogo["mandante"] not in da_liga):
            continue
        outros.append({
            "mandante": jogo["mandante"],
            "visitante": jogo["visitante"],
            "gols": [
                {"minuto": e["minuto"], "clube": e["clube"]}
                for e in jogo["eventos"] if e["tipo"] in TIPOS_GOL
            ],
        })

    mandante, visitante = _escalacoes(sim)
    return {
        "rodada": rodada,
        "clube_usuario": sim["clube_usuario"],
        "mandante": mandante,
        "visitante": visitante,
        "acrescimos": p.acrescimos,
        "minutos": minutos,
        "eventos": eventos,
        "decisoes": decisoes,
        "outros": outros,
        "desenhos": desenhos_das_formacoes(),
        # jogo da copa (v2.0): a fase e, no empate, os pênaltis
        "copa": {"fase": fase, "nome": copa_service.NOMES[fase]} if fase else None,
        "penaltis": [
            {**c, "lado": lado[c["lado"]]} for c in getattr(p, "cobrancas", [])
        ] if fase else [],
    }


def desenhos_das_formacoes():
    """{formação: [{funcao, x, y, rotulo}]}, goleiro primeiro."""
    return {
        f: [
            {"funcao": funcao, "x": x, "y": y, "rotulo": rotulo}
            for funcao, x, y, rotulo in posicoes.desenho(f)
        ]
        for f in Clube.FORMACOES
    }


def _transmissao(sim, decisoes):
    campeonato, rodada = _simular(sim, decisoes)
    return _montar(sim, campeonato, rodada, decisoes)


def _sim_em_andamento(conn, simulacao_id):
    sim = simulacao_repo.buscar(conn, simulacao_id)
    if sim is None:
        return None
    if sim["estado"] != "em_andamento":
        raise TemporadaConcluida("Esta temporada já foi concluída")
    return sim


# ---------------------------------------------------------------------------
# API do serviço
# ---------------------------------------------------------------------------

def iniciar(simulacao_id, tatica=None, formacao=None, xi_preferido=None,
            posicionamento=None):
    """Começa (ou retoma) a transmissão da partida do técnico na próxima
    rodada. Ao começar, grava a escalação como `PATCH /decisao`; se já há
    uma transmissão nesta rodada, a escalação dela vale e o corpo é
    ignorado (o time já entrou em campo). None se a simulação não existe."""

    conn = conectar()
    try:
        sim = _sim_em_andamento(conn, simulacao_id)
        if sim is None:
            return None
        if transmissao_ativa(sim):
            return _transmissao(sim, decisoes_ao_vivo(sim))
    finally:
        conn.close()

    # ainda não começou: grava a escalação e abre a transmissão
    escalacao_service.salvar_decisao(
        simulacao_id, tatica, formacao, xi_preferido, posicionamento
    )
    conn = conectar()
    try:
        sim = simulacao_repo.buscar(conn, simulacao_id)
        _escalacoes(sim)   # folga não tem transmissão
        with conn:
            simulacao_repo.definir_ao_vivo(
                conn, simulacao_id,
                json.dumps({"rodada": sim["rodada_atual"], "decisoes": [],
                            "copa": sim["copa_pendente"]}),
            )
        sim = simulacao_repo.buscar(conn, simulacao_id)
        return _transmissao(sim, [])
    finally:
        conn.close()


def atual(simulacao_id):
    """A transmissão em curso (None se a simulação não existe ou não há)."""

    conn = conectar()
    try:
        sim = _sim_em_andamento(conn, simulacao_id)
        if sim is None or not transmissao_ativa(sim):
            return None
        return _transmissao(sim, decisoes_ao_vivo(sim))
    finally:
        conn.close()


def estado(simulacao_id, minuto):
    """Os dois times ao fim de `minuto`: em campo (energia, cartões, nota),
    banco, substituições restantes e tática. É o que o técnico vê ao pausar."""

    conn = conectar()
    try:
        sim = _sim_em_andamento(conn, simulacao_id)
        if sim is None:
            return None
        if not transmissao_ativa(sim):
            raise TransmissaoInvalida("Nenhuma partida em andamento")
        campeonato, _ = _simular(sim, decisoes_ao_vivo(sim), capturar_em=minuto)
        foto = campeonato.partida_usuario.estado_capturado
        if foto is None:
            raise TransmissaoInvalida(f"A partida não chega ao minuto {minuto}")
        return foto
    finally:
        conn.close()


def _mudanca(clube, minuto, m):
    """Uma mudança da pausa vira decisão do motor. `m` tem uma só destas:
    `tatica`, `formacao`, `sai`+`entra` (substituição) ou `posicoes` (dois
    jogadores em campo trocam de vaga, v1.7)."""
    troca = m.get("sai") is not None or m.get("entra") is not None
    posicoes_ = m.get("posicoes")
    tipos = [m.get("tatica") is not None, m.get("formacao") is not None, troca,
             posicoes_ is not None]
    if tipos.count(True) != 1:
        raise TransmissaoInvalida(
            "Cada mudança é uma coisa só: tática, formação, substituição ou troca de posição"
        )
    if m.get("tatica") is not None:
        if m["tatica"] not in Clube.TATICAS:
            raise TransmissaoInvalida(f"Tática desconhecida: {m['tatica']!r}")
        return {"minuto": minuto, "clube": clube, "tatica": m["tatica"]}
    if m.get("formacao") is not None:
        if m["formacao"] not in Clube.FORMACOES:
            raise TransmissaoInvalida(f"Formação desconhecida: {m['formacao']!r}")
        return {"minuto": minuto, "clube": clube, "formacao": m["formacao"]}
    if troca:
        if not (m.get("sai") and m.get("entra")):
            raise TransmissaoInvalida("A substituição precisa de quem sai e de quem entra")
        return {"minuto": minuto, "clube": clube, "sai": m["sai"], "entra": m["entra"]}
    if len(posicoes_) != 2 or posicoes_[0] == posicoes_[1]:
        raise TransmissaoInvalida("A troca de posição é entre dois jogadores em campo")
    return {"minuto": minuto, "clube": clube, "posicoes": list(posicoes_)}


def _validar(partida, clube, novas):
    """Confere as mudanças da pausa, em ordem, contra a foto do fim do minuto
    anterior (o time como o técnico o vê). Devolve o motivo da primeira que
    não cabe, ou None."""

    foto = partida.estado_capturado
    time = next(c for c in foto["clubes"] if c["clube"] == clube)
    em_campo = {j["nome"]: dict(j) for j in time["em_campo"]}
    banco = {j["nome"]: j for j in time["banco"]}
    restantes = time["substituicoes_restantes"]

    for d in novas:
        if "posicoes" in d:
            a, b = d["posicoes"]
            for nome in (a, b):
                if nome not in em_campo:
                    return f"{nome} não está em campo"
            motivo = motivo_troca_de_posicao(
                em_campo[a]["posicao"], em_campo[a]["vaga"],
                em_campo[b]["posicao"], em_campo[b]["vaga"],
            )
            if motivo:
                return motivo
            for chave in ("vaga", "slot"):
                em_campo[a][chave], em_campo[b][chave] = em_campo[b][chave], em_campo[a][chave]
        elif "sai" in d:
            sai, entra = d["sai"], d["entra"]
            if restantes <= 0:
                return f"As {partida.max_substituicoes} substituições já foram feitas"
            if sai not in em_campo:
                return f"{sai} não está em campo"
            if em_campo[sai]["expulso"]:
                return f"{sai} foi expulso e não pode ser substituído"
            if entra not in banco:
                return f"{entra} não está no banco"
            if not banco[entra]["disponivel"]:
                return f"{entra} já saiu e não pode voltar"
            motivo = motivo_goleiro(em_campo[sai]["posicao"], banco[entra]["posicao"])
            if motivo:
                return motivo
            saindo = em_campo.pop(sai)
            em_campo[entra] = {
                **banco.pop(entra), "vaga": saindo["vaga"], "slot": saindo.get("slot"),
                "expulso": False,
            }
            restantes -= 1
    return None


def pausa(simulacao_id, minuto, mudancas):
    """As mudanças da pausa valendo a partir de `minuto` (v1.7), todas de
    uma vez e na ordem: substituem as que já estavam marcadas para esse
    minuto. Lista vazia desfaz todas. O que já foi jogado não muda: o minuto
    não pode vir antes da última decisão de outra pausa. Devolve a
    transmissão refeita."""

    conn = conectar()
    try:
        sim = _sim_em_andamento(conn, simulacao_id)
        if sim is None:
            return None
        if not transmissao_ativa(sim):
            raise TransmissaoInvalida("Nenhuma partida em andamento")
        if minuto < 1:
            raise TransmissaoInvalida("A decisão vale a partir do minuto 1")
        anteriores = [d for d in decisoes_ao_vivo(sim) if d["minuto"] != minuto]
        if anteriores and minuto < anteriores[-1]["minuto"]:
            raise TransmissaoInvalida("A partida não volta no tempo")

        clube = sim["clube_usuario"]
        novas = [_mudanca(clube, minuto, m) for m in mudancas]

        # o time como está no fim do minuto anterior: as mudanças cabem?
        campeonato, _ = _simular(sim, anteriores, capturar_em=minuto - 1)
        p = campeonato.partida_usuario
        if minuto > 90 + p.acrescimos:
            raise TransmissaoInvalida("A partida já acabou")
        motivo = _validar(p, clube, novas)
        if motivo:
            raise TransmissaoInvalida(motivo)

        decisoes = anteriores + novas
        with conn:
            simulacao_repo.definir_ao_vivo(
                conn, simulacao_id,
                json.dumps({"rodada": sim["rodada_atual"], "decisoes": decisoes,
                            "copa": sim["copa_pendente"]}, ensure_ascii=False),
            )
        return _transmissao(sim, decisoes)
    finally:
        conn.close()


def decidir(simulacao_id, minuto, tatica=None, sai=None, entra=None, formacao=None,
            posicoes=None):
    """Uma mudança a mais valendo a partir de `minuto` (tática, formação,
    substituição ou troca de posição), somada às já marcadas para ele.
    Devolve a transmissão refeita."""

    nova = {"tatica": tatica, "formacao": formacao, "sai": sai, "entra": entra,
            "posicoes": posicoes}
    _mudanca(None, minuto, nova)   # valida o formato antes de abrir o banco

    conn = conectar()
    try:
        sim = _sim_em_andamento(conn, simulacao_id)
        if sim is None:
            return None
        if not transmissao_ativa(sim):
            raise TransmissaoInvalida("Nenhuma partida em andamento")
        decisoes = decisoes_ao_vivo(sim)
    finally:
        conn.close()
    if decisoes and minuto < decisoes[-1]["minuto"]:
        raise TransmissaoInvalida("A partida não volta no tempo")
    marcadas = [
        {k: v for k, v in d.items() if k not in ("minuto", "clube")}
        for d in decisoes if d["minuto"] == minuto
    ]
    return pausa(simulacao_id, minuto, marcadas + [nova])
