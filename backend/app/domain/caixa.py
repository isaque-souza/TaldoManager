"""Caixa de entrada do técnico (v1.3): mensagens de cada setor do clube.

Como no Football Manager e no modo carreira do FIFA, quem trabalha no clube
avisa o técnico do que aconteceu: o diretor de futebol responde as
propostas (e diz o que faltou), o departamento médico fala das lesões, o
auxiliar técnico das suspensões e do cansaço, a diretoria da meta.

Aqui só se montam as mensagens (dicts com setor, assunto e corpo), a
partir de fatos que os serviços já têm; quem grava é o
`mensagem_repository`. Nada aqui sorteia.
"""

from app.domain import mercado
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
    if abs(valor) >= 1_000_000:
        return f"R$ {valor / 1_000_000:.1f} mi".replace(".", ",")
    return f"R$ {round(valor / 1_000)} mil"


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
    if resposta.tipo == "multa":
        return _mensagem(
            "Diretor de futebol", f"Contratado: {jogador.nome}",
            f"Pagamos a multa rescisória de {_dinheiro(resposta.valor)} e o "
            f"{vendedor.nome} não pôde recusar. {alvo} já é do nosso elenco.",
        )
    if resposta.tipo == "aceita":
        return _mensagem(
            "Diretor de futebol", f"Contratado: {jogador.nome}",
            f"O {vendedor.nome} aceitou os {_dinheiro(valor)}. {alvo} já é do "
            "nosso elenco.",
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


def negociacao_bloqueada(jogador, vendedor, motivo, caixa=None):
    """Nem deu para negociar (caixa, elenco cheio, o vendedor não pode
    liberar...): o motivo é o que faltou. Com `caixa`, diz quanto temos."""
    temos = f" Hoje temos {_dinheiro(caixa)} em caixa." if caixa is not None else ""
    return _mensagem(
        "Diretor de futebol", f"Não deu para negociar {jogador.nome}",
        f"Tentamos {jogador.nome}, do {vendedor.nome}, mas não deu: {motivo}.{temos}",
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
