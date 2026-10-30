"""Calendário (v2.0): ver o dia, avançar um dia ou continuar até o próximo
evento. As datas ficam em `app.domain.calendario`.

Passar dias não mexe no estado do jogo (nem no RNG): só anda a data gravada
na simulação. O dia do jogo é o limite — dele em diante, só jogando a
rodada (`temporada_service.avancar`, que leva o calendário até ele).
"""

from datetime import timedelta

from app.db.conexao import conectar
from app.domain import calendario, mercado
from app.repositories import simulacao_repository as simulacao_repo
from app.services import olheiro_base_service, relatorio_service
from app.services.temporada_service import TemporadaConcluida, exigir_sem_transmissao


def visao(sim):
    """O calendário de uma simulação (linha da tabela). Temporada concluída:
    o dia da última rodada."""
    temporada = sim["temporada"]
    concluida = sim["estado"] != "em_andamento"
    rodada = sim["rodadas"] if concluida else sim["rodada_atual"]
    na_copa = not concluida and bool(sim["copa_pendente"])
    hoje = (calendario.data_da_rodada(temporada, rodada) if concluida
            else calendario.data_atual(temporada, rodada, sim["data_atual"]))
    jogo = calendario.data_do_jogo(temporada, rodada, na_copa)
    return {
        "temporada": calendario.nome_da_temporada(temporada),
        "data": hoje.isoformat(),
        "data_fmt": calendario.formatar(hoje),
        "periodo": ("concluida" if concluida
                    else calendario.periodo(hoje, temporada, rodada, na_copa)),
        "rodada": None if concluida else rodada,
        # o próximo jogo é o da copa, na quarta (v2.0)
        "copa": na_copa,
        "data_do_jogo": None if concluida else jogo.isoformat(),
        "dias_ate_o_jogo": None if concluida else (jogo - hoje).days,
        "janela_aberta": not concluida and mercado.janela_aberta(rodada),
    }


def _carregar(conn, simulacao_id):
    sim = simulacao_repo.buscar(conn, simulacao_id)
    if sim is None:
        return None
    if sim["estado"] != "em_andamento":
        raise TemporadaConcluida("Esta temporada já foi concluída")
    exigir_sem_transmissao(sim)
    return sim


def ver(simulacao_id):
    conn = conectar()
    try:
        sim = simulacao_repo.buscar(conn, simulacao_id)
        return visao(sim) if sim else None
    finally:
        conn.close()


def _andar(simulacao_id, proximo):
    """Grava o dia `proximo(conn, simulacao_id, hoje, dia_do_jogo)`, entrega o que
    ficou pronto até ele e devolve a visão (com `chegou_mensagem`)."""
    conn = conectar()
    try:
        sim = _carregar(conn, simulacao_id)
        if sim is None:
            return None
        temporada, rodada = sim["temporada"], sim["rodada_atual"]
        na_copa = bool(sim["copa_pendente"])
        hoje = calendario.data_atual(temporada, rodada, sim["data_atual"])
        dia = proximo(conn, simulacao_id, hoje, calendario.data_do_jogo(temporada, rodada, na_copa))
        with conn:
            simulacao_repo.definir_data(conn, simulacao_id, dia)
            # relatórios do olheiro que ficaram prontos no caminho (v2.0)
            prontos = relatorio_service.entregar(conn, simulacao_id, dia, rodada)
            # e os relatórios mensais dos olheiros da base
            prontos += olheiro_base_service.entregar(conn, simulacao_id, dia, rodada)
        # a tela passa os dias um a um e para quando chega mensagem
        return {**visao(simulacao_repo.buscar(conn, simulacao_id)),
                "chegou_mensagem": bool(prontos)}
    finally:
        conn.close()


def avancar_dia(simulacao_id):
    """Um dia a mais (sem passar do dia do jogo)."""
    return _andar(
        simulacao_id,
        lambda conn, sid, hoje, jogo: min(hoje + timedelta(days=1), max(hoje, jogo)),
    )


def _proximo_evento(conn, simulacao_id, hoje, jogo):
    """O dia do próximo jogo, ou antes, o de um relatório que fica pronto
    (de contratação ou de um olheiro da base)."""
    jogo = max(hoje, jogo)
    relatorios = (relatorio_service.proximo_pronto(conn, simulacao_id),
                  olheiro_base_service.proximo_relatorio(conn, simulacao_id))
    return min([jogo] + [r for r in relatorios if r and r > hoje])


def continuar(simulacao_id):
    """Até o próximo evento: o dia do jogo ou um relatório pronto."""
    return _andar(simulacao_id, _proximo_evento)
