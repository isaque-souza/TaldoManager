"""Mercado de transferências de uma temporada rodada a rodada (v0.7).

Só saves "em andamento" têm mercado: é o único modo que para entre as
rodadas para o técnico decidir. As regras ficam em `app.domain.mercado`;
aqui é carregar o estado vivo, aplicar a negociação e regravar tudo
(snapshot, clubes, jogadores, propostas e o histórico em `transferencia`).

- comprar (v1.7, em duas etapas): `propor` → o clube vendedor aceita,
  contrapropõe ou recusa; o aceite abre uma `negociacao` com o valor
  travado e `propor_contrato` acerta salário, anos, multa e papel com o
  jogador — só então a transferência acontece
- vender: `ofertas` lista o que cada clube paga; `vender` aceita uma delas
- livres (v1.6): `contratar_livre` abre a negociação com quem está sem
  clube (v1.7: só a etapa 2), pagando só as luvas
- elenco (v1.7): `marcar_a_venda` põe/tira da lista de transferências e
  `dispensar` rescinde (a qualquer momento, sem depender da janela)
"""

import json
import random

from app.db.conexao import conectar
from app.domain import caixa, contrato, fama, livres, mercado, papeis, torcida
from app.domain.contrato import ContratoInvalido
from app.domain.mercado import TransferenciaInvalida
from app.domain.temporada import restaurar_estado, snapshot_estado
from app.repositories import clube_repository as clube_repo
from app.repositories import jogador_repository as jogador_repo
from app.repositories import mensagem_repository as mensagem_repo
from app.repositories import negociacao_repository as negociacao_repo
from app.repositories import proposta_repository as proposta_repo
from app.repositories import simulacao_repository as simulacao_repo
from app.repositories import transferencia_repository as transferencia_repo
from app.services import simulacao_service
from app.services.temporada_service import (
    TemporadaConcluida, exigir_sem_transmissao,
)
from scripts.data_loader import carregar_campeonato_do_save


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
        # antes da 1ª rodada (ou com reforço novo) ainda há quem não tem papel
        papeis.completar(self.alvo)

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

    def gravar(self):
        """Regrava o estado vivo depois de uma mudança fora das partidas
        (transferência, renovação). Devolve o mapa {clube: id}."""

        exigir_sem_transmissao(self.sim)

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
        return mapa

    def efetivar(self, jogador_id, jogador, vendedor, comprador, preco,
                 termos=None, papel=None):
        """Faz a transferência e regrava tudo o que mudou. `termos` e
        `papel`: o contrato combinado com o jogador (v1.7)."""

        mercado.transferir(jogador, vendedor, comprador, preco, termos)
        if papel:
            jogador.papel = papel
        mapa = self.gravar()
        transferencia_repo.inserir(
            self.conn, self.sim["id"], self.rodada, jogador_id,
            mapa[vendedor.nome], mapa[comprador.nome], preco,
        )

        return {
            "rodada": self.rodada,
            "jogador_id": jogador_id,
            "jogador": jogador.nome,
            "de_clube": vendedor.nome,
            "para_clube": comprador.nome,
            "valor": preco,
            "caixa": self.alvo.dinheiro,
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
        campeonato = carregar_campeonato_do_save(sim)
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
        "clube": clube.nome if clube else None,
        "posicao": jogador.posicao,
        "funcao": jogador.funcao,
        "atributos": jogador.atributos,
        "idade": jogador.idade,
        "overall": jogador.overall,
        "potencial": jogador.potencial,
        "valor_mercado": jogador.valor_mercado(),
        "salario": jogador.salario,
        "salario_referencia": jogador.salario_referencia(),
        "contrato_anos": jogador.contrato_anos,
        "multa_rescisoria": jogador.multa_rescisoria,
        "fama": jogador.fama,
        "idolo": fama.idolo(jogador),
        "a_venda": jogador.a_venda,
        # a temporada até aqui (ficha da Central do Elenco, v1.7)
        "numero": jogador.numero,
        "partidas": jogador.partidas,
        "gols": jogador.gols,
        "assistencias": jogador.assistencias,
        "nota_media": jogador.nota_media(),
    }


def _papel(jogador):
    """Papel no elenco (v1.7): o prometido, o humor e quanto da meta ele
    está cumprindo."""
    meta = papeis.META.get(jogador.papel)
    fracao = papeis.aproveitamento(jogador)
    return {
        "papel": jogador.papel,
        "humor": jogador.humor,
        "titularidades": jogador.titularidades,
        "jogos_disponivel": jogador.jogos_disponivel,
        "meta_conta": meta[0] if meta else None,
        "meta_fracao": meta[1] if meta else None,
        "aproveitamento": round(fracao, 3) if fracao is not None else None,
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
        negociacoes = [
            _resumo(n)
            for n in negociacao_repo.listar_da_janela(conn, simulacao_id, ctx.rodada)
        ]
        # a última de cada jogador (v1.7): aberta, fechada, desistiu...
        por_nome = {n["jogador"]: n for n in negociacoes}
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
                "rescisao": mercado.rescisao(j),
                "dispensa_bloqueada": mercado.motivo_dispensa_bloqueada(alvo, j),
                **_papel(j),
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
                    "negociacao": por_nome.get(j.nome),
                })
        disponiveis.sort(key=lambda f: (-f["overall"], f["valor_mercado"]))

        # sem clube não têm linha na tabela `jogador` (nem id): vão pelo nome
        livres = []
        for j in ctx.campeonato.livres:
            if posicao and j.posicao != posicao:
                continue
            if valor_max is not None and j.valor_mercado() > valor_max:
                continue
            luvas = mercado.luvas(j)
            livres.append({
                **_ficha(j, None, None),
                "luvas": luvas,
                "bloqueio": fechada or mercado.motivo_entrada_bloqueada(alvo, luvas),
                "negociacao": por_nome.get(j.nome),
            })
        livres.sort(key=lambda f: (-f["overall"], f["luvas"]))

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
            "livres": livres,
            "negociacoes": negociacoes,
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
            "idolo": fama.idolo(jogador),
            "bloqueio": mercado.motivo_saida_bloqueada(ctx.alvo, jogador),
            "ofertas": [
                {
                    "clube": o.clube.nome,
                    "valor": o.valor,
                    "seria_titular": o.titular,
                    "rival": o.rival,
                    # quanto da torcida vai embora (%, negativo): venda ao
                    # rival ou de um ídolo (v1.4)
                    "revolta_torcida": round(100 * torcida.revolta_da_venda(
                        ctx.alvo, o.clube, jogador,
                    ), 1) or None,
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

        def bloqueada(motivo):
            # o diretor de futebol conta o que faltou na caixa de entrada
            with conn:
                mensagem_repo.inserir(conn, simulacao_id, ctx.rodada, [
                    caixa.negociacao_bloqueada(
                        jogador, vendedor, motivo, comprador.dinheiro
                    )
                ])
            return TransferenciaInvalida(motivo)

        # regras que nem chegam a ser negociação (não gastam tentativa)
        motivo = (
            mercado.motivo_saida_bloqueada(vendedor, jogador)
            or mercado.motivo_entrada_bloqueada(comprador, valor)
        )
        if motivo:
            raise bloqueada(motivo)

        # já há acordo (falta o contrato) ou ele desistiu nesta janela (v1.7)
        neg = _negociacao_de(ctx, jogador.nome)
        if neg and neg["status"] == "aberta":
            raise TransferenciaInvalida(
                f"Já há acordo com o {vendedor.nome}: falta o contrato com {jogador.nome}"
            )
        if neg and neg["status"] == "desistiu":
            raise bloqueada(f"{jogador.nome} desistiu de vir nesta janela")

        feitas = _propostas_por_jogador(ctx).get(jogador_id, [])
        ultima = feitas[-1] if feitas else None
        aceitando_contra = (
            ultima is not None
            and ultima["resposta"] == "contraproposta"
            and valor >= ultima["valor_pedido"]
        )
        # aceitar a contraproposta sempre vale, mesmo no limite de tentativas
        if len(feitas) >= mercado.MAX_PROPOSTAS and not aceitando_contra:
            raise bloqueada(
                f"O {vendedor.nome} encerrou as conversas por {jogador.nome} "
                "nesta janela"
            )

        resposta = mercado.avaliar_proposta(jogador, vendedor, comprador, valor)
        restantes = max(0, mercado.MAX_PROPOSTAS - len(feitas) - 1)

        with conn:
            mensagem_repo.inserir(conn, simulacao_id, ctx.rodada, [
                caixa.resposta_proposta(
                    jogador, vendedor, comprador, valor, resposta, restantes
                )
            ])
            proposta_repo.inserir(
                conn, simulacao_id, ctx.rodada, jogador_id, valor,
                resposta.tipo,
                resposta.valor if resposta.tipo == "contraproposta" else None,
            )
            # o aceite só trava o valor: a etapa 2 é o contrato (v1.7)
            negociacao = None
            if resposta.fechou:
                negociacao = negociacao_repo.inserir(
                    conn, simulacao_id, ctx.rodada, jogador.nome, resposta.valor,
                    jogador_id=jogador_id, clube=vendedor.nome,
                )

        return {
            "resposta": resposta.tipo,
            "motivo": resposta.motivo,
            # o pedido só é revelado na contraproposta — na recusa, revelar
            # transformaria as tentativas num jogo com gabarito
            "valor_pedido": (
                resposta.valor if resposta.tipo == "contraproposta" else None
            ),
            "propostas_restantes": 0 if resposta.fechou else restantes,
            "negociacao_id": negociacao,
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

        # a torcida reage antes da transferência: o peso do jogador é medido
        # no elenco de onde ele sai (v1.4)
        idolo = fama.idolo(jogador)
        revolta = torcida.reagir_a_venda(ctx.alvo, oferta.clube, jogador)
        with conn:
            mensagem_repo.inserir(conn, simulacao_id, ctx.rodada, [
                caixa.venda(jogador, oferta.clube, oferta.valor),
                revolta and caixa.revolta_da_torcida(
                    jogador, oferta.clube, *revolta,
                    rival=oferta.rival, idolo=idolo,
                ),
            ])
            return ctx.efetivar(
                jogador_id, jogador, ctx.alvo, oferta.clube, oferta.valor
            )
    finally:
        conn.close()


def contratar_livre(simulacao_id, nome):
    """Abre a negociação com um jogador sem clube (v1.6; v1.7: vai direto ao
    contrato, com as luvas fixas). None se a simulação não existe ou ninguém
    com esse nome está livre."""

    conn = conectar()
    try:
        ctx = _carregar(conn, simulacao_id)
        if ctx is None:
            return None
        ctx.exigir_janela()
        jogador = next(
            (j for j in ctx.campeonato.livres if j.nome == nome), None
        )
        if jogador is None:
            return None

        clube = ctx.alvo
        motivo = mercado.motivo_entrada_bloqueada(clube, mercado.luvas(jogador))
        if motivo:
            with conn:
                mensagem_repo.inserir(conn, simulacao_id, ctx.rodada, [
                    caixa.livre_bloqueado(jogador, motivo, clube.dinheiro)
                ])
            raise TransferenciaInvalida(motivo)

        neg = _negociacao_de(ctx, nome)
        if neg and neg["status"] == "desistiu":
            raise TransferenciaInvalida(f"{nome} desistiu de vir nesta janela")
        if neg and neg["status"] == "aberta":
            neg_id = neg["id"]
        else:
            with conn:
                neg_id = negociacao_repo.inserir(
                    conn, simulacao_id, ctx.rodada, nome, mercado.luvas(jogador),
                )
        return {
            "negociacao_id": neg_id,
            "jogador": nome,
            "clube": None,
            "valor": mercado.luvas(jogador),
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# a etapa 2 (v1.7): o contrato com o jogador
# ---------------------------------------------------------------------------

def _negociacao_de(ctx, nome):
    """A última negociação desta janela pelo jogador (ou None)."""
    feitas = [
        n for n in negociacao_repo.listar_da_janela(ctx.conn, ctx.sim["id"], ctx.rodada)
        if n["jogador"] == nome
    ]
    return feitas[-1] if feitas else None


def _partes(ctx, neg):
    """(jogador, vendedor) de uma negociação aberta; vendedor None = livre.
    Levanta `TransferenciaInvalida` se o jogador não está mais onde estava."""
    if neg["clube"] is None:
        jogador = next((j for j in ctx.campeonato.livres if j.nome == neg["jogador"]), None)
        vendedor = None
    else:
        jogador, vendedor = ctx.jogador(neg["jogador_id"])
        if vendedor is not None and vendedor.nome != neg["clube"]:
            jogador = None
    if jogador is None:
        raise TransferenciaInvalida(f"{neg['jogador']} não está mais disponível")
    return jogador, vendedor


def _contraproposta(neg):
    if neg["contra_salario"] is None:
        return None
    return {
        "salario": neg["contra_salario"],
        "anos": neg["contra_anos"],
        "multa": neg["contra_multa"],
        "papel": neg["contra_papel"],
    }


def _resumo(neg):
    return {
        "negociacao_id": neg["id"],
        "jogador_id": neg["jogador_id"],
        "jogador": neg["jogador"],
        "clube": neg["clube"],
        "valor": neg["valor"],
        "status": neg["status"],
        "tentativas_restantes": max(0, contrato.MAX_TENTATIVAS - neg["tentativas"]),
        "contraproposta": _contraproposta(neg),
    }


def _buscar_negociacao(ctx, negociacao_id):
    neg = negociacao_repo.buscar(ctx.conn, negociacao_id)
    if neg is None or neg["simulacao_id"] != ctx.sim["id"]:
        return None
    return neg


def ver_negociacao(simulacao_id, negociacao_id):
    """Tudo para montar a proposta de contrato: o jogador, o que ganha hoje,
    as opções e o papel que ele espera. O salário pedido NÃO é revelado (só
    numa contraproposta). None se não existe."""

    conn = conectar()
    try:
        ctx = _carregar(conn, simulacao_id)
        if ctx is None:
            return None
        neg = _buscar_negociacao(ctx, negociacao_id)
        if neg is None:
            return None
        dados = _resumo(neg)
        if neg["status"] != "aberta":
            return dados
        jogador, vendedor = _partes(ctx, neg)
        return {
            **dados,
            "idade": jogador.idade,
            "overall": jogador.overall,
            "funcao": jogador.funcao,
            "salario_atual": jogador.salario if vendedor else None,
            "salario_referencia": jogador.salario_referencia(),
            "duracao_max": contrato.duracao_max(jogador),
            "opcoes_multa": [
                {"opcao": op, "valor": contrato.valor_multa(jogador, op)}
                for op in contrato.MULTAS
            ],
            "papeis": [
                p for p in papeis.PAPEIS
                if papeis.motivo_papel_bloqueado(jogador, p) is None
            ],
            "papel_esperado": contrato.papel_esperado(ctx.alvo, jogador),
            "clube_mais_fraco": (
                vendedor is not None and contrato.clube_mais_fraco(ctx.alvo, vendedor)
            ),
        }
    finally:
        conn.close()


def propor_contrato(simulacao_id, negociacao_id, salario, anos, multa, papel=None):
    """Etapa 2 (v1.7): o contrato oferecido ao jogador. Aceito, a
    transferência acontece (o valor acertado vai ao clube; para um livre,
    as luvas). Na 3ª recusa ele desiste e o acordo cai. None se a negociação
    não existe."""

    if salario <= 0:
        raise ContratoInvalido("O salário precisa ser positivo")

    conn = conectar()
    try:
        ctx = _carregar(conn, simulacao_id)
        if ctx is None:
            return None
        neg = _buscar_negociacao(ctx, negociacao_id)
        if neg is None:
            return None
        if neg["status"] != "aberta":
            raise TransferenciaInvalida(f"A negociação por {neg['jogador']} já terminou")
        ctx.exigir_janela()
        jogador, vendedor = _partes(ctx, neg)
        comprador = ctx.alvo

        motivo = (
            (vendedor and mercado.motivo_saida_bloqueada(vendedor, jogador))
            or mercado.motivo_entrada_bloqueada(comprador, neg["valor"])
        )
        if motivo:
            raise TransferenciaInvalida(motivo)
        papel = papel or contrato.papel_esperado(comprador, jogador)
        contrato.validar(jogador, anos, multa, papel)   # inválida não gasta tentativa

        contra = _contraproposta(neg)
        aceitando_contra = (
            contra is not None
            and (contra["anos"], contra["multa"], contra["papel"]) == (anos, multa, papel)
            and salario >= contra["salario"]
        )
        if neg["tentativas"] >= contrato.MAX_TENTATIVAS and not aceitando_contra:
            raise TransferenciaInvalida(
                f"{jogador.nome} só aceita a contraproposta que fez"
            )

        resposta = contrato.avaliar_chegada(
            jogador, comprador, vendedor, salario, anos, multa, papel
        )
        restantes = max(0, contrato.MAX_TENTATIVAS - neg["tentativas"] - 1)
        if resposta.fechou:
            status = "fechada"
        elif resposta.tipo == "recusada" and not restantes:
            status = "desistiu"
        else:
            status = "aberta"

        with conn:
            negociacao_repo.registrar_tentativa(
                conn, negociacao_id, status,
                (resposta.valor, anos, multa, papel)
                if resposta.tipo == "contraproposta" else None,
            )
            transferencia = None
            if resposta.fechou:
                termos = (anos, resposta.valor, contrato.valor_multa(jogador, multa))
                if vendedor is not None:
                    # a torcida de lá sente perder um ídolo, ou ver o jogador
                    # ir para o rival (v1.4); a nossa comemora
                    antes = comprador.torcedores
                    if torcida.reagir_a_venda(vendedor, comprador, jogador) and \
                            comprador.torcedores != antes:
                        mensagem_repo.inserir(conn, simulacao_id, ctx.rodada, [
                            caixa.tirado_do_rival(
                                jogador, vendedor, antes, comprador.torcedores,
                            )
                        ])
                    transferencia = ctx.efetivar(
                        neg["jogador_id"], jogador, vendedor, comprador,
                        neg["valor"], termos, papel,
                    )
                else:
                    mercado.contratar_livre(
                        jogador, ctx.campeonato.livres, comprador, termos
                    )
                    jogador.papel = papel
                    ctx.gravar()
            mensagem_repo.inserir(conn, simulacao_id, ctx.rodada, [
                caixa.resposta_contrato(
                    jogador, vendedor, resposta, restantes, neg["valor"],
                    desistiu=status == "desistiu",
                )
            ])

        return {
            "resposta": resposta.tipo,
            "motivo": resposta.motivo,
            "status": status,
            "salario_pedido": (
                resposta.valor if resposta.tipo == "contraproposta" else None
            ),
            "tentativas_restantes": restantes if status == "aberta" else 0,
            "transferencia": transferencia,
            "contrato": (
                {
                    "salario": jogador.salario,
                    "contrato_anos": jogador.contrato_anos,
                    "multa_rescisoria": jogador.multa_rescisoria,
                    "papel": jogador.papel,
                }
                if resposta.fechou else None
            ),
            "caixa": comprador.dinheiro,
        }
    finally:
        conn.close()


def _do_meu_elenco(ctx, jogador_id):
    jogador, dono = ctx.jogador(jogador_id)
    if jogador is None:
        return None
    if dono is not ctx.alvo:
        raise TransferenciaInvalida(f"{jogador.nome} não é do seu elenco")
    return jogador


def marcar_a_venda(simulacao_id, jogador_id, a_venda):
    """Põe (ou tira) um jogador do elenco dirigido na lista de
    transferências (v1.7). None se a simulação ou o jogador não existem."""

    conn = conectar()
    try:
        ctx = _carregar(conn, simulacao_id)
        if ctx is None:
            return None
        jogador = _do_meu_elenco(ctx, jogador_id)
        if jogador is None:
            return None
        jogador.a_venda = a_venda
        with conn:
            ctx.gravar()
        return {"jogador_id": jogador_id, "jogador": jogador.nome, "a_venda": a_venda}
    finally:
        conn.close()


def dispensar(simulacao_id, jogador_id):
    """Rescinde com um jogador do elenco dirigido (v1.7): paga a rescisão e
    ele vai para os livres. A qualquer momento, sem depender da janela. None
    se a simulação ou o jogador não existem."""

    conn = conectar()
    try:
        ctx = _carregar(conn, simulacao_id)
        if ctx is None:
            return None
        jogador = _do_meu_elenco(ctx, jogador_id)
        if jogador is None:
            return None

        clube = ctx.alvo
        motivo = mercado.motivo_dispensa_bloqueada(clube, jogador)
        if motivo:
            raise TransferenciaInvalida(motivo)

        # a torcida reage antes: a dispensa zera o tempo de casa (e o ídolo)
        revolta = torcida.reagir_a_dispensa(clube, jogador)
        custo = livres.dispensar(jogador, clube, ctx.campeonato.livres)
        with conn:
            ctx.gravar()
            mensagem_repo.inserir(conn, simulacao_id, ctx.rodada, [
                caixa.dispensa(jogador, custo),
                revolta and caixa.revolta_da_dispensa(jogador, *revolta),
            ])
        return {
            "rodada": ctx.rodada,
            "jogador_id": jogador_id,
            "jogador": jogador.nome,
            "rescisao": custo,
            "caixa": clube.dinheiro,
        }
    finally:
        conn.close()


def definir_papel(simulacao_id, jogador_id, papel):
    """Muda o papel prometido a um jogador do elenco dirigido (v1.7):
    rebaixar incomoda, promover deixa contente. None se a simulação ou o
    jogador não existem."""

    conn = conectar()
    try:
        ctx = _carregar(conn, simulacao_id)
        if ctx is None:
            return None
        jogador = _do_meu_elenco(ctx, jogador_id)
        if jogador is None:
            return None
        try:
            papeis.definir(jogador, papel)
        except papeis.PapelInvalido as e:
            raise TransferenciaInvalida(str(e)) from e
        with conn:
            ctx.gravar()
        return {
            "jogador_id": jogador_id,
            "jogador": jogador.nome,
            "papel": jogador.papel,
            "humor": jogador.humor,
        }
    finally:
        conn.close()
