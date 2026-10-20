"""Relatórios de contratação (v2.0): pedir ao olheiro e recebê-los quando o
calendário chega ao dia. As regras ficam em `app.domain.relatorio`; o
conteúdo de um relatório pronto é montado na hora de ler, nas fichas do
mercado (`mercado_service`).

`entregar` é chamado por quem anda com o calendário (`calendario_service`
e `temporada_service.avancar`), dentro da transação dele.
"""

from datetime import date, timedelta

from app.db.conexao import conectar
from app.domain import caixa, calendario, relatorio
from app.repositories import mensagem_repository as mensagem_repo
from app.repositories import observado_repository as observado_repo
from app.repositories import relatorio_repository as relatorio_repo


class PedidoInvalido(ValueError):
    """Jogador fora dos observados, já com relatório, do próprio clube ou o
    olheiro sem vaga."""


def entregar(conn, simulacao_id, dia, rodada):
    """Marca os relatórios prontos até `dia` (date) e manda a mensagem do
    olheiro. Devolve os nomes."""
    nomes = relatorio_repo.marcar_prontos(conn, simulacao_id, dia.isoformat())
    if nomes:
        mensagem_repo.inserir(conn, simulacao_id, rodada, [caixa.relatorios_prontos(nomes)])
    return nomes


def proximo_pronto(conn, simulacao_id):
    """O dia (date) em que o próximo relatório fica pronto, ou None."""
    dia = relatorio_repo.proximo_pronto(conn, simulacao_id)
    return date.fromisoformat(dia) if dia else None


def em_andamento(conn, simulacao_id):
    return sum(1 for r in relatorio_repo.listar(conn, simulacao_id) if not r["pronto"])


def pedir(simulacao_id, nome):
    """Pede o relatório sobre `nome` (um observado). Devolve
    {nome, pronto_em}; None se a simulação não existe; `PedidoInvalido` se
    não dá."""
    # aqui: o mercado importa o temporada_service, que importa este módulo
    from app.services.mercado_service import _carregar
    from app.services.observado_service import _onde_esta

    conn = conectar()
    try:
        ctx = _carregar(conn, simulacao_id)
        if ctx is None:
            return None
        sid, alvo = ctx.sim["id"], ctx.alvo
        if nome not in {r["nome"] for r in observado_repo.listar(conn, sid)}:
            raise PedidoInvalido("Só dá para pedir relatório de quem você observa")
        jogador, clube = _onde_esta(ctx, nome)
        if jogador is None:
            raise PedidoInvalido(f"{nome} não está mais no futebol")
        if clube is alvo:
            raise PedidoInvalido(f"{nome} já é do seu elenco")
        if nome in {r["nome"] for r in relatorio_repo.listar(conn, sid)}:
            raise PedidoInvalido(f"O olheiro já fez (ou está fazendo) o relatório de {nome}")
        nivel = alvo.nivel_olheiro
        if em_andamento(conn, sid) >= relatorio.limite(nivel):
            raise PedidoInvalido(
                f"O olheiro de nível {nivel} faz {relatorio.limite(nivel)} relatório(s) por vez"
            )

        hoje = calendario.data_atual(ctx.sim["temporada"], ctx.rodada, ctx.sim["data_atual"])
        pronto = hoje + timedelta(days=relatorio.DIAS[nivel])
        with conn:
            relatorio_repo.inserir(conn, sid, nome, hoje.isoformat(), pronto.isoformat())
        return {"nome": nome, "pronto_em": pronto.isoformat()}
    finally:
        conn.close()
