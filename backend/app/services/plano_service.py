"""Planos de jogo (v1.2), como as táticas personalizadas do EA FC.

O técnico guarda escalações com nome (formação, tática e XI) e marca uma
como padrão. A cada rodada nova a escalação da partida volta para o
padrão (`aplicar_padrao`, chamado por `temporada_service.avancar`); mexer
antes do apito (PATCH /decisao) vale só para aquele jogo, a não ser que o
técnico salve no plano. "Usar" carrega um plano para a próxima partida.

A escalação da partida continua sendo a de sempre (o estado vivo +
`simulacao.tatica/formacao/xi_preferido`); o plano é só um molde. Um XI de
plano pode ter quem saiu do clube (venda, fim de contrato): ao carregar,
esses nomes ficam de fora e o motor completa a vaga.
"""

import json

from app.db.conexao import conectar
from app.domain.clube import Clube
from app.repositories import plano_repository as plano_repo
from app.repositories import simulacao_repository as simulacao_repo
from app.services import escalacao_service, simulacao_service
from app.services.mercado_service import _carregar
from app.services.temporada_service import TemporadaConcluida

MAX_PLANOS = 8
MAX_NOME = 30
NOME_INICIAL = "Titular"


class PlanoInvalido(Exception):
    """Plano que não cabe (nome, formação, XI...)."""


# ---------------------------------------------------------------------------
# regras
# ---------------------------------------------------------------------------

def _validar(alvo, nome, formacao, tatica, xi):
    nome = (nome or "").strip()
    if not nome:
        raise PlanoInvalido("Dê um nome ao plano")
    if len(nome) > MAX_NOME:
        raise PlanoInvalido(f"O nome tem no máximo {MAX_NOME} caracteres")
    if formacao not in Clube.FORMACOES:
        raise PlanoInvalido(f"Formação inválida: {formacao!r}")
    if tatica not in Clube.TATICAS:
        raise PlanoInvalido(f"Tática inválida: {tatica!r}")

    xi = list(dict.fromkeys(xi or []))
    do_elenco = {j.nome: j for j in alvo.jogadores}
    fora = [n for n in xi if n not in do_elenco]
    if fora:
        raise PlanoInvalido(f"Não são do elenco de {alvo.nome}: {', '.join(fora)}")

    # o XI é preferência por posição (o motor completa e, faltando gente,
    # improvisa): só o que nunca cabe é recusado
    if len(xi) > 11:
        raise PlanoInvalido("O XI tem no máximo 11 jogadores")
    if sum(do_elenco[n].posicao == "Goleiro" for n in xi) > 1:
        raise PlanoInvalido("Só um goleiro joga")
    return nome, xi


def _xi_atual(sim):
    return json.loads(sim["xi_preferido"]) if sim["xi_preferido"] else []


def _no_elenco(alvo, xi):
    elenco = {j.nome for j in alvo.jogadores}
    return [n for n in xi if n in elenco]


def _modificado(alvo, plano):
    """A escalação da próxima partida (a efetiva, do estado vivo) difere do
    plano carregado? Quem saiu do clube não conta como diferença."""
    if plano is None:
        return False
    return (
        alvo.tatica != plano["tatica"]
        or alvo.formacao != plano["formacao"]
        or {j.nome for j in alvo.xi_preferido} != set(_no_elenco(alvo, plano["xi"]))
    )


def _em_andamento(conn, simulacao_id):
    sim = simulacao_repo.buscar(conn, simulacao_id)
    if sim is None:
        return None
    if sim["estado"] != "em_andamento":
        raise TemporadaConcluida("Esta temporada já foi concluída")
    return sim


def _visao(conn, sim):
    planos = plano_repo.listar(conn, sim["id"])
    em_uso = next((p for p in planos if p["id"] == sim["plano_em_uso"]), None)
    alvo = _carregar(conn, sim["id"]).alvo
    return {
        "planos": planos,
        "em_uso": em_uso["id"] if em_uso else None,
        "modificado": _modificado(alvo, em_uso),
    }


# ---------------------------------------------------------------------------
# API do serviço
# ---------------------------------------------------------------------------

def listar(simulacao_id):
    """Os planos do save, qual está carregado e se a escalação da próxima
    partida foi mexida. Save sem plano ganha um, "Titular", com a
    escalação atual (padrão e em uso). None se a simulação não existe."""

    conn = conectar()
    try:
        sim = _em_andamento(conn, simulacao_id)
        if sim is None:
            return None
        if not plano_repo.listar(conn, simulacao_id):
            ctx = _carregar(conn, simulacao_id)
            alvo = ctx.alvo
            with conn:
                pid = plano_repo.criar(
                    conn, simulacao_id, NOME_INICIAL, alvo.formacao, alvo.tatica,
                    _no_elenco(alvo, _xi_atual(sim)), padrao=True,
                )
                simulacao_repo.definir_plano_em_uso(conn, simulacao_id, pid)
            sim = simulacao_repo.buscar(conn, simulacao_id)
        return _visao(conn, sim)
    finally:
        conn.close()


def criar(simulacao_id, nome, formacao=None, tatica=None, xi=None, padrao=False):
    """Plano novo; o que não vier sai da escalação atual da próxima partida.
    O plano novo passa a ser o carregado (é o que está na tela)."""

    conn = conectar()
    try:
        sim = _em_andamento(conn, simulacao_id)
        if sim is None:
            return None
        planos = plano_repo.listar(conn, simulacao_id)
        if len(planos) >= MAX_PLANOS:
            raise PlanoInvalido(f"No máximo {MAX_PLANOS} planos")
        alvo = _carregar(conn, simulacao_id).alvo
        formacao = formacao or alvo.formacao
        tatica = tatica or alvo.tatica
        xi = _xi_atual(sim) if xi is None else xi
        nome, xi = _validar(alvo, nome, formacao, tatica, xi)
        if any(p["nome"].lower() == nome.lower() for p in planos):
            raise PlanoInvalido(f"Já existe um plano chamado {nome!r}")
        with conn:
            pid = plano_repo.criar(
                conn, simulacao_id, nome, formacao, tatica, xi,
                padrao=padrao or not planos,
            )
            if padrao:
                plano_repo.definir_padrao(conn, simulacao_id, pid)
            simulacao_repo.definir_plano_em_uso(conn, simulacao_id, pid)
        return _visao(conn, simulacao_repo.buscar(conn, simulacao_id))
    finally:
        conn.close()


def atualizar(simulacao_id, plano_id, nome=None, formacao=None, tatica=None,
              xi=None, padrao=None):
    """Renomeia, muda o molde e/ou vira padrão. Não mexe na escalação da
    próxima partida (para isso, `usar`)."""

    conn = conectar()
    try:
        sim = _em_andamento(conn, simulacao_id)
        if sim is None:
            return None
        plano = plano_repo.buscar(conn, simulacao_id, plano_id)
        if plano is None:
            return None
        alvo = _carregar(conn, simulacao_id).alvo
        novo_nome, novo_xi = _validar(
            alvo,
            plano["nome"] if nome is None else nome,
            formacao or plano["formacao"],
            tatica or plano["tatica"],
            plano["xi"] if xi is None else xi,
        )
        if novo_nome.lower() != plano["nome"].lower() and any(
            p["nome"].lower() == novo_nome.lower()
            for p in plano_repo.listar(conn, simulacao_id)
        ):
            raise PlanoInvalido(f"Já existe um plano chamado {novo_nome!r}")
        with conn:
            plano_repo.atualizar(
                conn, plano_id, novo_nome, formacao or plano["formacao"],
                tatica or plano["tatica"], novo_xi,
            )
            if padrao:
                plano_repo.definir_padrao(conn, simulacao_id, plano_id)
        return _visao(conn, simulacao_repo.buscar(conn, simulacao_id))
    finally:
        conn.close()


def apagar(simulacao_id, plano_id):
    """Apaga um plano (não o último). Se era o padrão, o mais antigo que
    sobrou assume."""

    conn = conectar()
    try:
        sim = _em_andamento(conn, simulacao_id)
        if sim is None:
            return None
        plano = plano_repo.buscar(conn, simulacao_id, plano_id)
        if plano is None:
            return None
        restantes = [p for p in plano_repo.listar(conn, simulacao_id) if p["id"] != plano_id]
        if not restantes:
            raise PlanoInvalido("Fique com pelo menos um plano")
        with conn:
            plano_repo.deletar(conn, plano_id)
            if plano["padrao"]:
                plano_repo.definir_padrao(conn, simulacao_id, restantes[0]["id"])
            if sim["plano_em_uso"] == plano_id:
                simulacao_repo.definir_plano_em_uso(conn, simulacao_id, None)
        return _visao(conn, simulacao_repo.buscar(conn, simulacao_id))
    finally:
        conn.close()


def usar(simulacao_id, plano_id):
    """Carrega o plano na escalação da próxima partida. Com a partida já
    rolando, `PartidaEmAndamento` (vem do salvar_decisao)."""

    conn = conectar()
    try:
        sim = _em_andamento(conn, simulacao_id)
        if sim is None:
            return None
        plano = plano_repo.buscar(conn, simulacao_id, plano_id)
        if plano is None:
            return None
        alvo = _carregar(conn, simulacao_id).alvo
        xi = _no_elenco(alvo, plano["xi"])
    finally:
        conn.close()

    escalacao_service.salvar_decisao(
        simulacao_id, plano["tatica"], plano["formacao"], xi
    )
    conn = conectar()
    try:
        with conn:
            simulacao_repo.definir_plano_em_uso(conn, simulacao_id, plano_id)
        return _visao(conn, simulacao_repo.buscar(conn, simulacao_id))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# chamado de outros serviços
# ---------------------------------------------------------------------------

def padrao(conn, simulacao_id):
    return next((p for p in plano_repo.listar(conn, simulacao_id) if p["padrao"]), None)


def aplicar_padrao(conn, simulacao_id, alvo):
    """Rodada nova: o clube do técnico volta para o plano padrão. Devolve
    (tatica, formacao, xi) aplicados, ou None se o save não tem planos.
    Não sorteia nada (o snapshot de quem chama segue determinístico)."""

    plano = padrao(conn, simulacao_id)
    if plano is None:
        return None
    xi = _no_elenco(alvo, plano["xi"])
    simulacao_service._configurar_clube(alvo, plano["tatica"], plano["formacao"], xi)
    simulacao_repo.definir_plano_em_uso(conn, simulacao_id, plano["id"])
    return plano["tatica"], plano["formacao"], xi


def copiar(conn, de_simulacao, para_simulacao, alvo):
    """Virada de temporada: os planos seguem, sem quem saiu do clube."""

    for p in plano_repo.listar(conn, de_simulacao):
        pid = plano_repo.criar(
            conn, para_simulacao, p["nome"], p["formacao"], p["tatica"],
            _no_elenco(alvo, p["xi"]), padrao=p["padrao"],
        )
        if p["padrao"]:
            simulacao_repo.definir_plano_em_uso(conn, para_simulacao, pid)
