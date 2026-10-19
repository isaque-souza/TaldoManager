"""Empréstimos (v1.7, passo 6).

Regras puras, sem banco. Por enquanto o técnico pega emprestado da CPU
(emprestar os dele é o passo seguinte):

- DURAÇÃO: na pré-temporada, até a virada do turno (19 rodadas) ou a
  temporada inteira; na janela da virada do turno, até o fim. Ele volta
  sozinho ao clube de origem quando acaba (`devolver_vencidos`).
- CUSTO: quem recebe paga uma taxa (até 10% do valor por uma temporada
  inteira, proporcional ao tempo) e uma parte do salário (50, 75 ou 100%);
  o clube de origem paga o resto. Quanto mais salário o técnico banca,
  menor a taxa.
- QUEM O CLUBE EMPRESTA: quem não é titular nem ídolo lá, e nunca para o
  rival. A taxa pedida fica escondida, como nas compras: a resposta é
  aceita, contraproposta (revela o pedido) ou recusa.
- OPÇÃO DE COMPRA (opcional): um preço fixo, acima do que o clube pediria
  numa venda. Enquanto o empréstimo dura, o técnico pode exercê-la a
  qualquer rodada (é cláusula, não depende da janela): o valor fica
  travado e falta só o contrato com o jogador, como na compra.

O jogador emprestado fica no elenco de quem o recebe, com
`Jogador.emprestimo` = {"de", "volta", "parte", "opcao", "id"}; o contrato
continua sendo o do clube de origem (não renova, não vai à lista, não é
dispensado). Tudo determinístico (sem `random`).
"""

from app.domain import fama, mercado

TURNO = "turno"           # até a virada do turno
TEMPORADA = "temporada"   # até o fim da temporada
DURACOES = (TURNO, TEMPORADA)

PARTES_SALARIO = (50, 75, 100)   # % do salário que quem recebe paga

TAXA_TEMPORADA = 0.10            # do valor, por uma temporada inteira
FATOR_PARTE = {50: 1.5, 75: 1.0, 100: 0.5}
# o que mexe no pedido sem o técnico ver (como em `mercado.preco_pedido`)
FATOR_VAI_JOGAR = 0.8            # titular no clube que recebe: bom para ele
FATOR_ENDIVIDADO = 1.2           # o clube de origem precisa do dinheiro
FATOR_OPCAO = 1.25               # opção de compra sobre o preço de venda
TAXA_MINIMA = 10_000
AVISO_OPCAO = 3                  # rodadas antes do fim: o aviso da opção


class EmprestimoInvalido(mercado.TransferenciaInvalida):
    """O empréstimo fere alguma regra."""


def duracoes(rodada):
    """As durações possíveis numa janela (nenhuma com ela fechada)."""
    if rodada == mercado.JANELAS[0]:
        return DURACOES
    if rodada == mercado.JANELAS[1]:
        return (TEMPORADA,)
    return ()


def volta(duracao, total_rodadas):
    """A rodada ANTES da qual ele volta (a de depois da última que joga)."""
    return mercado.JANELAS[1] if duracao == TURNO else total_rodadas + 1


def _fracao(rodada, duracao, total_rodadas):
    return (volta(duracao, total_rodadas) - rodada) / total_rodadas


def motivo_nao_empresta(jogador, cedente, tomador):
    """Por que o `cedente` não empresta o jogador ao `tomador` (None =
    empresta)."""
    if jogador.emprestimo:
        return f"{jogador.nome} já está emprestado"
    if mercado.sao_rivais(cedente, tomador):
        return f"O {cedente.nome} não empresta para o rival"
    if fama.idolo(jogador):
        return f"O {cedente.nome} não empresta um ídolo da torcida"
    if mercado.seria_titular(cedente, jogador):
        return f"{jogador.nome} é titular no {cedente.nome}"
    return mercado.motivo_saida_bloqueada(cedente, jogador)


def taxa_base(jogador, rodada, duracao, total_rodadas, parte):
    """A taxa sem os fatores escondidos: o ponto de partida da tela."""
    taxa = (jogador.valor_mercado() * TAXA_TEMPORADA
            * _fracao(rodada, duracao, total_rodadas) * FATOR_PARTE[parte])
    return max(TAXA_MINIMA, round(taxa / 10_000) * 10_000)


def taxa_pedida(jogador, cedente, tomador, rodada, duracao, total_rodadas, parte):
    taxa = taxa_base(jogador, rodada, duracao, total_rodadas, parte)
    if mercado.seria_titular(tomador, jogador):
        taxa *= FATOR_VAI_JOGAR
    if cedente.dinheiro < 0:
        taxa *= FATOR_ENDIVIDADO
    return max(TAXA_MINIMA, round(taxa / 10_000) * 10_000)


def preco_opcao(jogador, cedente, tomador):
    """O preço fixo da opção de compra (nunca acima da multa rescisória)."""
    preco = mercado._arredondar(mercado.preco_pedido(jogador, cedente, tomador) * FATOR_OPCAO)
    if jogador.multa_rescisoria is not None:
        preco = min(preco, jogador.multa_rescisoria)
    return preco


def validar(rodada, duracao, parte):
    if duracao not in duracoes(rodada):
        if not duracoes(rodada):
            raise EmprestimoInvalido("Janela de transferências fechada")
        raise EmprestimoInvalido(
            "Nesta janela o empréstimo só vale até o fim da temporada"
        )
    if parte not in PARTES_SALARIO:
        raise EmprestimoInvalido(
            f"A parte do salário é {', '.join(f'{p}%' for p in PARTES_SALARIO)}"
        )


def avaliar(jogador, cedente, tomador, rodada, duracao, total_rodadas, parte, taxa):
    """Resposta do `cedente` a um pedido de empréstimo com `taxa`
    (`mercado.Resposta`: aceita, contraproposta ou recusada)."""
    pedido = taxa_pedida(jogador, cedente, tomador, rodada, duracao, total_rodadas, parte)
    if taxa >= pedido:
        return mercado.Resposta("aceita", taxa, f"O {cedente.nome} topou o empréstimo")
    if taxa >= mercado.FAIXA_CONTRAPROPOSTA * pedido:
        return mercado.Resposta(
            "contraproposta", pedido, f"O {cedente.nome} topa, mas quer uma taxa maior",
        )
    return mercado.Resposta(
        "recusada", pedido, f"O {cedente.nome} achou a taxa baixa demais",
    )


def emprestar(jogador, cedente, tomador, volta_antes_da, parte, taxa, opcao=None,
              emprestimo_id=None):
    """Leva o jogador do `cedente` ao `tomador` até `volta_antes_da` e lança
    a taxa nos dois caixas. Levanta `EmprestimoInvalido` se alguma regra
    impedir."""
    if jogador not in cedente.jogadores:
        raise EmprestimoInvalido(f"{jogador.nome} não joga no {cedente.nome}")
    motivo = (
        motivo_nao_empresta(jogador, cedente, tomador)
        or mercado.motivo_entrada_bloqueada(tomador, taxa)
    )
    if motivo:
        raise EmprestimoInvalido(motivo)

    mercado.tirar_do_elenco(cedente, jogador)
    tomador.contratar_jogador(jogador)
    jogador.a_venda = False
    jogador.emprestimo = {
        "de": cedente.nome, "volta": volta_antes_da, "parte": parte,
        "opcao": opcao, "id": emprestimo_id,
    }
    tomador.lancar("despesa_compras", taxa)
    cedente.lancar("receita_vendas", taxa)


def devolver(jogador, tomador, cedente):
    """O empréstimo acabou (ou a opção foi exercida): ele volta ao elenco de
    origem. O tempo de casa lá não muda."""
    mercado.tirar_do_elenco(tomador, jogador)
    cedente.contratar_jogador(jogador)
    jogador.emprestimo = None


def devolver_vencidos(clubes, rodada):
    """Devolve quem tem empréstimo acabando antes de `rodada`. Devolve a
    lista de (jogador, tomador, cedente)."""
    por_nome = {c.nome: c for c in clubes}
    devolvidos = []
    for tomador in clubes:
        for jogador in list(tomador.jogadores):
            e = jogador.emprestimo
            if e and e["volta"] <= rodada:
                cedente = por_nome[e["de"]]
                devolver(jogador, tomador, cedente)
                devolvidos.append((jogador, tomador, cedente))
    return devolvidos


def salario_do_tomador(jogador):
    """O que o clube onde ele joga paga por temporada."""
    e = jogador.emprestimo
    return jogador.salario if not e else round(jogador.salario * e["parte"] / 100)


def salario_do_cedente(jogador):
    """O que o clube de origem ainda paga por um jogador que emprestou."""
    e = jogador.emprestimo
    return 0 if not e else jogador.salario - salario_do_tomador(jogador)
