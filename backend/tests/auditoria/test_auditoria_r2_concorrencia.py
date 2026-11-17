"""Auditoria 01 — R2: nada impede dois pedidos de processar o mesmo turno.

`temporada_service.avancar` lê o save, simula fora de transação e grava com
`UPDATE simulacao ... WHERE id = ?`, sem conferir a rodada lida; `partida`
não tem UNIQUE. `carreira_service.proxima_temporada` confere `sucessora()`
antes da transação de escrita.

Roteiro (fixo, sem depender da sorte):
- os dois fios leem o mesmo save antes de qualquer gravação (uma barreira
  logo antes do bloco de escrita);
- a simulação dos dois roda um de cada vez (uma trava em volta dela), para
  o R1 não se misturar ao que se mede aqui;
- depois da barreira, os dois gravam como gravariam em produção.

Os testes afirmam o comportamento correto e estão em `xfail(strict=True)`
enquanto o defeito existir. Detalhes: `pytest tests/auditoria --runxfail`.
"""

import threading

import pytest

from app.db.conexao import conectar
from app.repositories import carreira_repository as carreira_repo
from app.repositories import simulacao_repository as simulacao_repo
from app.services import carreira_service, simulacao_service, temporada_service
from tests.auditoria.roteiro import ESPERA, Fio, juntar

R2 = "R2 reproduzido: dois pedidos simultâneos processam o mesmo turno"
R2_VIRADA = "R2 reproduzido: duas viradas simultâneas criam duas temporadas seguintes"


def _clube():
    return simulacao_service.listar_clubes()[0]["nome"]


def _contagens(sid):
    conn = conectar()
    try:
        um = lambda sql: conn.execute(sql, (sid,)).fetchone()[0]   # noqa: E731
        por_rodada = dict(conn.execute(
            "SELECT rodada, COUNT(*) FROM partida WHERE simulacao_id = ? GROUP BY rodada",
            (sid,),
        ).fetchall())
        sim = simulacao_repo.buscar(conn, sid)
        return {
            "rodada_atual": sim["rodada_atual"],
            "partidas_por_rodada": por_rodada,
            "lances": um("SELECT COUNT(*) FROM lance l JOIN partida p ON p.id = l.partida_id"
                         " WHERE p.simulacao_id = ?"),
            "atuacoes": um("SELECT COUNT(*) FROM atuacao a JOIN partida p ON p.id = a.partida_id"
                           " WHERE p.simulacao_id = ?"),
            "mensagens": um("SELECT COUNT(*) FROM mensagem WHERE simulacao_id = ?"),
        }
    finally:
        conn.close()


def _sincronizar_avanco(monkeypatch):
    """Trava em volta da simulação (restaurar → serializar) e barreira antes
    da escrita."""
    trava = threading.Lock()
    barreira = threading.Barrier(2, timeout=ESPERA)
    restaurar_original = temporada_service.restaurar_estado
    serializar_original = simulacao_service._serializar

    def restaurar(campeonato, blob):
        assert trava.acquire(timeout=ESPERA), "a trava da simulação travou"
        return restaurar_original(campeonato, blob)

    def serializar(*args, **kwargs):
        try:
            return serializar_original(*args, **kwargs)
        finally:
            trava.release()
            barreira.wait()   # os dois já leram e simularam; agora gravam

    monkeypatch.setattr(temporada_service, "restaurar_estado", restaurar)
    monkeypatch.setattr(simulacao_service, "_serializar", serializar)


def _referencia_uma_rodada():
    sid = temporada_service.iniciar(seed=5, clube_usuario=_clube())
    temporada_service.avancar(sid)
    return _contagens(sid)


# ---------------------------------------------------------------------------
# controle: dois avanços em sequência jogam as rodadas 1 e 2
# ---------------------------------------------------------------------------

def test_controle_dois_avancos_em_sequencia_jogam_rodadas_diferentes():
    sid = temporada_service.iniciar(seed=5, clube_usuario=_clube())
    temporada_service.avancar(sid)
    temporada_service.avancar(sid)
    c = _contagens(sid)
    assert c["rodada_atual"] == 3
    assert set(c["partidas_por_rodada"]) == {1, 2}


# ---------------------------------------------------------------------------
# R2: a mesma rodada jogada duas vezes
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=True, reason=R2)
def test_r2_dois_avancos_simultaneos_nao_duplicam_a_rodada():
    ref = _referencia_uma_rodada()
    sid = temporada_service.iniciar(seed=5, clube_usuario=_clube())

    # MonkeyPatch próprio: desfazer os ganchos sem desfazer o banco
    # temporário do conftest (que usa o `monkeypatch` do teste)
    with pytest.MonkeyPatch.context() as mp:
        _sincronizar_avanco(mp)
        a = Fio("A", lambda: temporada_service.avancar(sid))
        b = Fio("B", lambda: temporada_service.avancar(sid))
        a.start()
        b.start()
        juntar(a, b)

    c = _contagens(sid)
    erros = [repr(f.erro) for f in (a, b) if f.erro]
    rodadas = [f.resultado["rodada_jogada"] for f in (a, b) if f.resultado]
    detalhe = f"referência (1 rodada): {ref} | dois pedidos: {c} | rodadas jogadas: {rodadas} | erros: {erros}"

    # correto: cada rodada aparece uma vez só e o save anda uma rodada por
    # rodada gravada (ou o segundo pedido é recusado, ou joga a rodada 2)
    assert all(n == ref["partidas_por_rodada"][1] for n in c["partidas_por_rodada"].values()), detalhe
    assert c["rodada_atual"] == 1 + len(c["partidas_por_rodada"]), detalhe


# ---------------------------------------------------------------------------
# R2: duas viradas de temporada
# ---------------------------------------------------------------------------

def _sincronizar_virada(monkeypatch):
    """Barreira logo depois das validações (sucessora, cargo) e antes da
    transação de escrita. O cargo vem fixo, como em `cargo_garantido`."""
    barreira = threading.Barrier(2, timeout=ESPERA)

    def cargo(conn, sim):
        barreira.wait()
        return {"estado": "mantido", "motivo": None}

    monkeypatch.setattr(simulacao_service, "cargo_da_temporada", cargo)


def _viradas_simultaneas(sid):
    with pytest.MonkeyPatch.context() as mp:
        _sincronizar_virada(mp)
        a = Fio("A", lambda: carreira_service.proxima_temporada(sid))
        b = Fio("B", lambda: carreira_service.proxima_temporada(sid))
        a.start()
        b.start()
        juntar(a, b)
    return a, b


def _temporadas_seguintes(sid):
    conn = conectar()
    try:
        sim = simulacao_repo.buscar(conn, sid)
        filhas = conn.execute(
            "SELECT id, carreira_id, temporada FROM simulacao"
            " WHERE temporada = ? AND clube_usuario = ? AND id != ?",
            (sim["temporada"] + 1, sim["clube_usuario"], sid),
        ).fetchall()
        carreiras = conn.execute("SELECT COUNT(*) FROM carreira").fetchone()[0]
        return [dict(r) for r in filhas], carreiras, sim["carreira_id"]
    finally:
        conn.close()


def _resumo(a, b):
    return [
        {"fio": f.name, "resultado": f.resultado, "erro": repr(f.erro) if f.erro else None}
        for f in (a, b)
    ]


@pytest.mark.xfail(strict=True, reason=R2_VIRADA)
def test_r2_virada_dupla_da_temporada_1_cria_uma_carreira_so():
    """Primeira virada: o save ainda não tem carreira, então nem a checagem
    de `sucessora()` existe — cada pedido cria a sua carreira."""
    sid = simulacao_service.salvar_temporada(seed=3, clube_usuario=_clube())

    a, b = _viradas_simultaneas(sid)
    filhas, carreiras, carreira_do_save = _temporadas_seguintes(sid)
    detalhe = (f"temporadas 2: {filhas} | carreiras no banco: {carreiras} | "
               f"carreira do save: {carreira_do_save} | pedidos: {_resumo(a, b)}")

    assert len(filhas) == 1, detalhe
    assert carreiras == 1, detalhe


@pytest.mark.xfail(strict=True, reason=R2_VIRADA)
def test_r2_virada_dupla_dentro_de_uma_carreira_cria_uma_temporada_so():
    """Save que já é a temporada 1 de uma carreira: a checagem de
    `sucessora()` existe, mas roda antes da transação de escrita."""
    sid = simulacao_service.salvar_temporada(seed=3, clube_usuario=_clube())
    conn = conectar()
    try:
        with conn:
            sim = simulacao_repo.buscar(conn, sid)
            carreira_id = carreira_repo.criar(conn, sim["clube_usuario"], sim["seed"], "2026-11-17")
            simulacao_repo.vincular_carreira(conn, sid, carreira_id, 1)
    finally:
        conn.close()

    a, b = _viradas_simultaneas(sid)
    filhas, carreiras, _ = _temporadas_seguintes(sid)
    da_carreira = [f for f in filhas if f["carreira_id"] == carreira_id]
    detalhe = (f"temporadas 2 da carreira {carreira_id}: {da_carreira} | "
               f"pedidos: {_resumo(a, b)}")

    assert len(da_carreira) == 1, detalhe
    perdedor = [f for f in (a, b) if f.erro]
    assert len(perdedor) == 1 and isinstance(perdedor[0].erro, carreira_service.CarreiraInvalida), detalhe


def test_controle_segunda_virada_em_sequencia_e_recusada(cargo_garantido):
    sid = simulacao_service.salvar_temporada(seed=3, clube_usuario=_clube())
    primeira = carreira_service.proxima_temporada(sid)
    with pytest.raises(carreira_service.CarreiraInvalida):
        carreira_service.proxima_temporada(sid)
    assert primeira["temporada"] == 2
