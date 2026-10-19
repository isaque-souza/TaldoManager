"""Jogadores observados pelo técnico (v1.7): uma lista de até 25 nomes, de
qualquer clube das duas ligas ou livres, que segue de temporada em
temporada. Vai pelo nome (livres não têm id, e os ids mudam a cada
temporada) e guarda como o jogador estava quando entrou na lista, para a
tela mostrar o que mudou desde então.

Ver e mexer na lista não depende da janela: fora dela o técnico observa,
só não negocia.
"""

from app.db.conexao import conectar
from app.domain.mercado import TransferenciaInvalida
from app.repositories import observado_repository as observado_repo
from app.services.mercado_service import (
    _carregar, _ficha, _ficha_de_compra, _ficha_de_livre, _Janela,
)

LIMITE = 25


def _onde_esta(ctx, nome):
    """(jogador, clube) — clube None se está livre; (None, None) se não
    está mais no jogo (aposentou)."""
    for clube in ctx.campeonato.clubes:
        for j in clube.jogadores:
            if j.nome == nome:
                return j, clube
    for j in ctx.campeonato.livres:
        if j.nome == nome:
            return j, None
    return None, None


def _avisos(antes, jogador, clube, alvo):
    """O que mudou desde que ele entrou na lista, além dos números."""
    if jogador is None:
        return ["Aposentou"]
    if clube is alvo:
        return ["Já é do seu elenco"]
    agora = clube.nome if clube else None
    if agora == antes:
        return []
    if agora is None:
        return [f"Ficou sem clube (estava no {antes})"]
    if antes is None:
        return [f"Assinou com o {agora}"]
    return [f"Mudou de clube: {antes} → {agora}"]


def ver(simulacao_id):
    """A lista, cada um com a situação de agora (clube, livre, no seu elenco
    ou aposentado), o overall e o valor de quando entrou, os avisos e a
    ficha de compra (None para quem se aposentou). None se a simulação não
    existe."""

    conn = conectar()
    try:
        ctx = _carregar(conn, simulacao_id)
        if ctx is None:
            return None
        janela = _Janela(ctx)

        observados = []
        for r in observado_repo.listar(conn, simulacao_id):
            jogador, clube = _onde_esta(ctx, r["nome"])
            if jogador is None:
                situacao, ficha = "aposentado", None
            elif clube is ctx.alvo:
                situacao = "no_elenco"
                ficha = {
                    **_ficha(jogador, janela.ids[jogador.nome], clube),
                    "bloqueio": f"{jogador.nome} já é do seu elenco",
                    "observado": True,
                }
            elif clube is None:
                situacao, ficha = "livre", _ficha_de_livre(ctx, janela, jogador)
            else:
                situacao, ficha = "clube", _ficha_de_compra(ctx, janela, jogador, clube)
            observados.append({
                "nome": r["nome"],
                "situacao": situacao,
                "desde_temporada": r["temporada"],
                "desde_rodada": r["rodada"],
                "clube_inicial": r["clube"],
                "overall_inicial": r["overall"],
                "valor_inicial": r["valor"],
                "avisos": _avisos(r["clube"], jogador, clube, ctx.alvo),
                "jogador": ficha,
            })
        return {"limite": LIMITE, "observados": observados}
    finally:
        conn.close()


def observar(simulacao_id, nome, observar=True):
    """Põe (ou tira) um jogador da lista. Pôr de novo quem já está não muda
    o "desde". None se a simulação não existe ou, ao pôr, ninguém com esse
    nome está no jogo."""

    conn = conectar()
    try:
        ctx = _carregar(conn, simulacao_id)
        if ctx is None:
            return None
        nomes = {r["nome"] for r in observado_repo.listar(conn, simulacao_id)}

        if not observar:
            with conn:
                observado_repo.remover(conn, simulacao_id, nome)
            nomes.discard(nome)
        elif nome not in nomes:
            jogador, clube = _onde_esta(ctx, nome)
            if jogador is None:
                return None
            if clube is ctx.alvo:
                raise TransferenciaInvalida(f"{nome} já é do seu elenco")
            if len(nomes) >= LIMITE:
                raise TransferenciaInvalida(
                    f"A lista de observados está cheia ({LIMITE}): tire alguém antes"
                )
            with conn:
                observado_repo.inserir(
                    conn, simulacao_id, nome, clube.nome if clube else None,
                    jogador.overall, jogador.valor_mercado(),
                    ctx.sim["temporada"], ctx.rodada,
                )
            nomes.add(nome)

        return {
            "nome": nome,
            "observado": nome in nomes,
            "total": len(nomes),
            "limite": LIMITE,
        }
    finally:
        conn.close()
