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
- INTERESSE em vir para um clube (`interesse`): prestígio, papel, sonho,
  ídolo, rivalidade viram pontos; os pontos viram um fator no salário que
  ele pede (`contrato.salario_pedido_chegada`). Bloqueia só o ídolo que
  iria para o rival do clube onde fez história.

Como a fama, tudo aqui é determinístico (crc32 do nome, nada de `random`):
não mexe na sequência aleatória nem nos resultados de um mesmo seed.
"""

import math
import zlib
from dataclasses import dataclass

from app.domain import contrato, diretoria, fama, mercado, papeis

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


# ---------------------------------------------------------------------------
# interesse em vir (passo 2)
# ---------------------------------------------------------------------------
#
# Uma pontuação do quanto o jogador quer vir para o `comprador`: prestígio
# comparado com o clube atual, o papel que teria, o sonho, se é ídolo onde
# está, rivalidade. Ela vira um fator no salário que ele pede (cada ponto,
# 8%) e um selo na tela. Bloqueia só um caso: o clube da história dele é
# rival do comprador ("um ídolo do Real não joga no Barça").

PONTOS_POR_PRESTIGIO = 15   # cada 15 pontos de diferença vale 1 ponto
LIMITE_PRESTIGIO = 3
PRESTIGIO_LIVRE = 50        # quem está livre compara com um clube médio
FATOR_POR_PONTO = 0.08
FATOR_MIN, FATOR_MAX = 0.85, 1.5
PONTOS_NEUTROS = 1          # "aberto" com 1 ponto pede o normal

QUER_VIR, ABERTO, RESISTENTE, NAO_VEM = "quer_vir", "aberto", "resistente", "nao_vem"


@dataclass
class Interesse:
    pontos: int
    nivel: str
    fator: float          # no salário pedido
    motivos: list         # textos curtos, do mais forte ao mais fraco
    bloqueio: str | None  # só com NAO_VEM


def _rivais(a, b):
    return b.nome in a.rivais or a.nome in b.rivais


def motivo_nao_vem(jogador, comprador, clubes):
    """Por que ele não joga no `comprador` de jeito nenhum (None = joga)."""
    historia = next((c for c in clubes if c.nome == jogador.clube_historia), None)
    if historia is not None and historia is not comprador and _rivais(historia, comprador):
        return f"Ídolo do {historia.nome}: não joga no rival"
    return None


def interesse(jogador, comprador, vendedor, clubes, prest=None):
    """O `Interesse` do jogador em sair do `vendedor` (None = está livre)
    para o `comprador`. `prest`: o `prestigio(clubes)`, se já calculado."""
    prest = prest if prest is not None else prestigio(clubes)
    motivos = []   # (peso, texto)

    atual = prest[vendedor.nome] if vendedor is not None else PRESTIGIO_LIVRE
    diferenca = prest[comprador.nome] - atual
    p_prestigio = max(-LIMITE_PRESTIGIO, min(LIMITE_PRESTIGIO, int(diferenca / PONTOS_POR_PRESTIGIO)))
    if p_prestigio > 0:
        motivos.append((p_prestigio, "clube de mais prestígio"))
    elif p_prestigio < 0:
        motivos.append((p_prestigio, "o clube atual tem mais prestígio"))

    if mercado.seria_titular(comprador, jogador):
        motivos.append((1, "seria titular"))
    elif contrato.papel_esperado(comprador, jogador) == papeis.RESERVA:
        motivos.append((-1, "seria reserva"))

    if vendedor is None:
        motivos.append((1, "quer voltar a jogar"))
    else:
        if not mercado.seria_titular(vendedor, jogador):
            motivos.append((1, "está no banco onde está"))
        if fama.idolo(jogador):
            motivos.append((-1, f"é ídolo do {vendedor.nome}"))
        if _rivais(vendedor, comprador):
            motivos.append((-1, "seria ir para o rival"))
        if jogador.sonho == vendedor.nome:
            motivos.append((-2, "já está no clube do sonho"))
    if jogador.sonho == comprador.nome:
        motivos.append((2, "é o clube do sonho"))

    pontos = sum(p for p, _ in motivos)
    textos = [t for _, t in sorted(motivos, key=lambda m: -abs(m[0]))]
    fator = max(FATOR_MIN, min(FATOR_MAX, 1 - FATOR_POR_PONTO * (pontos - PONTOS_NEUTROS)))

    bloqueio = motivo_nao_vem(jogador, comprador, clubes)
    if bloqueio:
        nivel = NAO_VEM
    elif pontos >= 3:
        nivel = QUER_VIR
    elif pontos >= 1:
        nivel = ABERTO
    else:
        nivel = RESISTENTE
    return Interesse(pontos, nivel, round(fator, 2), textos, bloqueio)


# ---------------------------------------------------------------------------
# vontade no clube (passo 4)
# ---------------------------------------------------------------------------

def no_clube_do_sonho(jogador, clube):
    return clube is not None and jogador.sonho == clube.nome


def quer_encerrar_fora(jogador, clube):
    """Veterano que sonha encerrar a carreira em outro clube."""
    return (
        jogador.idade >= IDADE_APOSENTADORIA
        and jogador.sonho is not None
        and not no_clube_do_sonho(jogador, clube)
    )


def recusou_o_sonho(jogador):
    """O técnico não vendeu o jogador ao clube do sonho dele: o humor piora
    um passo (quem passa a querer sair vai para a lista, como em
    `papeis.checar`). Devolve True se piorou."""
    i = papeis.HUMORES.index(jogador.humor)
    if i == len(papeis.HUMORES) - 1:
        return False
    jogador.humor = papeis.HUMORES[i + 1]
    if jogador.humor == papeis.QUER_SAIR and not jogador.emprestimo:
        jogador.a_venda = True
    return True
