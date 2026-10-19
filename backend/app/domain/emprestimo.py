"""Empréstimos (v1.7, passo 6).

Regras puras, sem banco. O técnico pega emprestado da CPU e também
empresta os dele (`propostas_de_cessao`):

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
- EMPRESTAR OS DO TÉCNICO: ele escolhe a duração e vê até 3 clubes
  interessados (os que precisam da posição e podem pagar), cada um com a
  parte do salário que banca (conforme o caixa) e a taxa — cheia se ele
  seria titular lá, menor se não. Ídolo não sai, nem para o rival; a CPU
  não pede opção de compra.
- OPÇÃO DE COMPRA (opcional): um preço fixo, acima do que o clube pediria
  numa venda. Enquanto o empréstimo dura, o técnico pode exercê-la a
  qualquer rodada (é cláusula, não depende da janela): o valor fica
  travado e falta só o contrato com o jogador, como na compra.

O jogador emprestado fica no elenco de quem o recebe, com
`Jogador.emprestimo` = {"de", "volta", "parte", "opcao", "id"}; o contrato
continua sendo o do clube de origem (não renova, não vai à lista, não é
dispensado). Tudo determinístico (sem `random`).
"""

from dataclasses import dataclass

from app.domain import fama, mercado, ofertas

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
# a CPU pedindo os do técnico
MAX_INTERESSADOS = 3
FATOR_BANCO_LA = 0.8             # não seria titular lá: paga menos taxa
CAIXA_PARA_PARTE = ((20, 100), (8, 75))   # caixa ≥ N salários → banca P%


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


def motivo_nao_empresta(jogador, cedente, tomador, pelo_tecnico=False):
    """Por que o `cedente` não empresta o jogador ao `tomador` (None =
    empresta). `pelo_tecnico`: quem empresta é o técnico, que decide se
    abre mão de um titular."""
    if jogador.emprestimo:
        return f"{jogador.nome} já está emprestado"
    if mercado.sao_rivais(cedente, tomador):
        return f"O {cedente.nome} não empresta para o rival"
    if fama.idolo(jogador):
        return f"O {cedente.nome} não empresta um ídolo da torcida"
    if not pelo_tecnico and mercado.seria_titular(cedente, jogador):
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
              emprestimo_id=None, pelo_tecnico=False):
    """Leva o jogador do `cedente` ao `tomador` até `volta_antes_da` e lança
    a taxa nos dois caixas. Levanta `EmprestimoInvalido` se alguma regra
    impedir."""
    if jogador not in cedente.jogadores:
        raise EmprestimoInvalido(f"{jogador.nome} não joga no {cedente.nome}")
    motivo = (
        motivo_nao_empresta(jogador, cedente, tomador, pelo_tecnico)
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


@dataclass
class PropostaCessao:
    """Um clube da CPU que quer o jogador do técnico emprestado."""
    clube: object
    parte: int           # % do salário que ele banca
    taxa: int
    titular: bool        # seria titular lá (joga, e jogar faz evoluir)


def parte_que_banca(clube, jogador):
    """Quanto do salário a CPU banca: depende de quantos salários dele
    cabem no caixa."""
    for salarios, parte in CAIXA_PARA_PARTE:
        if clube.dinheiro >= salarios * jogador.salario:
            return parte
    return PARTES_SALARIO[0]


def motivo_nao_cede(jogador, cedente):
    """Por que o técnico não pode emprestar o jogador (None = pode)."""
    if fama.idolo(jogador):
        return "A torcida não aceita ver um ídolo emprestado"
    return (f"{jogador.nome} já está emprestado" if jogador.emprestimo
            else mercado.motivo_saida_bloqueada(cedente, jogador))


def propostas_de_cessao(jogador, cedente, clubes, rodada, duracao, total_rodadas):
    """Os clubes que querem o jogador do técnico emprestado por `duracao`:
    até `MAX_INTERESSADOS`, os que o fariam titular primeiro, depois a
    maior taxa e o caixa mais folgado."""
    lista = []
    for clube in clubes:
        if clube is cedente or mercado.sao_rivais(cedente, clube):
            continue
        if not ofertas._precisa(clube, jogador):
            continue
        parte = parte_que_banca(clube, jogador)
        titular = mercado.seria_titular(clube, jogador)
        taxa = taxa_base(jogador, rodada, duracao, total_rodadas, parte)
        if not titular:
            taxa = max(TAXA_MINIMA, round(taxa * FATOR_BANCO_LA / 10_000) * 10_000)
        if mercado.motivo_entrada_bloqueada(clube, taxa):
            continue
        lista.append(PropostaCessao(clube, parte, taxa, titular))
    lista.sort(key=lambda p: (not p.titular, -p.taxa, -p.clube.dinheiro, p.clube.nome))
    return lista[:MAX_INTERESSADOS]


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
