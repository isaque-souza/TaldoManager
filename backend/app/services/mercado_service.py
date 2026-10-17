"""Mercado de transferências de uma temporada rodada a rodada (v0.7).

Só saves "em andamento" têm mercado: é o único modo que para entre as
rodadas para o técnico decidir. As regras ficam em `app.domain.mercado`;
aqui é carregar o estado vivo, aplicar a negociação e regravar tudo
(snapshot, clubes, jogadores, propostas e o histórico em `transferencia`).

- comprar: `propor` → o clube vendedor aceita, contrapropõe ou recusa
- vender: `ofertas` lista o que cada clube paga; `vender` aceita uma delas
"""

import json
import random

from app.db.conexao import conectar
from app.domain import mercado
from app.domain.mercado import TransferenciaInvalida
from app.domain.temporada import restaurar_estado, snapshot_estado
from app.repositories import clube_repository as clube_repo
from app.repositories import jogador_repository as jogador_repo
from app.repositories import proposta_repository as proposta_repo
from app.repositories import simulacao_repository as simulacao_repo
from app.repositories import transferencia_repository as transferencia_repo
from app.services import simulacao_service
from app.services.temporada_service import TemporadaConcluida
from scripts.data_loader import carregar_campeonato


# ---------------------------------------------------------------------------
# carregar / gravar o estado vivo
# ---------------------------------------------------------------------------

class _Contexto:
    """Uma temporada em andamento carregada para negociar."""

    def __init__(self, conn, sim, campeonato):
        self.conn = conn
        self.sim = sim
        self.campeonato = campeonato
        self.alvo = next(
            c for c in campeonato.clubes if c.nome == sim["clube_usuario"]
        )

    @property
    def rodada(self):
        return self.campeonato.rodada

    def exigir_janela(self):
        if not mercado.janela_aberta(self.rodada):
            raise TransferenciaInvalida("Janela de transferências fechada")

    def jogador(self, jogador_id):
        """(jogador, clube dono) a partir do id no banco; (None, None) se o
        id não é desta simulação."""
        linha = jogador_repo.buscar(self.conn, jogador_id)
        if linha is None or linha["simulacao_id"] != self.sim["id"]:
            return None, None
        for clube in self.campeonato.clubes:
            for j in clube.jogadores:
                if j.nome == linha["nome"]:
                    return j, clube
        return None, None

    def efetivar(self, jogador_id, jogador, vendedor, comprador, preco):
        """Faz a transferência e regrava tudo o que mudou."""

        mercado.transferir(jogador, vendedor, comprador, preco)

        alvo = self.alvo
        xi = sorted(j.nome for j in alvo.xi_preferido) or None
        cru = simulacao_service._serializar(
            self.campeonato, self.sim["seed"], alvo.nome,
            alvo.tatica, alvo.formacao, xi,
        )
        # o snapshot mantém a corrente de RNG original: negociar não sorteia
        # nada, e o RNG do processo foi devolvido ao que era em `_carregar`
        blob = snapshot_estado(self.campeonato)
        blob["rng"] = json.loads(self.sim["estado_json"])["rng"]

        conn = self.conn
        mapa = clube_repo.atualizar(conn, self.sim["id"], cru["clubes"])
        jogador_repo.atualizar(conn, self.sim["id"], mapa, cru["jogadores"])
        transferencia_repo.inserir(
            conn, self.sim["id"], self.rodada, jogador_id,
            mapa[vendedor.nome], mapa[comprador.nome], preco,
        )
        simulacao_repo.atualizar_estado(
            conn, self.sim["id"],
            estado="em_andamento",
            rodada_atual=self.rodada,
            estado_json=json.dumps(blob),
            campeao="",
            tatica=alvo.tatica,
            formacao=alvo.formacao,
            xi_preferido=json.dumps(xi, ensure_ascii=False) if xi else None,
        )

        return {
            "rodada": self.rodada,
            "jogador_id": jogador_id,
            "jogador": jogador.nome,
            "de_clube": vendedor.nome,
            "para_clube": comprador.nome,
            "valor": preco,
            "caixa": alvo.dinheiro,
        }


def _carregar(conn, simulacao_id):
    """`_Contexto` com o estado vivo restaurado; None se a simulação não
    existe. O RNG do processo é preservado — o snapshot já guarda a corrente
    da temporada."""

    sim = simulacao_repo.buscar(conn, simulacao_id)
    if sim is None:
        return None
    if sim["estado"] != "em_andamento":
        raise TemporadaConcluida("O mercado fecha quando a temporada termina")

    estado_rng = random.getstate()
    try:
        campeonato = carregar_campeonato()
        restaurar_estado(campeonato, json.loads(sim["estado_json"]))
    finally:
        random.setstate(estado_rng)

    return _Contexto(conn, sim, campeonato)


# ---------------------------------------------------------------------------
# leitura
# ---------------------------------------------------------------------------

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
        "multa_rescisoria": jogador.multa_rescisoria,
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


def _propostas_por_jogador(ctx):
    """{jogador_id: [propostas desta janela]}"""
    por_jogador = {}
    for p in proposta_repo.listar_da_janela(ctx.conn, ctx.sim["id"], ctx.rodada):
        por_jogador.setdefault(p["jogador_id"], []).append(p)
    return por_jogador


def ver_mercado(simulacao_id, posicao=None, valor_max=None):
    """Situação do mercado para o clube dirigido: janela, caixa, o próprio
    elenco (com quantas ofertas cada um tem) e os jogadores dos outros
    clubes (com o motivo de bloqueio e as propostas que ainda dá para
    fazer)."""

    conn = conectar()
    try:
        ctx = _carregar(conn, simulacao_id)
        if ctx is None:
            return None

        alvo = ctx.alvo
        clubes = ctx.campeonato.clubes
        ids = {
            r["nome"]: r["id"]
            for r in jogador_repo.listar_por_simulacao(conn, simulacao_id)
        }
        propostas = _propostas_por_jogador(ctx)
        aberta = mercado.janela_aberta(ctx.rodada)
        fechada = None if aberta else "Janela de transferências fechada"

        elenco = []
        for j in sorted(alvo.jogadores, key=lambda j: -j.overall):
            n_ofertas = len(mercado.ofertas(j, alvo, clubes)) if aberta else 0
            bloqueio = fechada or mercado.motivo_saida_bloqueada(alvo, j)
            if bloqueio is None and n_ofertas == 0:
                bloqueio = "Nenhum clube tem caixa para comprar"
            elenco.append({
                **_ficha(j, ids[j.nome], alvo),
                "bloqueio": bloqueio,
                "ofertas": n_ofertas,
            })

        disponiveis = []
        for clube in clubes:
            if clube is alvo:
                continue
            for j in clube.jogadores:
                if posicao and j.posicao != posicao:
                    continue
                if valor_max is not None and j.valor_mercado() > valor_max:
                    continue
                feitas = propostas.get(ids[j.nome], [])
                ultima = feitas[-1] if feitas else None
                bloqueio = fechada or mercado.motivo_saida_bloqueada(clube, j)
                if bloqueio is None and len(alvo.jogadores) >= mercado.ELENCO_MAX:
                    bloqueio = f"Seu elenco já tem {mercado.ELENCO_MAX} jogadores"
                disponiveis.append({
                    **_ficha(j, ids[j.nome], clube),
                    "bloqueio": bloqueio,
                    "rival": mercado.sao_rivais(alvo, clube),
                    "propostas_restantes": max(0, mercado.MAX_PROPOSTAS - len(feitas)),
                    "contraproposta": (
                        ultima["valor_pedido"]
                        if ultima and ultima["resposta"] == "contraproposta"
                        else None
                    ),
                })
        disponiveis.sort(key=lambda f: (-f["overall"], f["valor_mercado"]))

        return {
            "rodada": ctx.rodada,
            "janela_aberta": aberta,
            "janelas": list(mercado.JANELAS),
            "clube_usuario": alvo.nome,
            "rivais": sorted(alvo.rivais),
            "caixa": alvo.dinheiro,
            "elenco_min": mercado.ELENCO_MIN,
            "elenco_max": mercado.ELENCO_MAX,
            "max_propostas": mercado.MAX_PROPOSTAS,
            "elenco": elenco,
            "disponiveis": disponiveis,
            "transferencias": _historico(conn, simulacao_id),
        }
    finally:
        conn.close()


def ofertas(simulacao_id, jogador_id):
    """O que cada clube paga por um jogador do elenco dirigido. None se a
    simulação ou o jogador não existem."""

    conn = conectar()
    try:
        ctx = _carregar(conn, simulacao_id)
        if ctx is None:
            return None
        jogador, dono = ctx.jogador(jogador_id)
        if jogador is None:
            return None
        if dono is not ctx.alvo:
            raise TransferenciaInvalida(f"{jogador.nome} não é do seu elenco")
        ctx.exigir_janela()

        return {
            "jogador_id": jogador_id,
            "jogador": jogador.nome,
            "valor_mercado": jogador.valor_mercado(),
            "bloqueio": mercado.motivo_saida_bloqueada(ctx.alvo, jogador),
            "ofertas": [
                {
                    "clube": o.clube.nome,
                    "valor": o.valor,
                    "seria_titular": o.titular,
                    "rival": o.rival,
                }
                for o in mercado.ofertas(jogador, ctx.alvo, ctx.campeonato.clubes)
            ],
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# escrita
# ---------------------------------------------------------------------------

def propor(simulacao_id, jogador_id, valor):
    """Proposta de compra pelo jogador de outro clube. Devolve a resposta e,
    se fechou, a transferência. None se a simulação ou o jogador não
    existem."""

    if valor <= 0:
        raise TransferenciaInvalida("A proposta precisa ter um valor positivo")

    conn = conectar()
    try:
        ctx = _carregar(conn, simulacao_id)
        if ctx is None:
            return None
        ctx.exigir_janela()
        jogador, vendedor = ctx.jogador(jogador_id)
        if jogador is None:
            return None
        comprador = ctx.alvo
        if vendedor is comprador:
            raise TransferenciaInvalida(f"{jogador.nome} já é do seu elenco")

        # regras que nem chegam a ser negociação (não gastam tentativa)
        motivo = (
            mercado.motivo_saida_bloqueada(vendedor, jogador)
            or mercado.motivo_entrada_bloqueada(comprador, valor)
        )
        if motivo:
            raise TransferenciaInvalida(motivo)

        feitas = _propostas_por_jogador(ctx).get(jogador_id, [])
        ultima = feitas[-1] if feitas else None
        aceitando_contra = (
            ultima is not None
            and ultima["resposta"] == "contraproposta"
            and valor >= ultima["valor_pedido"]
        )
        # aceitar a contraproposta sempre vale, mesmo no limite de tentativas
        if len(feitas) >= mercado.MAX_PROPOSTAS and not aceitando_contra:
            raise TransferenciaInvalida(
                f"O {vendedor.nome} encerrou as conversas por {jogador.nome} "
                "nesta janela"
            )

        resposta = mercado.avaliar_proposta(jogador, vendedor, comprador, valor)

        with conn:
            proposta_repo.inserir(
                conn, simulacao_id, ctx.rodada, jogador_id, valor,
                resposta.tipo,
                resposta.valor if resposta.tipo == "contraproposta" else None,
            )
            transferencia = None
            if resposta.fechou:
                transferencia = ctx.efetivar(
                    jogador_id, jogador, vendedor, comprador, resposta.valor
                )

        restantes = max(0, mercado.MAX_PROPOSTAS - len(feitas) - 1)
        return {
            "resposta": resposta.tipo,
            "motivo": resposta.motivo,
            # o pedido só é revelado na contraproposta — na recusa, revelar
            # transformaria as tentativas num jogo com gabarito
            "valor_pedido": (
                resposta.valor if resposta.tipo == "contraproposta" else None
            ),
            "propostas_restantes": 0 if resposta.fechou else restantes,
            "transferencia": transferencia,
        }
    finally:
        conn.close()


def vender(simulacao_id, jogador_id, clube):
    """Aceita a oferta do `clube` por um jogador do elenco dirigido. A oferta
    é recalculada aqui — o cliente nunca define o preço. None se a simulação
    ou o jogador não existem."""

    conn = conectar()
    try:
        ctx = _carregar(conn, simulacao_id)
        if ctx is None:
            return None
        ctx.exigir_janela()
        jogador, dono = ctx.jogador(jogador_id)
        if jogador is None:
            return None
        if dono is not ctx.alvo:
            raise TransferenciaInvalida(f"{jogador.nome} não é do seu elenco")

        oferta = next(
            (
                o for o in mercado.ofertas(jogador, ctx.alvo, ctx.campeonato.clubes)
                if o.clube.nome == clube
            ),
            None,
        )
        if oferta is None:
            raise TransferenciaInvalida(
                f"O {clube} não tem oferta por {jogador.nome}"
            )

        with conn:
            return ctx.efetivar(
                jogador_id, jogador, ctx.alvo, oferta.clube, oferta.valor
            )
    finally:
        conn.close()
