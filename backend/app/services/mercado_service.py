"""Mercado de transferências de uma temporada rodada a rodada (v0.7).

Só saves "em andamento" têm mercado: é o único modo que para entre as
rodadas para o técnico decidir. As regras ficam em `app.domain.mercado`;
aqui é carregar o estado vivo, aplicar a negociação e regravar tudo
(snapshot, clubes, jogadores, propostas e o histórico em `transferencia`).

- comprar (v1.7, em duas etapas): `propor` → o clube vendedor aceita,
  contrapropõe ou recusa; o aceite abre uma `negociacao` com o valor
  travado e `propor_contrato` acerta salário, anos, multa e papel com o
  jogador — só então a transferência acontece
- vender (v1.7): a CPU faz ofertas (`oferta_service`); o técnico aceita,
  recusa ou contrapropõe (`aceitar_oferta`, `recusar_oferta`,
  `contrapropor_oferta`); `ofertas` lista as de um jogador
- livres (v1.6): `contratar_livre` abre a negociação com quem está sem
  clube (v1.7: só a etapa 2), pagando só as luvas
- elenco (v1.7): `marcar_a_venda` põe/tira da lista de transferências e
  `dispensar` rescinde (a qualquer momento, sem depender da janela)
- empréstimos (v1.7): pedir e exercer a opção ficam no `emprestimo_service`;
  aqui, o que a lista de compra mostra deles e a etapa 2 da opção de compra
"""

import json
import random

from app.db.conexao import conectar
from app.domain import caixa, contrato, emprestimo, fama, livres, mercado, ofertas as ofertas_cpu
from app.domain import papeis, torcida, vontade
from app.domain.contrato import ContratoInvalido
from app.domain.mercado import TransferenciaInvalida
from app.domain.temporada import restaurar_estado, snapshot_estado
from app.repositories import clube_repository as clube_repo
from app.repositories import emprestimo_repository as emprestimo_repo
from app.repositories import jogador_repository as jogador_repo
from app.repositories import mensagem_repository as mensagem_repo
from app.repositories import negociacao_repository as negociacao_repo
from app.repositories import observado_repository as observado_repo
from app.repositories import oferta_repository as oferta_repo
from app.repositories import proposta_repository as proposta_repo
from app.repositories import simulacao_repository as simulacao_repo
from app.repositories import transferencia_repository as transferencia_repo
from app.services import oferta_service, simulacao_service
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
        "liga": clube.liga if clube else None,
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
        # emprestado por outro clube (v1.7)
        "emprestimo": _emprestado(jogador),
    }


def _emprestado(jogador):
    e = jogador.emprestimo
    if not e:
        return None
    return {
        "emprestimo_id": e["id"],
        "de_clube": e["de"],
        "volta": e["volta"],
        "parte_salario": e["parte"],
        "opcao_compra": e["opcao"],
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


def _movimento(r):
    return {
        "temporada": r["temporada"],
        "rodada": r["rodada"],
        "tipo": r["tipo"],
        "jogador_id": r["jogador_id"],
        "jogador": r["jogador"],
        "posicao": r["posicao"],
        "de_clube": r["de_clube"],
        "para_clube": r["para_clube"],
        "valor": r["valor"],
    }


def _historico(conn, simulacao_id):
    return [
        _movimento(r)
        for r in transferencia_repo.listar_por_simulacao(conn, simulacao_id)
    ]


def _lado(r, clube):
    """O movimento do ponto de vista do clube dirigido: compra, venda,
    livre (contratado) ou dispensa; None se ele não está envolvido."""
    if r["tipo"] == "transferencia":
        if r["para_clube"] == clube:
            return "compra"
        if r["de_clube"] == clube:
            return "venda"
        return None
    if r["tipo"] == "livre":
        return "livre" if r["para_clube"] == clube else None
    if r["tipo"] == "emprestimo":
        # a taxa (v1.7): quem recebe paga
        if r["para_clube"] == clube:
            return "emprestimo"
        return "cedido" if r["de_clube"] == clube else None
    return "dispensa" if r["de_clube"] == clube else None


def historico(simulacao_id):
    """As movimentações do técnico (v1.7): compras, vendas, livres e
    dispensas do clube dirigido em todas as temporadas da carreira (num save
    avulso, só nesta), com o gasto e o arrecadado de cada temporada. Lê só
    as tabelas: vale também para temporadas concluídas. None se a simulação
    não existe."""

    conn = conectar()
    try:
        sim = simulacao_repo.buscar(conn, simulacao_id)
        if sim is None:
            return None
        clube = sim["clube_usuario"]
        linhas = (
            transferencia_repo.listar_por_carreira(conn, sim["carreira_id"])
            if sim["carreira_id"] is not None
            else transferencia_repo.listar_por_simulacao(conn, simulacao_id)
        )
    finally:
        conn.close()

    movimentos, por_temporada = [], {}
    for r in linhas:
        lado = _lado(r, clube)
        if lado is None:
            continue
        movimentos.append({**_movimento(r), "tipo": lado})
        t = por_temporada.setdefault(
            r["temporada"], {"temporada": r["temporada"], "gasto": 0, "arrecadado": 0}
        )
        t["arrecadado" if lado in ("venda", "cedido") else "gasto"] += r["valor"]

    temporadas = sorted(por_temporada.values(), key=lambda t: -t["temporada"])
    for t in temporadas:
        t["saldo"] = t["arrecadado"] - t["gasto"]
    gasto = sum(t["gasto"] for t in temporadas)
    arrecadado = sum(t["arrecadado"] for t in temporadas)
    return {
        "clube_usuario": clube,
        "temporada_atual": sim["temporada"],
        "movimentos": movimentos,
        "temporadas": temporadas,
        "total": {"gasto": gasto, "arrecadado": arrecadado, "saldo": arrecadado - gasto},
    }


def _propostas_por_jogador(ctx):
    """{jogador_id: [propostas desta janela]}"""
    por_jogador = {}
    for p in proposta_repo.listar_da_janela(ctx.conn, ctx.sim["id"], ctx.rodada):
        por_jogador.setdefault(p["jogador_id"], []).append(p)
    return por_jogador


class _Janela:
    """O que a lista de compra precisa saber da janela atual: os ids dos
    jogadores, as propostas e negociações feitas, se está fechada e quem o
    técnico observa (v1.7)."""

    def __init__(self, ctx):
        conn, sid = ctx.conn, ctx.sim["id"]
        self.ids = {
            r["nome"]: r["id"] for r in jogador_repo.listar_por_simulacao(conn, sid)
        }
        self.propostas = _propostas_por_jogador(ctx)
        self.negociacoes = [
            _resumo(n) for n in negociacao_repo.listar_da_janela(conn, sid, ctx.rodada)
        ]
        # a última de cada jogador (v1.7): aberta, fechada, desistiu...
        self.por_nome = {n["jogador"]: n for n in self.negociacoes}
        self.aberta = mercado.janela_aberta(ctx.rodada)
        self.fechada = None if self.aberta else "Janela de transferências fechada"
        self.observados = {r["nome"] for r in observado_repo.listar(conn, sid)}
        # o prestígio dos clubes, para o interesse de cada um em vir (v1.9)
        self.prestigio = vontade.prestigio(ctx.campeonato.clubes)
        # pedidos de empréstimo desta janela (v1.7), por jogador
        self.pedidos = {}
        for p in emprestimo_repo.listar_pedidos_da_janela(conn, sid, ctx.rodada):
            self.pedidos.setdefault(p["jogador_id"], []).append(p)
        self.total_rodadas = len(ctx.campeonato.calendario)


def _interesse(ctx, jogador, vendedor, prest=None):
    """O interesse do jogador em vir para o clube do técnico (v1.9)."""
    return vontade.interesse(jogador, ctx.alvo, vendedor, ctx.campeonato.clubes, prest)


def _interesse_dict(interesse):
    return {
        "nivel": interesse.nivel,
        "pontos": interesse.pontos,
        "motivos": interesse.motivos,
        "bloqueio": interesse.bloqueio,
    }


def _ficha_de_compra(ctx, janela, j, clube):
    """Um jogador de outro clube na lista de compra: o motivo de bloqueio e
    as propostas que ainda dá para fazer."""
    alvo = ctx.alvo
    feitas = janela.propostas.get(janela.ids[j.nome], [])
    ultima = feitas[-1] if feitas else None
    interesse = _interesse(ctx, j, clube, janela.prestigio)
    bloqueio = (
        janela.fechada or mercado.motivo_saida_bloqueada(clube, j) or interesse.bloqueio
    )
    if bloqueio is None and len(alvo.jogadores) >= mercado.ELENCO_MAX:
        bloqueio = f"Seu elenco já tem {mercado.ELENCO_MAX} jogadores"
    return {
        **_ficha(j, janela.ids[j.nome], clube),
        "bloqueio": bloqueio,
        "rival": mercado.sao_rivais(alvo, clube),
        "propostas_restantes": max(0, mercado.MAX_PROPOSTAS - len(feitas)),
        "contraproposta": (
            ultima["valor_pedido"]
            if ultima and ultima["resposta"] == "contraproposta"
            else None
        ),
        "negociacao": janela.por_nome.get(j.nome),
        "observado": j.nome in janela.observados,
        "interesse": _interesse_dict(interesse),
        "pedir_emprestado": _pedido_de_emprestimo(ctx, janela, j, clube),
    }


def _pedido_de_emprestimo(ctx, janela, j, clube):
    """O que a ficha precisa para pedir o jogador emprestado (v1.7): se o
    clube empresta, as durações desta janela com a taxa de partida (sem os
    fatores escondidos), o preço da opção de compra e a última
    contraproposta."""
    alvo, rodada, total = ctx.alvo, ctx.rodada, janela.total_rodadas
    feitos = janela.pedidos.get(janela.ids[j.nome], [])
    ultimo = feitos[-1] if feitos else None
    bloqueio = janela.fechada or emprestimo.motivo_nao_empresta(j, clube, alvo)
    if bloqueio is None and len(alvo.jogadores) >= mercado.ELENCO_MAX:
        bloqueio = f"Seu elenco já tem {mercado.ELENCO_MAX} jogadores"
    return {
        "bloqueio": bloqueio,
        "duracoes": [
            {
                "duracao": d,
                "volta": emprestimo.volta(d, total),
                "taxas": {
                    str(p): emprestimo.taxa_base(j, rodada, d, total, p)
                    for p in emprestimo.PARTES_SALARIO
                },
            }
            for d in emprestimo.duracoes(rodada)
        ],
        "opcao_compra": emprestimo.preco_opcao(j, clube, alvo),
        "propostas_restantes": max(0, mercado.MAX_PROPOSTAS - len(feitos)),
        "contraproposta": (
            {
                "duracao": ultimo["duracao"],
                "parte_salario": ultimo["parte_salario"],
                "opcao": bool(ultimo["opcao"]),
                "taxa": ultimo["taxa_pedida"],
            }
            if ultimo and ultimo["resposta"] == "contraproposta"
            else None
        ),
    }


def _ficha_de_livre(ctx, janela, j):
    """Um jogador sem clube: não tem linha na tabela `jogador` (nem id), vai
    pelo nome."""
    luvas = mercado.luvas(j)
    interesse = _interesse(ctx, j, None, janela.prestigio)
    return {
        **_ficha(j, None, None),
        "luvas": luvas,
        "bloqueio": (
            janela.fechada or mercado.motivo_entrada_bloqueada(ctx.alvo, luvas)
            or interesse.bloqueio
        ),
        "negociacao": janela.por_nome.get(j.nome),
        "observado": j.nome in janela.observados,
        "interesse": _interesse_dict(interesse),
    }


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
        janela = _Janela(ctx)
        ids, aberta, fechada = janela.ids, janela.aberta, janela.fechada

        from app.services.emprestimo_service import interessados   # evita import circular
        recebidas = _ofertas_da_janela(ctx)
        elenco = []
        for j in sorted(alvo.jogadores, key=lambda j: -j.overall):
            n_ofertas = sum(
                1 for o in recebidas
                if o["jogador_id"] == ids[j.nome] and o["status"] == "aberta"
            )
            elenco.append({
                **_ficha(j, ids[j.nome], alvo),
                "bloqueio": fechada or mercado.motivo_saida_bloqueada(alvo, j),
                "ofertas": n_ofertas,
                "rescisao": mercado.rescisao(j),
                "dispensa_bloqueada": mercado.motivo_dispensa_bloqueada(alvo, j),
                **_papel(j),
                # emprestar à CPU (v1.7): só os que são do clube
                "emprestar": None if j.emprestimo else interessados(ctx, j),
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
                disponiveis.append(_ficha_de_compra(ctx, janela, j, clube))
        disponiveis.sort(key=lambda f: (-f["overall"], f["valor_mercado"]))

        livres = []
        for j in ctx.campeonato.livres:
            if posicao and j.posicao != posicao:
                continue
            if valor_max is not None and j.valor_mercado() > valor_max:
                continue
            livres.append(_ficha_de_livre(ctx, janela, j))
        livres.sort(key=lambda f: (-f["overall"], f["luvas"]))

        return {
            "rodada": ctx.rodada,
            "janela_aberta": aberta,
            "janelas": list(mercado.JANELAS),
            "clube_usuario": alvo.nome,
            "liga_usuario": alvo.liga,
            "rivais": sorted(alvo.rivais),
            "caixa": alvo.dinheiro,
            "elenco_min": mercado.ELENCO_MIN,
            "elenco_max": mercado.ELENCO_MAX,
            "max_propostas": mercado.MAX_PROPOSTAS,
            "elenco": elenco,
            "disponiveis": disponiveis,
            "livres": livres,
            "negociacoes": janela.negociacoes,
            "ofertas_recebidas": recebidas,
            "transferencias": _historico(conn, simulacao_id),
            "emprestimos": _emprestimos(ctx),
            "partes_salario": list(emprestimo.PARTES_SALARIO),
        }
    finally:
        conn.close()


def _emprestimos(ctx):
    """Os empréstimos da temporada (v1.7), os ativos primeiro."""
    from app.services.emprestimo_service import visao   # evita import circular
    lista = [
        visao(r, ctx.rodada)
        for r in emprestimo_repo.listar_por_simulacao(ctx.conn, ctx.sim["id"])
    ]
    return sorted(lista, key=lambda e: (e["status"] != "ativo", -e["emprestimo_id"]))


def _oferta(ctx, r):
    """Uma oferta recebida como a tela mostra. Enquanto está aberta, diz se
    ele seria titular lá e quanto da torcida iria embora (rival, ídolo)."""
    clube = next((c for c in ctx.campeonato.clubes if c.nome == r["clube"]), None)
    jogador = next((j for j in ctx.alvo.jogadores if j.nome == r["jogador"]), None)
    visao = {
        "oferta_id": r["id"],
        "jogador_id": r["jogador_id"],
        "jogador": r["jogador"],
        "clube": r["clube"],
        "valor": r["valor"],
        "status": r["status"],
        "espontanea": bool(r["espontanea"]),
        "pedido": r["pedido"],
        "rival": clube is not None and mercado.sao_rivais(ctx.alvo, clube),
        "seria_titular": None,
        "revolta_torcida": None,
        "valor_mercado": None,
    }
    if r["status"] == "aberta" and clube is not None and jogador is not None:
        visao["seria_titular"] = mercado.seria_titular(clube, jogador)
        visao["valor_mercado"] = jogador.valor_mercado()
        # quanto da torcida vai embora (%, negativo): venda ao rival ou de
        # um ídolo (v1.4)
        visao["revolta_torcida"] = round(
            100 * torcida.revolta_da_venda(ctx.alvo, clube, jogador), 1
        ) or None
    return visao


def _ofertas_da_janela(ctx):
    """As ofertas da CPU nesta janela (v1.7); fora da janela, nenhuma."""
    if not mercado.janela_aberta(ctx.rodada):
        return []
    return [
        _oferta(ctx, r)
        for r in oferta_repo.listar_da_janela(ctx.conn, ctx.sim["id"], ctx.rodada)
    ]


def ofertas(simulacao_id, jogador_id):
    """As ofertas recebidas por um jogador do elenco dirigido nesta janela
    (v1.7: quem oferece é a CPU). None se a simulação ou o jogador não
    existem."""

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
            "a_venda": jogador.a_venda,
            "bloqueio": mercado.motivo_saida_bloqueada(ctx.alvo, jogador),
            "ofertas": [o for o in _ofertas_da_janela(ctx) if o["jogador_id"] == jogador_id],
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
            or _interesse(ctx, jogador, vendedor).bloqueio   # v1.9
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


def _oferta_de_pe(ctx, oferta_id):
    """(linha, jogador, clube comprador) de uma oferta aberta desta janela.
    None se ela não é desta simulação."""
    r = oferta_repo.buscar(ctx.conn, oferta_id)
    if r is None or r["simulacao_id"] != ctx.sim["id"]:
        return None
    ctx.exigir_janela()
    if r["rodada"] != ctx.rodada or r["status"] != "aberta":
        raise TransferenciaInvalida("Esta oferta não está mais de pé")
    jogador, dono = ctx.jogador(r["jogador_id"])
    if jogador is None or dono is not ctx.alvo:
        raise TransferenciaInvalida(f"{r['jogador']} não é mais do seu elenco")
    clube = next(c for c in ctx.campeonato.clubes if c.nome == r["clube"])
    return r, jogador, clube


def _vender(ctx, r, jogador, clube, valor, pedido=None):
    """Fecha a venda por uma oferta (ou pela contraproposta aceita). Se o
    comprador não pode mais pagar, a oferta cai."""

    alvo = ctx.alvo
    motivo = mercado.motivo_saida_bloqueada(alvo, jogador)
    if motivo:
        raise TransferenciaInvalida(motivo)
    if mercado.motivo_entrada_bloqueada(clube, valor):
        with ctx.conn:
            oferta_repo.responder(ctx.conn, r["id"], "retirada", pedido)
        raise TransferenciaInvalida(f"O {clube.nome} não tem mais como pagar e retirou a oferta")

    # a torcida reage antes da transferência: o peso do jogador é medido no
    # elenco de onde ele sai (v1.4)
    idolo = fama.idolo(jogador)
    rival = mercado.sao_rivais(alvo, clube)
    revolta = torcida.reagir_a_venda(alvo, clube, jogador)
    with ctx.conn:
        oferta_repo.responder(ctx.conn, r["id"], "aceita", pedido)
        oferta_repo.retirar_do_jogador(ctx.conn, ctx.sim["id"], ctx.rodada, r["jogador_id"])
        mensagem_repo.inserir(ctx.conn, ctx.sim["id"], ctx.rodada, [
            caixa.venda(jogador, clube, valor),
            revolta and caixa.revolta_da_torcida(
                jogador, clube, *revolta, rival=rival, idolo=idolo,
            ),
        ])
        return ctx.efetivar(r["jogador_id"], jogador, alvo, clube, valor)


def aceitar_oferta(simulacao_id, oferta_id):
    """Aceita uma oferta da CPU: a venda acontece na hora. None se a
    simulação ou a oferta não existem."""

    conn = conectar()
    try:
        ctx = _carregar(conn, simulacao_id)
        if ctx is None:
            return None
        achada = _oferta_de_pe(ctx, oferta_id)
        if achada is None:
            return None
        r, jogador, clube = achada
        return _vender(ctx, r, jogador, clube, r["valor"])
    finally:
        conn.close()


def recusar_oferta(simulacao_id, oferta_id):
    """Recusa uma oferta da CPU. None se a simulação ou a oferta não
    existem."""

    conn = conectar()
    try:
        ctx = _carregar(conn, simulacao_id)
        if ctx is None:
            return None
        achada = _oferta_de_pe(ctx, oferta_id)
        if achada is None:
            return None
        r, _, _ = achada
        with conn:
            oferta_repo.responder(conn, oferta_id, "recusada")
        return {"oferta_id": oferta_id, "jogador": r["jogador"], "clube": r["clube"],
                "status": "recusada"}
    finally:
        conn.close()


def contrapropor_oferta(simulacao_id, oferta_id, valor):
    """Pede mais por uma oferta, uma vez só: o clube aceita (a venda fecha
    pelo pedido) ou retira a oferta. None se a simulação ou a oferta não
    existem."""

    conn = conectar()
    try:
        ctx = _carregar(conn, simulacao_id)
        if ctx is None:
            return None
        achada = _oferta_de_pe(ctx, oferta_id)
        if achada is None:
            return None
        r, jogador, clube = achada
        resposta = ofertas_cpu.responder_contraproposta(r["valor"], r["teto"], valor)
        if resposta == "aceita":
            transferencia = _vender(ctx, r, jogador, clube, valor, pedido=valor)
            return {"resposta": "aceita", "transferencia": transferencia,
                    "caixa": ctx.alvo.dinheiro}
        with conn:
            oferta_repo.responder(conn, oferta_id, "retirada", valor)
            mensagem_repo.inserir(conn, simulacao_id, ctx.rodada, [
                caixa.oferta_retirada(r["jogador"], r["clube"], valor),
            ])
        return {"resposta": "retirada", "transferencia": None, "caixa": ctx.alvo.dinheiro}
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
        motivo = (
            mercado.motivo_entrada_bloqueada(clube, mercado.luvas(jogador))
            or _interesse(ctx, jogador, None).bloqueio   # v1.9
        )
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
    elif neg["emprestimo_id"]:
        # a opção de compra de um empréstimo (v1.7): ele está aqui, emprestado
        jogador, dono = ctx.jogador(neg["jogador_id"])
        vendedor = None
        if (jogador is not None and dono is ctx.alvo and jogador.emprestimo
                and jogador.emprestimo["id"] == neg["emprestimo_id"]):
            vendedor = next(c for c in ctx.campeonato.clubes if c.nome == neg["clube"])
        else:
            jogador = None
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
        "opcao_compra": neg["emprestimo_id"] is not None,   # v1.7
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
            "salario_sugerido": contrato.salario_sugerido_chegada(jogador, ctx.alvo, vendedor),
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
            "interesse": _interesse_dict(_interesse(ctx, jogador, vendedor)),
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
        opcao = neg["emprestimo_id"] is not None
        if not opcao:
            ctx.exigir_janela()   # a opção de compra é cláusula (v1.7)
        jogador, vendedor = _partes(ctx, neg)
        comprador = ctx.alvo
        if opcao:
            # o empréstimo acaba aqui (só vale se ele assinar: nada é gravado
            # sem o contrato): a compra parte do elenco de origem
            emprestimo.devolver(jogador, comprador, vendedor)

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
            jogador, comprador, vendedor, salario, anos, multa, papel,
            _interesse(ctx, jogador, vendedor),
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
                # contratado sai sozinho da lista de observados (v1.7)
                observado_repo.remover(conn, simulacao_id, jogador.nome)
                if opcao:
                    emprestimo_repo.marcar_comprado(conn, neg["emprestimo_id"])
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
                    mapa = ctx.gravar()
                    # no histórico (v1.7): sem clube de origem, valor = luvas
                    transferencia_repo.inserir(
                        conn, simulacao_id, ctx.rodada,
                        jogador_repo.buscar_por_nome(conn, simulacao_id, jogador.nome)["id"],
                        None, mapa[comprador.nome], neg["valor"], tipo="livre",
                    )
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
        if a_venda and jogador.emprestimo:
            raise TransferenciaInvalida(
                f"{jogador.nome} está emprestado pelo {jogador.emprestimo['de']}"
            )
        jogador.a_venda = a_venda
        novas = []
        with conn:
            ctx.gravar()
            # com a janela aberta, a CPU olha na hora (v1.7)
            if a_venda and mercado.janela_aberta(ctx.rodada):
                novas = oferta_service.ao_listar(
                    conn, simulacao_id, ctx.rodada, ctx.campeonato, ctx.alvo,
                    jogador, jogador_id,
                )
        return {"jogador_id": jogador_id, "jogador": jogador.nome, "a_venda": a_venda,
                "ofertas": len(novas)}
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
            mapa = ctx.gravar()
            # no histórico (v1.7): sem clube de destino, valor = rescisão
            transferencia_repo.inserir(
                conn, simulacao_id, ctx.rodada, jogador_id,
                mapa[clube.nome], None, custo, tipo="dispensa",
            )
            oferta_repo.retirar_do_jogador(conn, simulacao_id, ctx.rodada, jogador_id)
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
