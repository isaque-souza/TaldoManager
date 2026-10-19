"""Papel no elenco (v1.7) de ponta a ponta: rodadas, banco, caixa e virada."""

import json

from app.db.conexao import conectar
from app.domain import papeis
from app.domain.temporada import restaurar_estado
from app.repositories import jogador_repository as jogador_repo
from app.repositories import mensagem_repository as mensagem_repo
from app.repositories import simulacao_repository as simulacao_repo
from app.services import carreira_service, temporada_service
from scripts.data_loader import carregar_campeonato_do_save

CLUBE = "Real Taldo"


def _alvo(sid):
    conn = conectar()
    try:
        sim = simulacao_repo.buscar(conn, sid)
    finally:
        conn.close()
    campeonato = carregar_campeonato_do_save(sim)
    restaurar_estado(campeonato, json.loads(sim["estado_json"]))
    return next(c for c in campeonato.clubes if c.nome == CLUBE)


def _assuntos(sid):
    conn = conectar()
    try:
        return [m["assunto"] for m in mensagem_repo.listar(conn, sid)]
    finally:
        conn.close()


def test_papeis_sao_distribuidos_e_gravados_na_primeira_rodada():
    sid = temporada_service.iniciar(seed=3, clube_usuario=CLUBE)
    temporada_service.avancar(sid)

    alvo = _alvo(sid)
    assert all(j.papel in papeis.PAPEIS for j in alvo.jogadores)
    assert sum(1 for j in alvo.jogadores if j.papel == papeis.TITULAR) == 11
    assert all(j.jogos_disponivel == 1 for j in alvo.jogadores if not j.lesionado)
    titulares = [j for j in alvo.jogadores if j.titularidades == 1]
    assert len(titulares) == 11

    conn = conectar()
    try:
        linhas = [r for r in jogador_repo.listar_por_simulacao(conn, sid) if r["clube"] == CLUBE]
    finally:
        conn.close()
    assert all(r["papel"] for r in linhas) and all(r["humor"] == "contente" for r in linhas)


def test_titular_fora_do_time_fica_incomodado_e_depois_quer_sair():
    sid = temporada_service.iniciar(seed=3, clube_usuario=CLUBE)
    temporada_service.avancar(sid)
    alvo = _alvo(sid)
    # o goleiro titular vai para o banco (goleiro não entra por rodízio): o
    # técnico escala o reserva e os 10 melhores da linha
    encostado = next(
        j for j in alvo.jogadores if j.papel == papeis.TITULAR and j.posicao == "Goleiro"
    )
    reserva = max(
        (j for j in alvo.jogadores if j.posicao == "Goleiro" and j is not encostado),
        key=lambda j: j.overall,
    )
    linha = sorted((j for j in alvo.jogadores if j.posicao != "Goleiro"), key=lambda j: -j.overall)
    xi = [reserva.nome] + [j.nome for j in linha[:10]]

    for _ in range(9):   # até a rodada 10, a primeira checagem
        temporada_service.avancar(sid, xi_preferido=xi)
    j = next(x for x in _alvo(sid).jogadores if x.nome == encostado.nome)
    assert j.humor == papeis.INCOMODADO
    assert f"{j.nome} está incomodado" in _assuntos(sid)

    for _ in range(5):   # rodada 15
        temporada_service.avancar(sid, xi_preferido=xi)
    j = next(x for x in _alvo(sid).jogadores if x.nome == encostado.nome)
    assert j.humor == papeis.QUER_SAIR and j.a_venda
    assert f"{j.nome} quer sair" in _assuntos(sid)


def test_papel_e_humor_seguem_na_virada_e_os_contadores_zeram():
    sid = temporada_service.iniciar(seed=5, clube_usuario=CLUBE)
    while temporada_service.avancar(sid)["concluida"] is False:
        pass
    conn = conectar()
    try:
        finais = {
            r["nome"]: r for r in jogador_repo.listar_por_simulacao(conn, sid)
            if r["clube"] == CLUBE
        }
    finally:
        conn.close()

    nova = carreira_service.proxima_temporada(sid)["simulacao_id"]
    temporada_service.avancar(nova)
    for j in _alvo(nova).jogadores:
        if j.nome in finais:
            assert j.papel == finais[j.nome]["papel"]
            assert j.jogos_disponivel <= 1 and j.titularidades <= 1
