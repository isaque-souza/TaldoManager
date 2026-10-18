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
from app.domain.partida import motivo_goleiro
from app.domain.temporada import restaurar_estado
from app.repositories import simulacao_repository as simulacao_repo
from app.services import escalacao_service
from app.services.temporada_service import (
    TemporadaConcluida, _achar_clube, _confronto_do_clube, _escalacao,
    decisoes_ao_vivo, transmissao_ativa,
)
from scripts.data_loader import carregar_campeonato

TIPOS_GOL = ("gol", "penalti")


class TransmissaoInvalida(Exception):
    """Pedido que não cabe na transmissão (folga, decisão inválida...)."""


# ---------------------------------------------------------------------------
# simulação
# ---------------------------------------------------------------------------

def _restaurado(sim):
    campeonato = carregar_campeonato()
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
            campeonato.jogar_rodada(sim["clube_usuario"], decisoes, capturar_em)
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
    r = campeonato.rodada
    alvo = _achar_clube(campeonato, sim["clube_usuario"])
    adversario, mando = _confronto_do_clube(campeonato.calendario[r - 1], alvo.nome)
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

    outros = []
    for jogo in campeonato.partidas_jogadas:
        if jogo["rodada"] != rodada or jogo["mandante"] == p.clube1.nome:
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
                json.dumps({"rodada": sim["rodada_atual"], "decisoes": []}),
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


def decidir(simulacao_id, minuto, tatica=None, sai=None, entra=None, formacao=None):
    """Mudança do técnico valendo a partir de `minuto`: nova tática, nova
    formação ou uma substituição (`sai` por `entra`) — uma por vez.
    Devolve a transmissão refeita."""

    troca = sai is not None or entra is not None
    if [tatica is not None, formacao is not None, troca].count(True) != 1:
        raise TransmissaoInvalida(
            "Mande uma mudança por vez: tática, formação ou substituição (sai e entra)"
        )
    if tatica is not None and tatica not in Clube.TATICAS:
        raise TransmissaoInvalida(f"Tática desconhecida: {tatica!r}")
    if formacao is not None and formacao not in Clube.FORMACOES:
        raise TransmissaoInvalida(f"Formação desconhecida: {formacao!r}")
    if troca and not (sai and entra):
        raise TransmissaoInvalida("A substituição precisa de quem sai e de quem entra")

    conn = conectar()
    try:
        sim = _sim_em_andamento(conn, simulacao_id)
        if sim is None:
            return None
        if not transmissao_ativa(sim):
            raise TransmissaoInvalida("Nenhuma partida em andamento")
        decisoes = decisoes_ao_vivo(sim)
        if decisoes and minuto < decisoes[-1]["minuto"]:
            raise TransmissaoInvalida("A partida não volta no tempo")
        if minuto < 1:
            raise TransmissaoInvalida("A decisão vale a partir do minuto 1")

        # o time como está no fim do minuto anterior: a decisão cabe?
        campeonato, _ = _simular(sim, decisoes, capturar_em=minuto - 1)
        p = campeonato.partida_usuario
        if minuto > 90 + p.acrescimos:
            raise TransmissaoInvalida("A partida já acabou")
        clube = sim["clube_usuario"]
        if tatica is not None:
            nova = {"minuto": minuto, "clube": clube, "tatica": tatica}
        elif formacao is not None:
            nova = {"minuto": minuto, "clube": clube, "formacao": formacao}
        else:
            nova = {"minuto": minuto, "clube": clube, "sai": sai, "entra": entra}
            motivo = _motivo_troca(p, minuto - 1, decisoes, clube, sai, entra)
            if motivo:
                raise TransmissaoInvalida(motivo)

        decisoes = decisoes + [nova]
        with conn:
            simulacao_repo.definir_ao_vivo(
                conn, simulacao_id,
                json.dumps({"rodada": sim["rodada_atual"], "decisoes": decisoes},
                           ensure_ascii=False),
            )
        return _transmissao(sim, decisoes)
    finally:
        conn.close()


def _motivo_troca(partida, minuto_foto, decisoes, clube, sai, entra):
    """Valida a troca contra a foto do fim do minuto anterior. Trocas já
    marcadas para o MESMO minuto ainda não aparecem na foto, então entram
    na conta à parte."""

    foto = partida.estado_capturado
    time = next(c for c in foto["clubes"] if c["clube"] == clube)
    mesmas = [d for d in decisoes if d["minuto"] == minuto_foto + 1 and "sai" in d]

    em_campo = {j["nome"]: j for j in time["em_campo"]}
    banco = {j["nome"]: j for j in time["banco"]}
    for d in mesmas:
        em_campo.pop(d["sai"], None)
        banco.pop(d["entra"], None)

    if time["substituicoes_restantes"] - len(mesmas) <= 0:
        return f"As {partida.max_substituicoes} substituições já foram feitas"
    if sai not in em_campo:
        return f"{sai} não está em campo"
    if em_campo[sai]["expulso"]:
        return f"{sai} foi expulso e não pode ser substituído"
    if entra not in banco:
        return f"{entra} não está no banco"
    if not banco[entra]["disponivel"]:
        return f"{entra} já saiu e não pode voltar"
    return motivo_goleiro(em_campo[sai]["posicao"], banco[entra]["posicao"])
