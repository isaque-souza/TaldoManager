"""Empréstimos do técnico (v1.7): pedir emprestado à CPU, exercer a opção
de compra e emprestar os dele à CPU. As regras ficam em `app.domain.emprestimo`; o estado vivo é o do
`mercado_service` (carregar, regravar).

- `pedir`: o pedido ao clube (duração, parte do salário, taxa e se quer a
  opção de compra). Ele aceita (o jogador chega na hora), contrapropõe ou
  recusa — até `mercado.MAX_PROPOSTAS` pedidos por jogador em cada janela
- `exercer_opcao`: abre a negociação com o valor da cláusula; a etapa 2 (o
  contrato com o jogador) é a de sempre, em `mercado_service.propor_contrato`
  — mas não depende da janela
- `ceder`: empresta um jogador do técnico a um dos clubes interessados
  (`emprestimo.propostas_de_cessao`), nos termos que eles oferecem
- a volta ao clube de origem é do motor (`Campeonato.jogar_rodada`)
"""

from app.db.conexao import conectar
from app.domain import caixa, emprestimo, mercado, papeis
from app.domain.emprestimo import EmprestimoInvalido
from app.repositories import emprestimo_repository as emprestimo_repo
from app.repositories import mensagem_repository as mensagem_repo
from app.repositories import negociacao_repository as negociacao_repo
from app.repositories import observado_repository as observado_repo
from app.repositories import oferta_repository as oferta_repo
from app.repositories import transferencia_repository as transferencia_repo
from app.services import mercado_service


def visao(r, rodada_atual, em_andamento=True):
    """Um empréstimo como a tela mostra. Ativo enquanto a temporada não
    chegou à rodada da volta (e a opção não foi exercida)."""
    if r["comprado"]:
        status = "comprado"
    elif em_andamento and rodada_atual < r["volta"]:
        status = "ativo"
    else:
        status = "encerrado"
    return {
        "emprestimo_id": r["id"],
        "rodada": r["rodada"],
        "jogador_id": r["jogador_id"],
        "jogador": r["jogador"],
        "de_clube": r["de_clube"],
        "para_clube": r["para_clube"],
        "duracao": r["duracao"],
        "volta": r["volta"],
        "parte_salario": r["parte_salario"],
        "taxa": r["taxa"],
        "opcao_compra": r["opcao_compra"],
        "status": status,
    }


def pedir(simulacao_id, jogador_id, duracao, parte_salario, taxa, opcao=False):
    """Pede um jogador de outro clube emprestado. Devolve a resposta e, se
    o clube topou, o empréstimo. None se a simulação ou o jogador não
    existem."""

    if taxa <= 0:
        raise EmprestimoInvalido("A taxa precisa ter um valor positivo")

    conn = conectar()
    try:
        ctx = mercado_service._carregar(conn, simulacao_id)
        if ctx is None:
            return None
        ctx.exigir_janela()
        jogador, cedente = ctx.jogador(jogador_id)
        if jogador is None:
            return None
        tomador = ctx.alvo
        if cedente is tomador:
            raise EmprestimoInvalido(f"{jogador.nome} já é do seu elenco")
        emprestimo.validar(ctx.rodada, duracao, parte_salario)   # não gasta pedido

        def bloqueada(motivo):
            with conn:
                mensagem_repo.inserir(conn, simulacao_id, ctx.rodada, [
                    caixa.negociacao_bloqueada(jogador, cedente, motivo, tomador.dinheiro)
                ])
            return EmprestimoInvalido(motivo)

        motivo = (
            emprestimo.motivo_nao_empresta(jogador, cedente, tomador)
            or mercado.motivo_entrada_bloqueada(tomador, taxa)
        )
        if motivo:
            raise bloqueada(motivo)
        neg = mercado_service._negociacao_de(ctx, jogador.nome)
        if neg and neg["status"] == "aberta":
            raise EmprestimoInvalido(
                f"Já há acordo de compra com o {cedente.nome}: falta o contrato com {jogador.nome}"
            )

        feitos = [
            p for p in emprestimo_repo.listar_pedidos_da_janela(conn, simulacao_id, ctx.rodada)
            if p["jogador_id"] == jogador_id
        ]
        ultimo = feitos[-1] if feitos else None
        aceitando_contra = (
            ultimo is not None
            and ultimo["resposta"] == "contraproposta"
            and (ultimo["duracao"], ultimo["parte_salario"]) == (duracao, parte_salario)
            and taxa >= ultimo["taxa_pedida"]
        )
        if len(feitos) >= mercado.MAX_PROPOSTAS and not aceitando_contra:
            raise bloqueada(
                f"O {cedente.nome} encerrou as conversas por {jogador.nome} nesta janela"
            )

        total = len(ctx.campeonato.calendario)
        resposta = emprestimo.avaliar(
            jogador, cedente, tomador, ctx.rodada, duracao, total, parte_salario, taxa,
        )
        restantes = max(0, mercado.MAX_PROPOSTAS - len(feitos) - 1)
        contra = resposta.valor if resposta.tipo == "contraproposta" else None

        with conn:
            emprestimo_repo.inserir_pedido(
                conn, simulacao_id, ctx.rodada, jogador_id, duracao, parte_salario,
                opcao, taxa, resposta.tipo, contra,
            )
            mensagem_repo.inserir(conn, simulacao_id, ctx.rodada, [
                caixa.resposta_emprestimo(
                    jogador, cedente, taxa, duracao, parte_salario, resposta, restantes,
                )
            ])
            feito = None
            if resposta.fechou:
                # o preço da opção sai do elenco de lá, antes de ele sair
                preco = emprestimo.preco_opcao(jogador, cedente, tomador) if opcao else None
                volta = emprestimo.volta(duracao, total)
                eid = emprestimo_repo.inserir(
                    conn, simulacao_id, ctx.rodada, jogador_id, jogador.nome,
                    cedente.nome, tomador.nome, duracao, volta, parte_salario, taxa, preco,
                )
                emprestimo.emprestar(
                    jogador, cedente, tomador, volta, parte_salario, taxa, preco, eid,
                )
                papeis.completar(tomador)
                mapa = ctx.gravar()
                transferencia_repo.inserir(
                    conn, simulacao_id, ctx.rodada, jogador_id,
                    mapa[cedente.nome], mapa[tomador.nome], taxa, tipo="emprestimo",
                )
                observado_repo.remover(conn, simulacao_id, jogador.nome)
                mensagem_repo.inserir(conn, simulacao_id, ctx.rodada, [
                    caixa.emprestimo_feito(jogador, cedente, taxa, duracao, parte_salario, preco)
                ])
                feito = visao(emprestimo_repo.buscar(conn, eid), ctx.rodada)

        return {
            "resposta": resposta.tipo,
            "motivo": resposta.motivo,
            "taxa_pedida": contra,
            "propostas_restantes": 0 if resposta.fechou else restantes,
            "emprestimo": feito,
            "caixa": tomador.dinheiro,
        }
    finally:
        conn.close()


def exercer_opcao(simulacao_id, emprestimo_id):
    """Exerce a opção de compra de um empréstimo ativo: o valor fica
    travado e abre a negociação do contrato (etapa 2), em qualquer rodada.
    None se a simulação ou o empréstimo não existem."""

    conn = conectar()
    try:
        ctx = mercado_service._carregar(conn, simulacao_id)
        if ctx is None:
            return None
        r = emprestimo_repo.buscar(conn, emprestimo_id)
        if r is None or r["simulacao_id"] != simulacao_id:
            return None
        if r["opcao_compra"] is None:
            raise EmprestimoInvalido("Este empréstimo não tem opção de compra")
        jogador, dono = ctx.jogador(r["jogador_id"])
        ativo = (
            jogador is not None and dono is ctx.alvo and jogador.emprestimo
            and jogador.emprestimo["id"] == emprestimo_id
        )
        if not ativo:
            raise EmprestimoInvalido(f"O empréstimo de {r['jogador']} já acabou")
        if ctx.alvo.dinheiro < r["opcao_compra"]:
            raise EmprestimoInvalido(
                f"{ctx.alvo.nome} não tem caixa para pagar a opção de compra"
            )

        neg = mercado_service._negociacao_de(ctx, jogador.nome)
        if neg and neg["status"] == "desistiu":
            raise EmprestimoInvalido(
                f"{jogador.nome} recusou o contrato: dá para tentar de novo na próxima rodada"
            )
        if neg and neg["status"] == "aberta":
            neg_id = neg["id"]
        else:
            with conn:
                neg_id = negociacao_repo.inserir(
                    conn, simulacao_id, ctx.rodada, jogador.nome, r["opcao_compra"],
                    jogador_id=r["jogador_id"], clube=r["de_clube"],
                    emprestimo_id=emprestimo_id,
                )
        return {
            "negociacao_id": neg_id,
            "jogador": jogador.nome,
            "clube": r["de_clube"],
            "valor": r["opcao_compra"],
        }
    finally:
        conn.close()


def interessados(ctx, jogador):
    """O bloco "emprestar" da ficha de um jogador do técnico: o motivo de
    bloqueio e, por duração desta janela, os clubes interessados."""
    total = len(ctx.campeonato.calendario)
    bloqueio = (
        (None if mercado.janela_aberta(ctx.rodada) else "Janela de transferências fechada")
        or emprestimo.motivo_nao_cede(jogador, ctx.alvo)
    )
    if bloqueio:
        return {"bloqueio": bloqueio, "duracoes": []}
    return {
        "bloqueio": None,
        "duracoes": [
            {
                "duracao": d,
                "volta": emprestimo.volta(d, total),
                "propostas": [
                    {"clube": p.clube.nome, "parte_salario": p.parte, "taxa": p.taxa,
                     "seria_titular": p.titular}
                    for p in emprestimo.propostas_de_cessao(
                        jogador, ctx.alvo, ctx.campeonato.clubes, ctx.rodada, d, total,
                    )
                ],
            }
            for d in emprestimo.duracoes(ctx.rodada)
        ],
    }


def ceder(simulacao_id, jogador_id, clube, duracao):
    """Empresta um jogador do técnico ao `clube`, nos termos que ele
    ofereceu para `duracao`. None se a simulação ou o jogador não
    existem."""

    conn = conectar()
    try:
        ctx = mercado_service._carregar(conn, simulacao_id)
        if ctx is None:
            return None
        ctx.exigir_janela()
        jogador = mercado_service._do_meu_elenco(ctx, jogador_id)
        if jogador is None:
            return None
        cedente = ctx.alvo
        emprestimo.validar(ctx.rodada, duracao, emprestimo.PARTES_SALARIO[-1])
        motivo = emprestimo.motivo_nao_cede(jogador, cedente)
        if motivo:
            raise EmprestimoInvalido(motivo)
        total = len(ctx.campeonato.calendario)
        proposta = next(
            (p for p in emprestimo.propostas_de_cessao(
                jogador, cedente, ctx.campeonato.clubes, ctx.rodada, duracao, total,
            ) if p.clube.nome == clube),
            None,
        )
        if proposta is None:
            raise EmprestimoInvalido(f"O {clube} não está interessado em {jogador.nome}")

        tomador, volta = proposta.clube, emprestimo.volta(duracao, total)
        with conn:
            eid = emprestimo_repo.inserir(
                conn, simulacao_id, ctx.rodada, jogador_id, jogador.nome,
                cedente.nome, tomador.nome, duracao, volta, proposta.parte, proposta.taxa, None,
            )
            emprestimo.emprestar(
                jogador, cedente, tomador, volta, proposta.parte, proposta.taxa,
                emprestimo_id=eid, pelo_tecnico=True,
            )
            mapa = ctx.gravar()
            transferencia_repo.inserir(
                conn, simulacao_id, ctx.rodada, jogador_id,
                mapa[cedente.nome], mapa[tomador.nome], proposta.taxa, tipo="emprestimo",
            )
            # as ofertas de compra por ele caem: saiu do elenco
            oferta_repo.retirar_do_jogador(conn, simulacao_id, ctx.rodada, jogador_id)
            mensagem_repo.inserir(conn, simulacao_id, ctx.rodada, [
                caixa.emprestimo_cedido(
                    jogador, tomador, proposta.taxa, duracao, proposta.parte, proposta.titular,
                )
            ])
            feito = visao(emprestimo_repo.buscar(conn, eid), ctx.rodada)
        return {"emprestimo": feito, "caixa": cedente.dinheiro}
    finally:
        conn.close()
