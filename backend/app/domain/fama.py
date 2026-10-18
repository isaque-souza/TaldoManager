"""Fama dos jogadores e ídolos (v1.4).

A fama vai de 0 a 100 e é do jogador, não do clube: vem com ele numa
transferência. No fim de cada temporada ela é recalculada pelo que ele fez
— gols, assistências, prêmios de melhor em campo, jogos sem sofrer gol,
título — e parte da fama antiga se apaga, então quem some do time é
esquecido aos poucos.

Ídolo é quem tem fama alta E história no clube (algumas temporadas
seguidas lá). O tempo de casa zera quando o jogador muda de clube; a fama,
não. Um ídolo atrai torcida, vale mais no mercado, e vendê-lo revolta a
torcida (ver `app.domain.torcida`).

Como a torcida, tudo aqui é determinístico: nada de `random`, para não
mexer na sequência aleatória e nos resultados de um mesmo seed.

As constantes ficam juntas para facilitar o balanceamento.
"""

import zlib

FAMA_MAX = 100
RETENCAO = 0.78  # fração da fama que passa para a temporada seguinte

# pontos por temporada; no longo prazo a fama tende a pontos / (1 − RETENCAO).
# Calibrado em 12 temporadas: a liga fica com uns 15 ídolos (até 3 por clube)
# e só o artilheiro de anos seguidos encosta em 100. Com 0,6 por gol eram 30
# ídolos e meia dúzia de atacantes travados em 100
POR_GOL = 0.5
POR_ASSISTENCIA = 0.35
POR_MELHOR_EM_CAMPO = 0.6
POR_CLEAN_SHEET = 0.4      # só goleiro: é a "artilharia" dele
POR_PARTIDA = 0.1
CAMPEAO = 5
JOGOS_PARA_TITULO = 10     # quem quase não jogou não leva a fama do título

LIMIAR_IDOLO = 60
TEMPORADAS_IDOLO = 3       # temporadas completas no clube

# efeitos: no valor de mercado, no preço para tirar do clube, na torcida
VALOR_POR_FAMA = 0.003     # fama 100 → vale 30% a mais
FATOR_IDOLO = 1.3          # o clube cobra mais para liberar o ídolo
TORCIDA_POR_IDOLO = 0.005  # no fim da temporada, por ídolo no elenco
MAX_IDOLOS_TORCIDA = 3


def inicial(nome, idade, overall):
    """(fama, temporadas no clube) de quem já está na liga no começo da
    carreira: craques veteranos começam famosos. O tempo de casa sai do
    nome (crc32, o mesmo em toda execução — `hash` muda a cada processo),
    limitado pelo que a idade permite."""
    fama = (overall - 70) * 2.5 + max(0, idade - 22) * 1.5
    teto = min(8, max(0, idade - 19) // 2)
    temporadas = zlib.crc32(nome.encode("utf-8")) % (teto + 1)
    return _limitar(fama), temporadas


def _limitar(fama):
    return int(round(min(FAMA_MAX, max(0, fama))))


def eh_idolo(fama, temporadas_no_clube):
    return fama >= LIMIAR_IDOLO and temporadas_no_clube >= TEMPORADAS_IDOLO


def idolo(jogador):
    return eh_idolo(jogador.fama, jogador.temporadas_no_clube)


def idolos(clube):
    return [j for j in clube.jogadores if idolo(j)]


def pontos_da_temporada(jogador, campeao=False):
    pontos = (
        POR_GOL * jogador.gols
        + POR_ASSISTENCIA * jogador.assistencias
        + POR_MELHOR_EM_CAMPO * jogador.melhor_em_campo
        + POR_PARTIDA * jogador.partidas
    )
    if jogador.posicao == "Goleiro":
        pontos += POR_CLEAN_SHEET * jogador.clean_sheets
    if campeao and jogador.partidas >= JOGOS_PARA_TITULO:
        pontos += CAMPEAO
    return pontos


def fim_de_temporada(classificacao):
    """Recalcula a fama de todo mundo e soma uma temporada de casa. Chamar
    antes de `torcida.fim_de_temporada`: os ídolos novos já atraem gente."""
    for posicao, clube in enumerate(classificacao, start=1):
        for jogador in clube.jogadores:
            jogador.fama = _limitar(
                jogador.fama * RETENCAO
                + pontos_da_temporada(jogador, campeao=posicao == 1)
            )
            jogador.temporadas_no_clube += 1


def fator_valor(fama):
    return 1 + VALOR_POR_FAMA * fama


def bonus_torcida(clube):
    """Fração que a torcida ganha no fim da temporada pelos ídolos."""
    return TORCIDA_POR_IDOLO * min(MAX_IDOLOS_TORCIDA, len(idolos(clube)))
