"""Mercado de transferências de uma temporada rodada a rodada (v0.7).

Só saves "em andamento" têm mercado: é o único modo que para entre as
rodadas para o técnico decidir. As regras ficam em `app.domain.mercado`;
aqui é carregar o estado vivo, aplicar a transferência e regravar tudo
(snapshot, clubes, jogadores e o histórico em `transferencia`).
"""

import json
import random

from app.db.conexao import conectar
from app.domain import mercado
from app.domain.mercado import TransferenciaInvalida
from app.domain.temporada import restaurar_estado, snapshot_estado
from app.repositories import clube_repository as clube_repo
from app.repositories import jogador_repository as jogador_repo
from app.repositories import simulacao_repository as simulacao_repo
from app.repositories import transferencia_repository as transferencia_repo
from app.services import simulacao_service
from app.services.temporada_service import TemporadaConcluida
from scripts.data_loader import carregar_campeonato

TIPOS = ("compra", "venda")


def _carregar(conn, simulacao_id):
    """(sim, campeonato) com o estado vivo restaurado; (None, None) se a
    simulação não existe. O RNG do processo é preservado — o snapshot já
    guarda a corrente da temporada."""

    sim = simulacao_repo.buscar(conn, simulacao_id)
    if sim is None:
        return None, None
    if sim["estado"] != "em_andamento":
        raise TemporadaConcluida("O mercado fecha quando a temporada termina")

    estado_rng = random.getstate()
    try:
        campeonato = carregar_campeonato()
        restaurar_estado(campeonato, json.loads(sim["estado_json"]))
    finally:
        random.setstate(estado_rng)

    return sim, campeonato


def _clube_de(campeonato, jogador):
    return next(c for c in campeonato.clubes if jogador in c.jogadores)


def _ficha(jogador, jogador_id, clube):
    return {
        "jogador_id": jogador_id,
        "nome": jogador.nome,
        "clube": clube.nome,
        "posicao": jogador.posicao,
        "idade": jogador.idade,
        "overall": jogador.overall,
        "potencial": jogador.potencial,
        "valor_mercado": jogador.valor_mercado(),
        "salario": jogador.salario(),
        "contrato_anos": jogador.contrato_anos,
    }


def _ids_por_nome(conn, simulacao_id):
    return {
        r["nome"]: r["id"]
        for r in jogador_repo.listar_por_simulacao(conn, simulacao_id)
    }


def _historico(conn, simulacao_id):
    return [
        {
            "rodada": r["rodada"],
            "jogador_id": r["jogador_id"],
            "jogador": r["jogador"],
            "posicao": r["posicao"],
            "de_clube": r["de_clube"],
            "para_clube": r["para_clube"],
            "valor": r["valor"],
        }
        for r in transferencia_repo.listar_por_simulacao(conn, simulacao_id)
    ]


def ver_mercado(simulacao_id, posicao=None, valor_max=None):
    """Situação do mercado para o clube dirigido: janela, caixa, o próprio
    elenco (com o que pode ser vendido) e os jogadores dos outros clubes
    (com o motivo de bloqueio, se não der para comprar)."""

    conn = conectar()
    try:
        sim, campeonato = _carregar(conn, simulacao_id)
        if sim is None:
            return None

        alvo = next(c for c in campeonato.clubes if c.nome == sim["clube_usuario"])
        ids = _ids_por_nome(conn, simulacao_id)
        aberta = mercado.janela_aberta(campeonato.rodada)
        fechada = None if aberta else "Janela de transferências fechada"

        elenco = []
        for j in sorted(alvo.jogadores, key=lambda j: -j.overall):
            preco = j.valor_mercado()
            bloqueio = fechada or mercado.motivo_saida_bloqueada(alvo, j)
            if bloqueio is None and mercado.melhor_comprador(
                j, campeonato.clubes, preco, excluir=[alvo]
            ) is None:
                bloqueio = "Nenhum clube tem caixa para comprar"
            elenco.append({**_ficha(j, ids[j.nome], alvo), "bloqueio": bloqueio})

        disponiveis = []
        for clube in campeonato.clubes:
            if clube is alvo:
                continue
            for j in clube.jogadores:
                if posicao and j.posicao != posicao:
                    continue
                preco = j.valor_mercado()
                if valor_max is not None and preco > valor_max:
                    continue
                bloqueio = (
                    fechada
                    or mercado.motivo_saida_bloqueada(clube, j)
                    or mercado.motivo_entrada_bloqueada(alvo, preco)
                )
                disponiveis.append(
                    {**_ficha(j, ids[j.nome], clube), "bloqueio": bloqueio}
                )
        disponiveis.sort(key=lambda f: (-f["overall"], f["valor_mercado"]))

        return {
            "rodada": campeonato.rodada,
            "janela_aberta": aberta,
            "janelas": list(mercado.JANELAS),
            "clube_usuario": alvo.nome,
            "caixa": alvo.dinheiro,
            "elenco_min": mercado.ELENCO_MIN,
            "elenco_max": mercado.ELENCO_MAX,
            "elenco": elenco,
            "disponiveis": disponiveis,
            "transferencias": _historico(conn, simulacao_id),
        }
    finally:
        conn.close()


def transferir(simulacao_id, jogador_id, tipo):
    """Compra (de outro clube) ou vende (para o clube mais rico que puder
    pagar) um jogador pelo valor de mercado. Devolve a transferência feita.
    None se a simulação ou o jogador não existem."""

    if tipo not in TIPOS:
        raise TransferenciaInvalida(f"Tipo inválido: {tipo!r} (use compra ou venda)")

    conn = conectar()
    try:
        sim, campeonato = _carregar(conn, simulacao_id)
        if sim is None:
            return None
        if not mercado.janela_aberta(campeonato.rodada):
            raise TransferenciaInvalida("Janela de transferências fechada")

        linha = jogador_repo.buscar(conn, jogador_id)
        if linha is None or linha["simulacao_id"] != simulacao_id:
            return None

        alvo = next(c for c in campeonato.clubes if c.nome == sim["clube_usuario"])
        jogador = next(
            j for c in campeonato.clubes for j in c.jogadores
            if j.nome == linha["nome"]
        )
        dono = _clube_de(campeonato, jogador)
        preco = jogador.valor_mercado()

        if tipo == "compra":
            if dono is alvo:
                raise TransferenciaInvalida(f"{jogador.nome} já é do seu elenco")
            vendedor, comprador = dono, alvo
        else:
            if dono is not alvo:
                raise TransferenciaInvalida(f"{jogador.nome} não é do seu elenco")
            vendedor = alvo
            comprador = mercado.melhor_comprador(
                jogador, campeonato.clubes, preco, excluir=[alvo]
            )
            if comprador is None:
                raise TransferenciaInvalida("Nenhum clube tem caixa para comprar")

        mercado.transferir(jogador, vendedor, comprador, preco)

        # regrava tudo o que mudou. O snapshot mantém a corrente de RNG
        # original: transferir não sorteia nada, e o RNG do processo já foi
        # devolvido ao que era antes de `_carregar`
        xi = sorted(j.nome for j in alvo.xi_preferido) or None
        cru = simulacao_service._serializar(
            campeonato, sim["seed"], alvo.nome, alvo.tatica, alvo.formacao, xi
        )
        blob = snapshot_estado(campeonato)
        blob["rng"] = json.loads(sim["estado_json"])["rng"]

        with conn:
            mapa = clube_repo.atualizar(conn, simulacao_id, cru["clubes"])
            jogador_repo.atualizar(conn, simulacao_id, mapa, cru["jogadores"])
            transferencia_repo.inserir(
                conn, simulacao_id, campeonato.rodada, jogador_id,
                mapa[vendedor.nome], mapa[comprador.nome], preco,
            )
            simulacao_repo.atualizar_estado(
                conn, simulacao_id,
                estado="em_andamento",
                rodada_atual=campeonato.rodada,
                estado_json=json.dumps(blob),
                campeao="",
                tatica=alvo.tatica,
                formacao=alvo.formacao,
                xi_preferido=json.dumps(xi, ensure_ascii=False) if xi else None,
            )

        return {
            "tipo": tipo,
            "rodada": campeonato.rodada,
            "jogador_id": jogador_id,
            "jogador": jogador.nome,
            "de_clube": vendedor.nome,
            "para_clube": comprador.nome,
            "valor": preco,
            "caixa": alvo.dinheiro,
        }
    finally:
        conn.close()
