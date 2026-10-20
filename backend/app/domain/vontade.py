"""Vontade do jogador (v1.9): de onde ele vem e para onde quer ir.

- PRESTÍGIO do clube (0 a 100): força do elenco e tamanho da torcida, em
  relação aos outros clubes do save. Os títulos entram pela torcida, que
  cresce com as boas campanhas (v1.4).
- CLUBE FORMADOR: onde o jogador começou. Quem sobe da base é formado no
  próprio clube; quem já está na seed tem o formador sorteado pelo nome
  (o clube atual, outro do mesmo país ou qualquer um).
- CLUBE DA HISTÓRIA: o último clube em que ele foi ídolo. Fica com ele
  mesmo depois que sai de lá.
- CLUBE DO SONHO, que muda com a idade:
  - até 30 anos, um dos grandes do país onde foi formado ou um dos
    melhores do mundo (os de mais prestígio);
  - a partir de 31, encerrar a carreira no clube formador ou no da história.
  É recalculado na virada de temporada (`virada`), não a cada rodada:
  comprar um reforço não muda o sonho de ninguém no meio da temporada.

Como a fama, tudo aqui é determinístico (crc32 do nome, nada de `random`):
não mexe na sequência aleatória nem nos resultados de um mesmo seed.
"""

import math
import zlib

from app.domain import diretoria, fama

# prestígio: peso da força do elenco (o resto é a torcida)
PESO_FORCA = 0.6

# formador de quem já está na liga: o clube atual, outro do mesmo país ou
# qualquer um. Jovens (até IDADE_CRIA) são sempre crias do clube atual
CHANCE_CRIA = 40
CHANCE_MESMO_PAIS = 35
IDADE_CRIA = 21

IDADE_APOSENTADORIA = 31     # a partir daqui, sonha em encerrar a carreira
CHANCE_SONHO_NACIONAL = 50   # senão, um dos melhores do mundo
GRANDES_DO_PAIS = 3
MELHORES_DO_MUNDO = 8
CHANCE_VOLTAR_PARA_HISTORIA = 60   # veterano com clube da história


def _sorte(nome, sal):
    """Um número fixo para o jogador (o mesmo em toda execução)."""
    return zlib.crc32(f"{nome}:{sal}".encode("utf-8"))


def _normalizar(valores):
    menor, maior = min(valores.values()), max(valores.values())
    if maior == menor:
        return {nome: 0.5 for nome in valores}
    return {nome: (v - menor) / (maior - menor) for nome, v in valores.items()}


def prestigio(clubes):
    """{nome do clube: prestígio de 0 a 100}."""
    if not clubes:
        return {}
    forca = _normalizar({c.nome: diretoria.forca_do_elenco(c) for c in clubes})
    torcida = _normalizar({c.nome: math.log1p(c.torcedores) for c in clubes})
    return {
        c.nome: round(100 * (PESO_FORCA * forca[c.nome] + (1 - PESO_FORCA) * torcida[c.nome]))
        for c in clubes
    }


def _por_prestigio(clubes, prest):
    return sorted(clubes, key=lambda c: (-prest[c.nome], c.nome))


def _escolher(opcoes, prest, sorte):
    """Um entre `opcoes`, com chance proporcional ao prestígio: o maior sai
    mais vezes, mas sem engolir os outros."""
    pesos = [prest[c.nome] + 1 for c in opcoes]
    alvo = sorte % sum(pesos)
    for opcao, peso in zip(opcoes, pesos):
        if alvo < peso:
            return opcao
        alvo -= peso
    return opcoes[-1]


def formador_inicial(jogador, clube, clubes):
    """O clube formador de quem já está na liga (`clube` None = livre)."""
    ordem = sorted(clubes, key=lambda c: c.nome)
    sorte = _sorte(jogador.nome, "formador")
    faixa = sorte % 100
    if clube is not None:
        if jogador.idade <= IDADE_CRIA or faixa < CHANCE_CRIA:
            return clube.nome
        if faixa < CHANCE_CRIA + CHANCE_MESMO_PAIS:
            mesmo_pais = [c for c in ordem if c.pais == clube.pais and c is not clube]
            if mesmo_pais:
                return mesmo_pais[(sorte // 100) % len(mesmo_pais)].nome
    return ordem[(sorte // 100) % len(ordem)].nome


def sonho(jogador, clubes, prest):
    """O clube do sonho do jogador agora (None sem clubes)."""
    if not clubes:
        return None
    por_nome = {c.nome: c for c in clubes}
    sorte = _sorte(jogador.nome, "sonho")

    if jogador.idade >= IDADE_APOSENTADORIA:
        historia = jogador.clube_historia if jogador.clube_historia in por_nome else None
        formador = jogador.formador if jogador.formador in por_nome else None
        if historia and historia != formador and (
            formador is None or sorte % 100 < CHANCE_VOLTAR_PARA_HISTORIA
        ):
            return historia
        if formador:
            return formador
        if historia:
            return historia

    formador = por_nome.get(jogador.formador)
    nacionais = []
    if formador is not None:
        nacionais = _por_prestigio(
            [c for c in clubes if c.pais == formador.pais], prest
        )[:GRANDES_DO_PAIS]
    if nacionais and sorte % 100 < CHANCE_SONHO_NACIONAL:
        return _escolher(nacionais, prest, sorte // 100).nome
    melhores = _por_prestigio(clubes, prest)[:MELHORES_DO_MUNDO]
    return _escolher(melhores, prest, sorte // 100).nome


def _todos(campeonato):
    """(jogador, clube) de todo mundo, livres com clube None."""
    return [(j, c) for c in campeonato.clubes for j in c.jogadores] + [
        (j, None) for j in campeonato.livres
    ]


def marcar_historia(campeonato):
    """Quem é ídolo do clube onde está passa a ter a história lá."""
    for clube in campeonato.clubes:
        for jogador in fama.idolos(clube):
            jogador.clube_historia = clube.nome


def completar(campeonato):
    """Dá formador e sonho a quem ainda não tem (todos, no começo de um jogo;
    depois, quem vem de um save antigo ou é livre novo). Quem já tem fica
    como está."""
    marcar_historia(campeonato)
    prest = prestigio(campeonato.clubes)
    for jogador, clube in _todos(campeonato):
        if jogador.formador is None:
            jogador.formador = formador_inicial(jogador, clube, campeonato.clubes)
        if jogador.sonho is None:
            jogador.sonho = sonho(jogador, campeonato.clubes, prest)


def virada(campeonato):
    """Na virada de temporada, depois de envelhecer e de a base subir: todo
    mundo revê o sonho (a idade e o prestígio mudaram)."""
    completar(campeonato)
    prest = prestigio(campeonato.clubes)
    for jogador, _ in _todos(campeonato):
        jogador.sonho = sonho(jogador, campeonato.clubes, prest)
