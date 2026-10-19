"""Papel no elenco (v1.7).

Cada jogador do clube do técnico tem um papel prometido — titular, rotação,
promessa ou reserva — e cobra o tempo de jogo que ele promete:

- titular: começar >= 50% dos jogos; rotação: entrar em >= 30%; promessa
  (até 21 anos): entrar em >= 20%; reserva: sem exigência.
- conta só a liga (a copa é isolada) e só os jogos em que ele estava
  disponível (lesionado ou suspenso não reclama).
- a cada 5 rodadas, a partir da 10, o humor anda um passo: abaixo da meta,
  contente → incomodado → quer sair; na meta, volta um passo.
- quem quer sair se põe na lista de transferências e não renova.
- rebaixar o papel incomoda na hora; promover deixa contente.
- papel e humor são do clube: quem sai começa do zero no próximo
  (`mercado.tirar_do_elenco`, `livres.ficar_livre`).

Sem `random`: não mexe na sorte da temporada. Os clubes da CPU não usam.
"""


TITULAR, ROTACAO, PROMESSA, RESERVA = "titular", "rotacao", "promessa", "reserva"
PAPEIS = (TITULAR, ROTACAO, PROMESSA, RESERVA)
NIVEL = {TITULAR: 3, ROTACAO: 2, PROMESSA: 1, RESERVA: 0}

# papel -> (o que conta, fração mínima dos jogos em que estava disponível)
# calibrado com o motor escalando sozinho: o rodízio por cansaço deixa um
# titular de verdade entre 55% e 90%; com 60% / 40%, 2 ou 3 reclamavam à toa
META = {TITULAR: ("titular", 0.50), ROTACAO: ("jogou", 0.30), PROMESSA: ("jogou", 0.20)}

IDADE_PROMESSA = 21
MARGEM_PROMESSA = 8      # potencial - overall para a distribuição chamar de promessa
VAGAS_ROTACAO = 6

PRIMEIRA_CHECAGEM = 10
INTERVALO_CHECAGEM = 5
MINIMO_DE_JOGOS = 5      # com menos jogos disponível, ainda não dá para cobrar

CONTENTE, INCOMODADO, QUER_SAIR = "contente", "incomodado", "quer_sair"
HUMORES = (CONTENTE, INCOMODADO, QUER_SAIR)


class PapelInvalido(ValueError):
    """O papel não existe ou não cabe no jogador (promessa só até 21)."""


def _sugerido(clube, jogador, xi):
    if jogador in xi and sum(1 for j in clube.jogadores if j.papel == TITULAR) < 11:
        return TITULAR
    if jogador.idade <= IDADE_PROMESSA and jogador.potencial - jogador.overall >= MARGEM_PROMESSA:
        return PROMESSA
    # goleiro reserva quase nunca entra: não vai para a rotação
    if jogador.posicao != "Goleiro" and sum(
        1 for j in clube.jogadores if j.papel == ROTACAO
    ) < VAGAS_ROTACAO:
        return ROTACAO
    return RESERVA


def completar(clube):
    """Dá papel a quem ainda não tem (todos, na primeira vez; depois, quem
    chega), dos melhores para os piores. Titular é quem o motor escalaria
    agora (`Clube.escalar_time` é determinístico; a partida escala de novo)."""
    sem = [j for j in clube.jogadores if j.papel is None]
    if not sem:
        return
    clube.escalar_time()
    xi = set(clube.titulares)
    for jogador in sorted(sem, key=lambda j: (-j.overall, j.nome)):
        jogador.papel = _sugerido(clube, jogador, xi)


def motivo_papel_bloqueado(jogador, papel):
    if papel not in PAPEIS:
        return f"Papel desconhecido: {papel}"
    if papel == PROMESSA and jogador.idade > IDADE_PROMESSA:
        return f"Promessa é só até {IDADE_PROMESSA} anos"
    return None


def definir(jogador, papel):
    """O técnico muda o papel: rebaixar incomoda, promover deixa contente."""
    motivo = motivo_papel_bloqueado(jogador, papel)
    if motivo:
        raise PapelInvalido(motivo)
    antigo = jogador.papel
    jogador.papel = papel
    if antigo is None or NIVEL[papel] == NIVEL[antigo]:
        return
    if NIVEL[papel] > NIVEL[antigo]:
        jogador.humor = CONTENTE
    elif jogador.humor == CONTENTE:
        jogador.humor = INCOMODADO


def contar_disponiveis(clube):
    """Antes do jogo do clube na liga: quem pode jogar ganha um jogo na conta."""
    for jogador in clube.jogadores:
        if not (jogador.lesionado or jogador.suspenso):
            jogador.jogos_disponivel += 1


def aproveitamento(jogador):
    """Fração cumprida da meta do papel (None sem meta ou sem jogos)."""
    meta = META.get(jogador.papel)
    if meta is None or jogador.jogos_disponivel == 0:
        return None
    feito = jogador.titularidades if meta[0] == "titular" else jogador.partidas
    return feito / jogador.jogos_disponivel


def eh_checagem(rodada):
    return rodada >= PRIMEIRA_CHECAGEM and (rodada - PRIMEIRA_CHECAGEM) % INTERVALO_CHECAGEM == 0


def checar(clube):
    """Anda o humor de cada um um passo (depois da rodada de checagem). Quem
    passa a querer sair vai para a lista de transferências."""
    for jogador in clube.jogadores:
        fracao = aproveitamento(jogador)
        if fracao is None or jogador.jogos_disponivel < MINIMO_DE_JOGOS:
            continue
        i = HUMORES.index(jogador.humor)
        if fracao < META[jogador.papel][1]:
            jogador.humor = HUMORES[min(i + 1, len(HUMORES) - 1)]
        else:
            jogador.humor = HUMORES[max(i - 1, 0)]
        if jogador.humor == QUER_SAIR:
            jogador.a_venda = True

