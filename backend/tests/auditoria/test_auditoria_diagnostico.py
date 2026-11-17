"""Auditoria 02 — o diagnóstico somente leitura
(`AUDITORIA/scripts/diagnostico_integridade.py`).

Valida as consultas nos dois sentidos, sempre no SQLite temporário do teste:
- numa base LIMPA, feita pelos fluxos normais do jogo, as checagens não
  acusam nada (sem falso positivo nesses fluxos);
- numa base com as duplicatas do R2 (reproduzidas como na Auditoria 01),
  as checagens certas acusam.
E as proteções: recusa de caminhos, authorizer e arquivo intacto.
"""

import importlib.util
import os
import sys
import threading
from pathlib import Path

import pytest

from app.db.conexao import conectar
from app.repositories import carreira_repository as carreira_repo
from app.repositories import simulacao_repository as simulacao_repo
from app.services import (
    carreira_service, mercado_service, simulacao_service, temporada_service,
)
from tests.auditoria.roteiro import ESPERA, Fio, juntar
from tests.auditoria.test_auditoria_r2_concorrencia import _sincronizar_avanco
from tests.negociar import oferecer

_SCRIPT = Path(__file__).resolve().parents[3] / "AUDITORIA" / "scripts" / "diagnostico_integridade.py"
_spec = importlib.util.spec_from_file_location("diagnostico_integridade", _SCRIPT)
diag = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = diag   # o dataclass procura o módulo aqui
_spec.loader.exec_module(diag)


def _banco():
    return os.environ["TALDO_DB"]


def _achados(rel):
    return {r["id"]: r for r in rel["resultados"]}


def _com_achados(rel):
    return {r["id"]: r["amostra"][:3] for r in rel["resultados"] if r["achados"]}


def _clube():
    return simulacao_service.listar_clubes()[0]["nome"]


# ---------------------------------------------------------------------------
# base limpa: os fluxos normais não acusam nada
# ---------------------------------------------------------------------------

def _base_limpa(cargo_garantido):
    # temporada em andamento, 3 rodadas
    a = temporada_service.iniciar(seed=5, clube_usuario=_clube())
    for _ in range(3):
        temporada_service.avancar(a)
    # venda aceita (regrava o blob por `_Contexto.gravar`) e mais uma rodada
    b = temporada_service.iniciar(seed=11, clube_usuario="Real Taldo")
    m = mercado_service.ver_mercado(b)
    vendido = next(f for f in m["elenco"] if f["bloqueio"] is None)
    comprador = next(f["clube"] for f in m["disponiveis"] if not f["rival"])
    mercado_service.aceitar_oferta(b, oferecer(b, vendido["jogador_id"], comprador, 1_000_000))
    temporada_service.avancar(b)
    # temporada inteira de uma vez, virada para a carreira e 2 rodadas
    c = simulacao_service.salvar_temporada(seed=3, clube_usuario=_clube())
    nova = carreira_service.proxima_temporada(c)["simulacao_id"]
    temporada_service.avancar(nova)
    temporada_service.avancar(nova)


def test_base_limpa_nao_tem_achado_forte(cargo_garantido):
    _base_limpa(cargo_garantido)
    rel = diag.diagnosticar(_banco())
    erros = {r["id"]: r["erro"] for r in rel["resultados"] if r["erro"]}
    assert not erros, erros
    fortes = {k: v for k, v in _com_achados(rel).items()
              if _achados(rel)[k]["forca"] == "forte"}
    assert not fortes, fortes


def test_base_limpa_sinais(cargo_garantido):
    """Os 'sinais' também devem ficar quietos nos fluxos normais; o que
    acusar aqui é falso positivo a documentar."""
    _base_limpa(cargo_garantido)
    rel = diag.diagnosticar(_banco())
    sinais = {k: v for k, v in _com_achados(rel).items()
              if _achados(rel)[k]["forca"] == "sinal"}
    assert not sinais, sinais


# ---------------------------------------------------------------------------
# base com as duplicatas do R2
# ---------------------------------------------------------------------------

def test_rodada_dupla_e_acusada():
    sid = temporada_service.iniciar(seed=5, clube_usuario=_clube())
    with pytest.MonkeyPatch.context() as mp:
        _sincronizar_avanco(mp)
        fios = [Fio(n, lambda: temporada_service.avancar(sid)) for n in "AB"]
        for f in fios:
            f.start()
        juntar(*fios)
    a = _achados(diag.diagnosticar(_banco()))
    assert a["C01"]["achados"] == 10        # cada mandante da rodada 1, duas vezes
    assert a["C02"]["achados"] == 20        # cada clube em dois jogos
    assert a["C04"]["achados"] == 1         # a rodada 1 com 20 jogos e não 10
    assert a["C17"]["achados"] == 20        # todo clube: 2 jogos gravados × 1 na tabela
    assert a["C03"]["achados"] == 0         # rodadas distintas batem: não acusa
    assert a["B01"]["achados"] == 0         # blob e tabelas concordam entre si


def _viradas(sid):
    barreira = threading.Barrier(2, timeout=ESPERA)

    def cargo(conn, sim):
        barreira.wait()
        return {"estado": "mantido", "motivo": None}

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(simulacao_service, "cargo_da_temporada", cargo)
        fios = [Fio(n, lambda: carreira_service.proxima_temporada(sid)) for n in "AB"]
        for f in fios:
            f.start()
        juntar(*fios)


def test_virada_dupla_dentro_da_carreira_e_acusada():
    sid = simulacao_service.salvar_temporada(seed=3, clube_usuario=_clube())
    conn = conectar()
    try:
        with conn:
            sim = simulacao_repo.buscar(conn, sid)
            carreira = carreira_repo.criar(conn, sim["clube_usuario"], sim["seed"], "2026-11-17")
            simulacao_repo.vincular_carreira(conn, sid, carreira, 1)
    finally:
        conn.close()
    _viradas(sid)
    a = _achados(diag.diagnosticar(_banco()))
    assert a["C05"]["achados"] == 1          # (carreira, temporada 2) duas vezes
    assert a["C07"]["achados"] == 1          # duas temporadas em andamento


def test_virada_dupla_sem_carreira_e_acusada():
    sid = simulacao_service.salvar_temporada(seed=3, clube_usuario=_clube())
    _viradas(sid)
    a = _achados(diag.diagnosticar(_banco()))
    assert a["C05"]["achados"] == 0          # cada uma na sua carreira...
    assert a["C06"]["achados"] == 1          # ...mas uma ficou sem a temporada 1


# ---------------------------------------------------------------------------
# proteções do script
# ---------------------------------------------------------------------------

def test_recusa_caminho_vazio_inexistente_padrao_e_producao(tmp_path):
    with pytest.raises(diag.Recusado):
        diag.validar_caminho("")
    with pytest.raises(diag.Recusado, match="não encontrado"):
        diag.validar_caminho(tmp_path / "nao_existe.db")
    assert diag.BANCO_PADRAO.name == "taldo_manager.db"
    assert diag.BANCO_PADRAO.parent.name == "database"
    if diag.BANCO_PADRAO.exists():   # só se houver um banco local de desenvolvimento
        with pytest.raises(diag.Recusado, match="banco padrão"):
            diag.validar_caminho(diag.BANCO_PADRAO)
    assert diag.main([str(tmp_path / "nao_existe.db")]) == 2


def test_authorizer_nega_toda_escrita_e_as_tabelas_de_conta():
    temporada_service.avancar(temporada_service.iniciar(seed=5, clube_usuario=_clube()))
    conn = diag.abrir(_banco())
    try:
        tentativas = [
            "DELETE FROM partida",
            "UPDATE simulacao SET campeao = 'x'",
            "INSERT INTO carreira (clube_usuario, criada_em) VALUES ('x', 'y')",
            "CREATE INDEX ix_teste ON partida(rodada)",
            "CREATE UNIQUE INDEX ux_teste ON partida(simulacao_id, rodada, mandante_id)",
            "DROP TABLE lance",
            "PRAGMA query_only = OFF",
            "ATTACH DATABASE ':memory:' AS outro",
            "SELECT * FROM usuario",
            "SELECT * FROM sessao",
        ]
        res = diag.executar(conn, [diag.Checagem(f"X{i}", sql, "forte", sql)
                                   for i, sql in enumerate(tentativas)])
    finally:
        conn.close()
    assert all(r.erro for r in res), [(r.titulo, r.erro) for r in res if not r.erro]
    conn = conectar()
    try:
        assert conn.execute("SELECT COUNT(*) FROM partida").fetchone()[0] == 10
    finally:
        conn.close()


def test_o_arquivo_nao_muda():
    temporada_service.avancar(temporada_service.iniciar(seed=5, clube_usuario=_clube()))
    antes = diag.sha256(_banco())
    rel = diag.diagnosticar(_banco())
    assert rel["sha256"] == antes == diag.sha256(_banco())
