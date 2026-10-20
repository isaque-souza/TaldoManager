"""Calendário (v2.0): ver o dia, avançar um dia ou continuar até o próximo
evento. As datas ficam em `app.domain.calendario`.

Passar dias não mexe no estado do jogo (nem no RNG): só anda a data gravada
na simulação. O dia do jogo é o limite — dele em diante, só jogando a
rodada (`temporada_service.avancar`, que leva o calendário até ele).
"""

from app.db.conexao import conectar
from app.domain import calendario, mercado
from app.repositories import simulacao_repository as simulacao_repo
from app.services.temporada_service import TemporadaConcluida, exigir_sem_transmissao


def visao(sim):
    """O calendário de uma simulação (linha da tabela). Temporada concluída:
    o dia da última rodada."""
    temporada = sim["temporada"]
    concluida = sim["estado"] != "em_andamento"
    rodada = sim["rodadas"] if concluida else sim["rodada_atual"]
    hoje = (calendario.data_da_rodada(temporada, rodada) if concluida
            else calendario.data_atual(temporada, rodada, sim["data_atual"]))
    jogo = calendario.data_da_rodada(temporada, rodada)
    return {
        "temporada": calendario.nome_da_temporada(temporada),
        "data": hoje.isoformat(),
        "data_fmt": calendario.formatar(hoje),
        "periodo": "concluida" if concluida else calendario.periodo(hoje, temporada, rodada),
        "rodada": None if concluida else rodada,
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
    """Grava o dia `proximo(hoje, temporada, rodada)` e devolve a visão."""
    conn = conectar()
    try:
        sim = _carregar(conn, simulacao_id)
        if sim is None:
            return None
        temporada, rodada = sim["temporada"], sim["rodada_atual"]
        hoje = calendario.data_atual(temporada, rodada, sim["data_atual"])
        with conn:
            simulacao_repo.definir_data(conn, simulacao_id, proximo(hoje, temporada, rodada))
        return visao(simulacao_repo.buscar(conn, simulacao_id))
    finally:
        conn.close()


def avancar_dia(simulacao_id):
    """Um dia a mais (sem passar do dia do jogo)."""
    return _andar(simulacao_id, calendario.avancar_um_dia)


def continuar(simulacao_id):
    """Até o próximo evento — por enquanto, o dia do próximo jogo."""
    return _andar(
        simulacao_id,
        lambda hoje, temporada, rodada: max(hoje, calendario.data_da_rodada(temporada, rodada)),
    )
