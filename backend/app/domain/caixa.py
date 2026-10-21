"""Caixa de entrada do técnico (v1.3): mensagens de cada setor do clube.

Como no Football Manager e no modo carreira do FIFA, quem trabalha no clube
avisa o técnico do que aconteceu: o diretor de futebol responde as
propostas (e diz o que faltou), o departamento médico fala das lesões, o
auxiliar técnico das suspensões e do cansaço, a diretoria da meta.

Aqui só se montam as mensagens (dicts com setor, assunto e corpo), a
partir de fatos que os serviços já têm; quem grava é o
`mensagem_repository`. Nada aqui sorteia.
"""

from app.domain import formato, mercado
from app.domain.diretoria import descricao_meta, situacao

# setores que escrevem para o técnico, na ordem dos filtros da tela
SETORES = (
    "Diretor de futebol",
    "Departamento médico",
    "Auxiliar técnico",
    "Diretoria",
    "Categorias de base",
    "Marketing",
)


def _mensagem(setor, assunto, corpo):
    return {"setor": setor, "assunto": assunto, "corpo": corpo}


def _dinheiro(valor):
    """1.234.567 → "R$ 1,2 mi"; abaixo de 1 milhão, "R$ 850 mil"."""
    return formato.reais(valor)


def _rodadas(n):
    return f"{n} rodada" if n == 1 else f"{n} rodadas"


# ---------------------------------------------------------------------------
# mercado: o diretor de futebol responde as propostas
# ---------------------------------------------------------------------------

def _por_que_custa(jogador, vendedor, comprador):
    """O que encarece o jogador para o vendedor (as razões do pedido, sem o
    número: revelar o pedido na recusa transformaria as tentativas num jogo
    com gabarito)."""
    razoes = []
    if mercado.eh_craque(vendedor, jogador):
        razoes.append("é o craque do elenco deles")
    elif mercado.seria_titular(vendedor, jogador):
        razoes.append("é titular lá")
    if jogador.contrato_anos >= 4:
        razoes.append(f"tem contrato longo ({jogador.contrato_anos} temporadas)")
    if mercado.sao_rivais(vendedor, comprador):
        razoes.append("vender para o rival sai mais caro")
    return razoes


def resposta_proposta(jogador, vendedor, comprador, valor, resposta, restantes):
    """Mensagem do diretor de futebol sobre uma proposta de compra."""
    alvo = f"{jogador.nome} ({jogador.funcao}, {jogador.overall})"
    # o acordo com o clube só trava o valor (v1.7): falta o contrato com ele
    falta = (" Agora falta acertar o contrato com o jogador (salário, anos, "
             "multa e papel) antes da rodada; se a rodada for jogada antes, o "
             "acordo cai.")
    if resposta.tipo == "multa":
        return _mensagem(
            "Diretor de futebol", f"Acordo pela multa: {jogador.nome}",
            f"Cobrimos a multa rescisória de {_dinheiro(resposta.valor)} por "
            f"{alvo} e o {vendedor.nome} não pode recusar.{falta}",
        )
    if resposta.tipo == "aceita":
        return _mensagem(
            "Diretor de futebol", f"Acordo com o {vendedor.nome}: {jogador.nome}",
            f"O {vendedor.nome} aceitou os {_dinheiro(valor)} por {alvo}.{falta}",
        )

    razoes = _por_que_custa(jogador, vendedor, comprador)
    porque = f" Pesou que ele {', '.join(razoes)}." if razoes else ""
    tentativas = (
        f" Ainda dá para fazer mais {restantes} {'proposta' if restantes == 1 else 'propostas'} "
        "nesta janela."
        if restantes else " Eles encerraram as conversas por ele nesta janela."
    )
    if resposta.tipo == "contraproposta":
        falta = resposta.valor - valor
        return _mensagem(
            "Diretor de futebol", f"Contraproposta por {jogador.nome}",
            f"Oferecemos {_dinheiro(valor)} por {alvo}. O {vendedor.nome} topa "
            f"negociar, mas pede {_dinheiro(resposta.valor)}: faltaram "
            f"{_dinheiro(falta)}.{porque} Se cobrirmos o pedido, fecha.{tentativas}",
        )
    return _mensagem(
        "Diretor de futebol", f"Proposta recusada: {jogador.nome}",
        f"Oferecemos {_dinheiro(valor)} por {alvo} e o {vendedor.nome} achou "
        "baixo demais: ficou longe do que eles esperam (menos de "
        f"{round(mercado.FAIXA_CONTRAPROPOSTA * 100)}% do pedido).{porque}"
        f"{tentativas}",
    )


def resposta_contrato(jogador, vendedor, resposta, restantes, valor, desistiu=False,
                      concorrente=None):
    """A etapa 2 (v1.7): o jogador responde o contrato oferecido.
    `concorrente` (v1.9): o clube que também o quer, ou None."""
    de = f" do {vendedor.nome}" if vendedor else " (estava sem clube)"
    disputa = (
        f" O {concorrente} também quer ele: sem contrato até a rodada, ele "
        f"assina lá." if concorrente else ""
    )
    if resposta.fechou:
        pago = (f"Pagamos {_dinheiro(valor)} ao {vendedor.nome}" if vendedor
                else f"Pagamos {_dinheiro(valor)} de luvas")
        return _mensagem(
            "Diretor de futebol", f"Contratado: {jogador.nome}",
            f"{jogador.nome}{de} assinou: {_dinheiro(jogador.salario)} por "
            f"temporada, por {jogador.contrato_anos} "
            f"{'temporada' if jogador.contrato_anos == 1 else 'temporadas'}. "
            f"{pago}. Ele já é do nosso elenco.",
        )
    if desistiu:
        return _mensagem(
            "Diretor de futebol", f"{jogador.nome} desistiu",
            f"{jogador.nome}{de} não gostou das propostas de contrato e "
            "desistiu de vir. O acordo com o clube caiu; nesta janela não dá "
            "para tentar de novo."
            + (f" Ele vai assinar com o {concorrente} no fim da rodada." if concorrente else ""),
        )
    tentativas = (
        f" Ainda dá para fazer mais {restantes} {'proposta' if restantes == 1 else 'propostas'}."
        if restantes else " Não há mais tentativas: só vale aceitar o que ele pediu."
    )
    if resposta.tipo == "contraproposta":
        return _mensagem(
            "Diretor de futebol", f"{jogador.nome} pede mais",
            f"{jogador.nome}{de} topa vir, mas pede {_dinheiro(resposta.valor)} "
            f"por temporada.{tentativas}{disputa}",
        )
    return _mensagem(
        "Diretor de futebol", f"{jogador.nome} recusou o contrato",
        f"{jogador.nome}{de} achou o salário baixo demais.{tentativas}{disputa}",
    )


# --- disputa pela contratação (v1.9) -----------------------------------------

def concorrente_apareceu(jogador, concorrente, salario_aproximado):
    """Outro clube entrou na disputa pelo jogador."""
    return _mensagem(
        "Diretor de futebol", f"O {concorrente} também quer {jogador.nome}",
        f"O {concorrente} ofereceu a {jogador.nome} cerca de "
        f"{_dinheiro(salario_aproximado)} por temporada. Ele vai comparar as "
        "propostas — o salário e o quanto quer jogar em cada clube. Sem "
        "contrato acertado até a rodada, ele assina com o "
        f"{concorrente}.",
    )


def disputas_perdidas(perdidas):
    """`perdidas`: (jogador, clube que ganhou). A rodada foi jogada sem o
    contrato: eles assinaram com o concorrente."""
    if not perdidas:
        return None
    lista = "; ".join(f"{nome} assinou com o {clube}" for nome, clube in perdidas)
    return _mensagem(
        "Diretor de futebol",
        "Perdemos a disputa" if len(perdidas) == 1 else "Perdemos disputas",
        f"Sem contrato acertado a tempo, ficaram com a outra proposta: {lista}.",
    )


def acordos_expirados(nomes):
    """A rodada foi jogada com contratos por acertar (v1.7)."""
    if not nomes:
        return None
    return _mensagem(
        "Diretor de futebol", "Acordos que caíram",
        f"A rodada começou sem o contrato acertado com {', '.join(nomes)}: os "
        "acordos com os clubes caíram.",
    )


def negociacao_bloqueada(jogador, vendedor, motivo, caixa=None):
    """Nem deu para negociar (caixa, elenco cheio, o vendedor não pode
    liberar...): o motivo é o que faltou. Com `caixa`, diz quanto temos."""
    temos = f" Hoje temos {_dinheiro(caixa)} em caixa." if caixa is not None else ""
    return _mensagem(
        "Diretor de futebol", f"Não deu para negociar {jogador.nome}",
        f"Tentamos {jogador.nome}, do {vendedor.nome}, mas não deu: {motivo}.{temos}",
    )


# --- empréstimos (v1.7) ------------------------------------------------------

def _ate(duracao):
    return "a virada do turno" if duracao == "turno" else "o fim da temporada"


def resposta_emprestimo(jogador, cedente, taxa, duracao, parte, resposta, restantes):
    """O diretor de futebol conta a resposta a um pedido de empréstimo."""
    alvo = f"{jogador.nome} ({jogador.funcao}, {jogador.overall})"
    termos = f"até {_ate(duracao)}, pagando {parte}% do salário"
    if resposta.fechou:
        return None   # quem fecha manda a mensagem do empréstimo feito
    tentativas = (
        f" Ainda dá para fazer mais {restantes} {'pedido' if restantes == 1 else 'pedidos'} "
        "nesta janela."
        if restantes else " Eles encerraram as conversas por ele nesta janela."
    )
    if resposta.tipo == "contraproposta":
        return _mensagem(
            "Diretor de futebol", f"Contraproposta pelo empréstimo de {jogador.nome}",
            f"Pedimos {alvo} emprestado ({termos}) com uma taxa de "
            f"{_dinheiro(taxa)}. O {cedente.nome} topa, mas quer "
            f"{_dinheiro(resposta.valor)}. Bancar mais do salário baixa a "
            f"taxa.{tentativas}",
        )
    return _mensagem(
        "Diretor de futebol", f"Empréstimo recusado: {jogador.nome}",
        f"Pedimos {alvo} emprestado ({termos}) com uma taxa de "
        f"{_dinheiro(taxa)} e o {cedente.nome} achou baixo demais.{tentativas}",
    )


def emprestimo_feito(jogador, cedente, taxa, duracao, parte, opcao=None):
    opcao_txt = (
        f" Temos a opção de comprá-lo por {_dinheiro(opcao)} enquanto ele "
        "estiver aqui, em qualquer rodada."
        if opcao else ""
    )
    return _mensagem(
        "Diretor de futebol", f"Emprestado: {jogador.nome}",
        f"{jogador.nome} ({jogador.funcao}, {jogador.overall}) chegou "
        f"emprestado pelo {cedente.nome} até {_ate(duracao)}. Pagamos "
        f"{_dinheiro(taxa)} de taxa e {parte}% do salário "
        f"({_dinheiro(round(jogador.salario * parte / 100))} por temporada); o "
        f"contrato continua com eles.{opcao_txt}",
    )


def emprestimo_cedido(jogador, tomador, taxa, duracao, parte, titular):
    """O técnico emprestou um jogador dele à CPU."""
    la = ("Lá ele deve ser titular: jogando, evolui." if titular
          else "Lá ele não chega como titular.")
    return _mensagem(
        "Diretor de futebol", f"Emprestamos: {jogador.nome}",
        f"{jogador.nome} ({jogador.funcao}, {jogador.overall}) foi emprestado "
        f"ao {tomador.nome} até {_ate(duracao)}. Recebemos {_dinheiro(taxa)} "
        f"de taxa e eles pagam {parte}% do salário; nós, o resto "
        f"({_dinheiro(jogador.salario - round(jogador.salario * parte / 100))} "
        f"por temporada). {la}",
    )


def emprestados_de_volta(nomes_e_clubes):
    """Os nossos que voltaram de empréstimo depois da rodada."""
    if not nomes_e_clubes:
        return None
    lista = ", ".join(f"{n} (estava no {c})" for n, c in nomes_e_clubes)
    return _mensagem(
        "Diretor de futebol", "Voltaram de empréstimo",
        f"O empréstimo acabou e voltaram ao elenco: {lista}. Confira a escalação.",
    )


def emprestimo_acabando(jogador, rodadas):
    """Faltam poucas rodadas e há opção de compra."""
    e = jogador.emprestimo
    return _mensagem(
        "Diretor de futebol", f"O empréstimo de {jogador.nome} está acabando",
        f"{jogador.nome} volta ao {e['de']} em {_rodadas(rodadas)}. Se quisermos "
        f"ficar com ele, a opção de compra é de {_dinheiro(e['opcao'])} (depois "
        "falta só o contrato com ele).",
    )


def emprestimos_encerrados(nomes_e_clubes):
    """Quem voltou ao clube de origem depois da rodada."""
    if not nomes_e_clubes:
        return None
    lista = ", ".join(f"{n} ao {c}" for n, c in nomes_e_clubes)
    return _mensagem(
        "Diretor de futebol", "Fim de empréstimo",
        f"O empréstimo acabou e voltaram: {lista}.",
    )


def venda(jogador, comprador, valor):
    return _mensagem(
        "Diretor de futebol", f"Vendido: {jogador.nome}",
        f"Fechamos a venda de {jogador.nome} para o {comprador.nome} por "
        f"{_dinheiro(valor)}. O dinheiro já entrou no caixa.",
    )


def contratacao_livre(jogador, luvas):
    return _mensagem(
        "Diretor de futebol", f"Contratado: {jogador.nome}",
        f"{jogador.nome} ({jogador.funcao}, {jogador.overall}) estava sem "
        f"clube e assinou por {jogador.contrato_anos} temporadas. Sem "
        f"transferência: pagamos só {_dinheiro(luvas)} de luvas, e o salário "
        f"é de {_dinheiro(jogador.salario)} por temporada.",
    )


def ofertas_pela_lista(por_jogador):
    """As ofertas da CPU pelos jogadores à venda (v1.7): `por_jogador` é uma
    lista de (jogador, [OfertaCpu]). Quem ficou sem oferta também aparece."""
    if not por_jogador:
        return None
    linhas = []
    for jogador, lista in por_jogador:
        if lista:
            clubes = ", ".join(f"{o.clube.nome} ({_dinheiro(o.valor)})" for o in lista)
            linhas.append(f"{jogador.nome}: {clubes}.")
        else:
            linhas.append(f"{jogador.nome}: ninguém se interessou por enquanto.")
    total = sum(len(lista) for _, lista in por_jogador)
    return _mensagem(
        "Diretor de futebol",
        f"{total} oferta{'s' if total != 1 else ''} pela lista de transferências",
        "Os clubes viram quem está à venda. " + " ".join(linhas) +
        " Dá para aceitar, recusar ou pedir mais uma vez; elas valem até a "
        "próxima rodada.",
    )


def assedio(jogador, oferta):
    """Um clube mais forte quer um dos nossos melhores (v1.7)."""
    return _mensagem(
        "Diretor de futebol", f"O {oferta.clube.nome} quer {jogador.nome}",
        f"Sem estar à venda, {jogador.nome} recebeu uma oferta de "
        f"{_dinheiro(oferta.valor)} do {oferta.clube.nome} — "
        f"{_dinheiro(jogador.valor_mercado())} é o valor de mercado dele. A "
        "decisão é sua; a oferta vale até a próxima rodada.",
    )


def oferta_do_sonho(jogador, oferta):
    """O clube do sonho do jogador quer ele (v1.9)."""
    return _mensagem(
        "Diretor de futebol", f"O {oferta.clube.nome}, clube do sonho de {jogador.nome}",
        f"O {oferta.clube.nome} ofereceu {_dinheiro(oferta.valor)} por "
        f"{jogador.nome} ({_dinheiro(jogador.valor_mercado())} é o valor de "
        "mercado dele). É o clube do sonho dele: se não vendermos — recusando, "
        "pedindo demais ou deixando a oferta expirar —, ele vai ficar chateado.",
    )


def sonho_recusado(jogador, clube):
    """O técnico não vendeu o jogador ao clube do sonho (v1.9)."""
    humor = {
        "incomodado": "Está incomodado",
        "quer_sair": "Agora quer sair e foi para a lista de transferências",
    }.get(jogador.humor, "Ficou chateado")
    return _mensagem(
        "Auxiliar técnico", f"{jogador.nome} queria o {clube}",
        f"{jogador.nome} esperava ir para o {clube}, o clube do sonho dele. "
        f"{humor}.",
    )


def relatorios_prontos(nomes):
    """O olheiro terminou relatórios de contratação (v2.0)."""
    if not nomes:
        return None
    if len(nomes) == 1:
        assunto, corpo = (f"Relatório pronto: {nomes[0]}",
                          f"Terminei o relatório sobre {nomes[0]}: preço, salário, "
                          "se ele quer vir e a dificuldade estão na ficha dele.")
    else:
        lista = ", ".join(nomes[:-1]) + f" e {nomes[-1]}"
        assunto, corpo = (f"{len(nomes)} relatórios prontos",
                          f"Terminei os relatórios sobre {lista}: estão nas fichas deles.")
    return _mensagem("Olheiro", assunto, corpo)


def _e(nomes):
    return nomes[0] if len(nomes) == 1 else ", ".join(nomes[:-1]) + f" e {nomes[-1]}"


def peneira(jovens, de_fora):
    """A peneira da base (v2.0): quem chegou e quantos não couberam.
    `jovens`: [(nome, idade, funcao, overall, potencial)]."""
    if not jovens and not de_fora:
        return None
    if jovens:
        linhas = "; ".join(
            f"{n} ({i} anos, {f.lower()}, overall {o}, potencial {p})"
            for n, i, f, o, p in jovens
        )
        corpo = f"A peneira deste ano trouxe {len(jovens)} para a base: {linhas}."
    else:
        corpo = "A peneira deste ano achou jovens, mas a base está cheia."
    if de_fora:
        corpo += (f" {de_fora} {'ficou' if de_fora == 1 else 'ficaram'} de fora por falta de "
                  "vaga: promova ou dispense alguém antes da próxima.")
    return _mensagem("Categorias de base", "Peneira: jovens novos na base", corpo)


def base_na_virada(sairam, ultimo_ano):
    """A base na temporada nova (v2.0): quem fez 20 anos sem ser promovido
    foi embora, e quem está no último ano."""
    partes = []
    if sairam:
        partes.append(f"Deixaram a base sem subir ao profissional: {_e(sairam)}.")
    if ultimo_ano:
        partes.append(f"Último ano na base: {_e(ultimo_ano)}. Promova até o fim da "
                      "temporada ou eles vão embora.")
    if not partes:
        return None
    return _mensagem("Categorias de base", "A base na temporada nova", " ".join(partes))


def oferta_retirada(jogador, clube, pedido):
    """O clube não topou a contraproposta do técnico (v1.7)."""
    return _mensagem(
        "Diretor de futebol", f"O {clube} desistiu de {jogador}",
        f"Pedimos {_dinheiro(pedido)} por {jogador} e o {clube} achou demais: "
        "retirou a oferta.",
    )


def dispensa(jogador, custo):
    """Rescisão feita pelo técnico (v1.7)."""
    paga = (f"Pagamos {_dinheiro(custo)} de rescisão, metade dos salários que "
            f"o contrato ainda devia" if custo else "Sem contrato a pagar")
    return _mensagem(
        "Diretor de futebol", f"Dispensado: {jogador.nome}",
        f"Rescindimos com {jogador.nome}. {paga}. Ele está sem clube e "
        f"pode assinar com quem quiser.",
    )


def revolta_da_dispensa(jogador, antes, depois):
    """Dispensa de um ídolo (v1.7): a torcida sente como uma venda."""
    pct = f"{abs(depois / antes - 1) * 100:.0f}".replace(".", ",")
    return _mensagem(
        "Marketing", "A torcida não perdoou",
        f"Mandar embora {jogador.nome}, um ídolo da casa, deixou a torcida de "
        f"luto: perdemos {pct}% da torcida, de {_torcedores(antes)} para "
        f"{_torcedores(depois)} torcedores.",
    )


def livre_bloqueado(jogador, motivo, caixa=None):
    """Nem deu para contratar o livre (elenco cheio, caixa para as luvas)."""
    temos = f" Hoje temos {_dinheiro(caixa)} em caixa." if caixa is not None else ""
    return _mensagem(
        "Diretor de futebol", f"Não deu para contratar {jogador.nome}",
        f"{jogador.nome} está sem clube, mas não deu: {motivo}.{temos}",
    )


# ---------------------------------------------------------------------------
# depois da rodada: médico e auxiliar técnico
# ---------------------------------------------------------------------------

def foto_do_elenco(clube):
    """O que interessa de cada jogador para comparar antes × depois."""
    return {
        j.nome: {
            "rodadas_lesao": j.rodadas_lesao,
            "jogos_suspensao": j.jogos_suspensao,
            "amarelos_ciclo": j.amarelos_ciclo,
            "vermelhos": j.vermelhos,
            "condicao": j.condicao,
            "funcao": j.funcao,
            # papel no elenco (v1.7)
            "papel": j.papel,
            "humor": j.humor,
            "titularidades": j.titularidades,
            "partidas": j.partidas,
            "jogos_disponivel": j.jogos_disponivel,
        }
        for j in clube.jogadores
    }


def depois_da_rodada(antes, depois, adversario):
    """Mensagens do médico e do auxiliar técnico comparando o elenco antes
    e depois da rodada. A lesão e a suspensão andam uma rodada no começo de
    cada jogo (Partida._avancar_pendencias), então "nova" é o que passou de
    antes − 1. Sem `adversario` (folga), nada andou."""
    mensagens = []
    jogou = adversario is not None
    contra = f" contra o {adversario}" if jogou else ""

    def andou(valor):
        return max(0, valor - 1) if jogou else valor

    for nome, d in depois.items():
        a = antes.get(nome)
        if a is None:
            continue
        posicao = d["funcao"]

        if d["rodadas_lesao"] > andou(a["rodadas_lesao"]):
            n = d["rodadas_lesao"]
            gravidade = (
                "Uma pancada, nada grave" if n <= 2
                else "Um estiramento" if n <= 5 else "Lesão séria"
            )
            mensagens.append(_mensagem(
                "Departamento médico", f"Lesão: {nome}",
                f"{nome} ({posicao}) sentiu{contra}. {gravidade}: fica fora "
                f"das próximas {_rodadas(n)}. Já começou o tratamento.",
            ))
        elif a["rodadas_lesao"] > 0 and d["rodadas_lesao"] == 0:
            mensagens.append(_mensagem(
                "Departamento médico", f"Liberado: {nome}",
                f"{nome} ({posicao}) terminou a recuperação e está liberado "
                "para jogar.",
            ))

        if d["jogos_suspensao"] > andou(a["jogos_suspensao"]):
            motivo = (
                "foi expulso" if d["vermelhos"] > a["vermelhos"]
                else "chegou ao 5º amarelo"
            )
            mensagens.append(_mensagem(
                "Auxiliar técnico", f"Suspenso: {nome}",
                f"{nome} ({posicao}) {motivo}{contra} e cumpre suspensão de "
                f"{_rodadas(d['jogos_suspensao'])}. Vale pensar em quem entra.",
            ))
        elif a["jogos_suspensao"] > 0 and d["jogos_suspensao"] == 0:
            mensagens.append(_mensagem(
                "Auxiliar técnico", f"Fim da suspensão: {nome}",
                f"{nome} ({posicao}) cumpriu a suspensão e volta a ficar "
                "disponível.",
            ))
        elif d["amarelos_ciclo"] == 4 and a["amarelos_ciclo"] < 4:
            mensagens.append(_mensagem(
                "Auxiliar técnico", f"Pendurado: {nome}",
                f"{nome} ({posicao}) está com 4 amarelos: mais um e ele perde "
                "o jogo seguinte.",
            ))

        humor = _mudanca_de_humor(nome, a, d)
        if humor:
            mensagens.append(humor)

    exaustos = sorted(
        n for n, d in depois.items()
        if d["condicao"] == "Exausto" and antes.get(n, {}).get("condicao") != "Exausto"
    )
    if exaustos:
        mensagens.append(_mensagem(
            "Auxiliar técnico", "Jogadores exaustos",
            f"{', '.join(exaustos)} {'chegou' if len(exaustos) == 1 else 'chegaram'} "
            "ao limite. Escalado assim, o jogador rende bem menos e o motor "
            "pode poupá-lo; um rodízio agora ajuda.",
        ))
    return mensagens


# papel no elenco (v1.7): o auxiliar avisa quando o humor muda na checagem
PAPEL_ROTULO = {"titular": "titular", "rotacao": "rotação", "promessa": "promessa", "reserva": "reserva"}


def _tempo_de_jogo(d):
    if d["papel"] == "titular":
        return f"começou {d['titularidades']} de {d['jogos_disponivel']} jogos"
    return f"entrou em {d['partidas']} de {d['jogos_disponivel']} jogos"


def _mudanca_de_humor(nome, a, d):
    if a.get("humor") == d.get("humor") or not d.get("papel"):
        return None
    papel = PAPEL_ROTULO[d["papel"]]
    if d["humor"] == "quer_sair":
        return _mensagem(
            "Auxiliar técnico", f"{nome} quer sair",
            f"{nome}, prometido como {papel}, {_tempo_de_jogo(d)} e pediu para "
            "ser negociado. Ele se colocou na lista de transferências e não "
            "aceita renovar enquanto não voltar a jogar.",
        )
    if d["humor"] == "incomodado" and a.get("humor") == "contente":
        return _mensagem(
            "Auxiliar técnico", f"{nome} está incomodado",
            f"{nome} foi prometido como {papel} e {_tempo_de_jogo(d)}. Se "
            "continuar assim, vai pedir para sair.",
        )
    return _mensagem(
        "Auxiliar técnico", f"{nome} está mais tranquilo",
        f"{nome} voltou a ter o tempo de jogo de {papel} ({_tempo_de_jogo(d)}) "
        "e o clima melhorou.",
    )


# ---------------------------------------------------------------------------
# temporada: diretoria, base e contratos
# ---------------------------------------------------------------------------

def meta_da_temporada(clube, meta, ranking):
    return _mensagem(
        "Diretoria", "A meta da temporada",
        f"Bem-vindo ao comando do {clube}. Pelo elenco, somos a "
        f"{ranking}ª força da liga, e a diretoria espera: "
        f"{descricao_meta(meta).lower()} ({meta}º lugar ou melhor).",
    )


def fim_de_temporada(posicao, meta, campeao, clube):
    if meta is None:
        return None
    s = situacao(posicao, meta)
    if clube == campeao:
        abre = f"Campeões! Terminamos em {posicao}º."
    else:
        abre = f"Terminamos em {posicao}º; o campeão foi o {campeao}."
    fecha = {
        "batida": "Meta cumprida: a diretoria está satisfeita.",
        "perto": f"A meta era o {meta}º: ficou perto, mas a diretoria quer mais.",
        "longe": f"A meta era o {meta}º e ficamos longe: a cobrança vai aumentar.",
    }[s]
    return _mensagem("Diretoria", "Balanço da temporada", f"{abre} {fecha}")


def _torcedores(n):
    """1.234.567 → "1,2 milhão"; abaixo de 1 milhão, "850 mil"."""
    if n >= 1_000_000:
        mi = f"{n / 1_000_000:.1f}".replace(".", ",")
        return f"{mi} {'milhão' if n < 2_000_000 else 'milhões'}"
    return f"{round(n / 1_000)} mil"


def balanco_da_torcida(inicial, final):
    """Fim de temporada (v1.4): o marketing conta quanto a torcida mudou."""
    if not inicial:
        return None
    pct = (final / inicial - 1) * 100
    numero = f"{abs(pct):.1f}".replace(".", ",")
    if pct >= 0.05:
        abre = f"A torcida cresceu {numero}% na temporada"
        fecha = "Mais gente no estádio é mais bilheteria."
    elif pct <= -0.05:
        abre = f"A torcida encolheu {numero}% na temporada"
        fecha = "Vitórias (e clássicos) trazem o torcedor de volta."
    else:
        abre = "A torcida ficou do mesmo tamanho na temporada"
        fecha = "Uma boa campanha faz ela crescer."
    return _mensagem(
        "Marketing", "Balanço da torcida",
        f"{abre}: de {_torcedores(inicial)} para {_torcedores(final)} "
        f"torcedores. {fecha}",
    )


def revolta_da_torcida(jogador, comprador, antes, depois, rival=True, idolo=False):
    """Venda que a torcida não engoliu (v1.4): para o rival, de um ídolo,
    ou as duas coisas. O marketing conta o estrago."""
    pct = f"{abs(depois / antes - 1) * 100:.0f}".replace(".", ",")
    if rival and idolo:
        motivo = (f"Vender {jogador.nome}, um ídolo da casa, justo para o "
                  f"{comprador.nome} caiu como uma traição")
    elif idolo:
        motivo = (f"Vender {jogador.nome}, um ídolo da casa, para o "
                  f"{comprador.nome} deixou a torcida de luto")
    else:
        motivo = f"Vender {jogador.nome} para o {comprador.nome} caiu muito mal"
    festa = (f" Do outro lado, a torcida do {comprador.nome} está em festa."
             if rival else "")
    return _mensagem(
        "Marketing", "A torcida não perdoou",
        f"{motivo}: perdemos {pct}% da torcida, de {_torcedores(antes)} para "
        f"{_torcedores(depois)} torcedores.{festa}",
    )


def tirado_do_rival(jogador, rival, antes, depois):
    """Contratação do rival (v1.4): a nossa torcida comemora."""
    return _mensagem(
        "Marketing", "A torcida está em festa",
        f"Tirar {jogador.nome} do {rival.nome} animou a arquibancada: "
        f"ganhamos {_torcedores(depois - antes)} torcedores, agora somos "
        f"{_torcedores(depois)}.",
    )


def novos_idolos(nomes, clube):
    """Fim de temporada (v1.4): quem virou ídolo da torcida."""
    if not nomes:
        return None
    if len(nomes) == 1:
        abre = f"{nomes[0]} virou ídolo da torcida do {clube}"
    else:
        abre = (f"{', '.join(nomes[:-1])} e {nomes[-1]} viraram ídolos da "
                f"torcida do {clube}")
    return _mensagem(
        "Marketing", "Nasce um ídolo" if len(nomes) == 1 else "Nascem ídolos",
        f"{abre}. Ídolo vende camisa e atrai torcedores a cada temporada, "
        "mas vendê-lo vai doer na arquibancada.",
    )


def homenagem(nome, clube):
    """Um ídolo do clube pendurou as chuteiras (v1.4)."""
    return _mensagem(
        "Marketing", f"Adeus, {nome}",
        f"{nome} se aposentou como ídolo do {clube}. A torcida lotou o "
        "estádio para a despedida, e o nome dele fica na história do clube.",
    )


def campanha(nome, custo, antes, depois):
    """Campanha de marketing feita (v1.4)."""
    return _mensagem(
        "Marketing", f"{nome}: no ar",
        f"A {nome.lower()} saiu por {_dinheiro(custo)} e trouxe "
        f"{_torcedores(depois - antes)} torcedores novos: agora somos "
        f"{_torcedores(depois)}. Mais gente no estádio é mais bilheteria e "
        f"mais pressão no mando de campo.",
    )


def obra_iniciada(nome, lugares, rodadas, custo):
    """Ampliação do estádio contratada (v1.5)."""
    return _mensagem(
        "Estádio", f"{nome}: obra começou",
        f"A obra de +{lugares // 1000} mil lugares saiu por {_dinheiro(custo)}, "
        f"pagos à vista, e fica pronta em {_rodadas(rodadas)}. O estádio "
        "segue funcionando normalmente até lá.",
    )


def obra_concluida(lugares, capacidade):
    """Ampliação do estádio entregue (v1.5)."""
    return _mensagem(
        "Estádio", "Obra concluída",
        f"Os {lugares // 1000} mil lugares novos estão prontos: o estádio "
        f"agora recebe {capacidade:,} torcedores.".replace(",", ".")
        + " Lugar novo tem manutenção a cada jogo em casa, então vale "
        "enchê-lo.",
    )


def mercado_da_cpu(negocios, liga, rivais=()):
    """A janela abriu e os clubes da CPU negociaram entre si (v1.7).
    `negocios`: [(jogador, overall, de, para, valor, liga_do_comprador)];
    os da liga do técnico primeiro (e os do rival em destaque)."""
    if not negocios:
        return None
    ordem = sorted(negocios, key=lambda n: (n[5] != liga, -n[4]))
    itens = [
        f"{nome} ({ovr}): {de} → {para}, {_dinheiro(valor)}"
        + (" — o rival se reforçou" if para in rivais else "")
        for nome, ovr, de, para, valor, _ in ordem[:8]
    ]
    resto = len(negocios) - len(itens)
    return _mensagem(
        "Diretor de futebol", "Movimentações do mercado",
        "A janela abriu e os outros clubes já se mexeram: " + "; ".join(itens)
        + (f". E mais {resto} negócio{'s' if resto > 1 else ''}." if resto else "."),
    )


def obras_na_liga(obras):
    """Virada (v1.5): os clubes da CPU que começaram a ampliar o estádio.
    `obras`: [(clube, lugares)]."""
    if not obras:
        return None
    itens = [f"{nome} (+{lugares // 1000} mil)" for nome, lugares in obras]
    lista = itens[0] if len(itens) == 1 else f"{', '.join(itens[:-1])} e {itens[-1]}"
    verbo = "começou" if len(obras) == 1 else "começaram"
    return _mensagem(
        "Estádio", "Obras na liga",
        f"Estádio lotado vira obra: {lista} {verbo} a ampliar para esta "
        "temporada. Com mais gente na arquibancada, eles ficam mais fortes "
        "em casa.",
    )


def virada(clube, movimentos, contratos_acabando, idolos=()):
    """Mensagens da virada de temporada para o clube do técnico: quem subiu
    da base, quem saiu, quem renovou e os contratos que acabam no fim desta.
    `contratos_acabando`: [(nome, funcao)]; `idolos`: nomes dos ídolos do
    clube antes da virada (os que se aposentam ganham homenagem, v1.4)."""
    do_clube = [m for m in movimentos if m["clube"] == clube]
    mensagens = [
        homenagem(m["jogador"], clube) for m in do_clube
        if m["tipo"] == "aposentou" and m["jogador"] in idolos
    ]

    base = [m for m in do_clube if m["tipo"] == "subiu_da_base"]
    if base:
        linhas = "; ".join(
            f"{m['jogador']} ({m['idade']} anos, overall {m['overall']}, {m['detalhe']})"
            for m in base
        )
        mensagens.append(_mensagem(
            "Categorias de base", "Jovens promovidos ao profissional",
            f"Subiram da base: {linhas}.",
        ))

    saidas = [m for m in do_clube if m["tipo"] in ("aposentou", "saiu_livre")]
    renovados = [m for m in do_clube if m["tipo"] == "renovou"]
    partes = []
    if saidas:
        partes.append("Saíram: " + "; ".join(
            f"{m['jogador']} ({'aposentou' if m['tipo'] == 'aposentou' else m['detalhe'] or 'fim de contrato'})"
            for m in saidas
        ) + ".")
    if renovados:
        partes.append("Renovaram: " + ", ".join(m["jogador"] for m in renovados) + ".")
    if contratos_acabando:
        partes.append(
            "Acabam no fim desta temporada: "
            + ", ".join(f"{n} ({f})" for n, f in contratos_acabando)
            + ". Renove quem quiser manter."
        )
    if partes:
        mensagens.append(_mensagem("Diretoria", "Elenco para a nova temporada", " ".join(partes)))
    return mensagens


# --- copa entre as ligas (v1.6) ---------------------------------------------

_FASE = {
    "oitavas": "as oitavas", "quartas": "as quartas", "semi": "a semifinal",
    "final": "a final",
}
_NA_FASE = {
    "oitavas": "nas oitavas", "quartas": "nas quartas", "semi": "na semifinal",
    "final": "na final",
}


def _placar_copa(jogo, clube):
    """"2 a 1" do ponto de vista do clube, com os pênaltis se teve."""
    em_casa = jogo["mandante"] == clube
    nossos = jogo["gols_mandante"] if em_casa else jogo["gols_visitante"]
    deles = jogo["gols_visitante"] if em_casa else jogo["gols_mandante"]
    texto = f"{nossos} a {deles}"
    if jogo["penaltis"]:
        p = jogo["penaltis"] if em_casa else jogo["penaltis"][::-1]
        texto += f" ({p[0]} a {p[1]} nos pênaltis)"
    return texto


def _confronto_copa(fase, rodada, adversario, mando):
    onde = "em casa" if mando == "casa" else "fora"
    return (f"Em {_FASE[fase]}, no meio da semana depois da rodada {rodada}, "
            f"pegamos o {adversario}, {onde}.")


def copa_classificacao(situacao, rodada, premio_total):
    """Início da temporada: entramos na copa ou não. `situacao` vem de
    `copa_service.situacao`."""
    if situacao["estado"] == "fora":
        return _mensagem(
            "Diretoria", "Fora da copa",
            "Não estamos entre os 8 da liga que disputam a copa contra a "
            "outra liga nesta temporada. Uma boa campanha agora garante a "
            "vaga na próxima.",
        )
    jogo = situacao["jogo"]
    return _mensagem(
        "Diretoria", "Estamos na copa",
        "Vamos disputar a copa entre as ligas: mata-mata em jogo único, com "
        "pênaltis no empate. "
        + _confronto_copa(situacao["fase"], rodada, jogo["adversario"], jogo["mando"])
        + f" Cada vitória rende prêmio; o campeão leva {_dinheiro(premio_total)}.",
    )


def copa_resultado(fase, jogo, clube, premio, proxima=None):
    """O jogo do técnico numa fase da copa. `proxima`: (fase, rodada,
    adversário, mando) quando passou e ainda há fase."""
    adversario = jogo["visitante"] if jogo["mandante"] == clube else jogo["mandante"]
    placar = _placar_copa(jogo, clube)
    if jogo["vencedor"] != clube:
        return _mensagem(
            "Diretoria", "Fora da copa",
            f"Caímos {_NA_FASE[fase]} da copa: {placar} para o {adversario}. "
            "Agora é a liga.",
        )
    if fase == "final":
        return _mensagem(
            "Diretoria", "Campeões da copa!",
            f"Vencemos o {adversario} por {placar} na final: a copa é nossa! "
            f"O título rendeu mais {_dinheiro(premio)} de prêmio.",
        )
    corpo = (f"Passamos do {adversario} por {placar} {_NA_FASE[fase]} da copa "
             f"(prêmio de {_dinheiro(premio)}).")
    if proxima:
        corpo += " " + _confronto_copa(*proxima)
    return _mensagem("Diretoria", "Avançamos na copa", corpo)
