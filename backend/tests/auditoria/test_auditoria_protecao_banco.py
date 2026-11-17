"""Auditoria 02 — a proteção do banco padrão (ver `conftest.py` desta pasta)."""

import os
from pathlib import Path

import pytest

from app.core import config
from app.db.conexao import conectar
from tests.auditoria.protecao import BancoPadraoBloqueado

PADRAO = Path(config._DB_PADRAO).resolve()


def test_conexao_normal_vai_para_o_banco_temporario():
    caminho = os.environ["TALDO_DB"]
    assert Path(caminho).resolve() != PADRAO
    conn = conectar()
    try:
        arquivo = conn.execute("PRAGMA database_list").fetchone()["file"]
    finally:
        conn.close()
    assert Path(arquivo).resolve() == Path(caminho).resolve()


def test_sem_a_protecao_o_acidente_iria_para_o_banco_padrao(monkeypatch):
    """O risco que a proteção cobre, sem abrir arquivo nenhum: sem
    TALDO_DB, o `caminho_banco()` de produção devolve o banco padrão."""
    monkeypatch.delenv("TALDO_DB")
    assert Path(config.caminho_banco()).resolve() == PADRAO


def test_monkeypatch_undo_nao_abre_o_banco_padrao(monkeypatch):
    """O acidente da Auditoria 01: `undo()` desfaz o TALDO_DB do conftest."""
    existia = PADRAO.exists()
    monkeypatch.undo()
    assert "TALDO_DB" not in os.environ
    with pytest.raises(BancoPadraoBloqueado, match="não está definido"):
        conectar()
    assert PADRAO.exists() == existia   # nada foi criado


def test_apontar_para_o_banco_padrao_e_recusado(monkeypatch):
    existia = PADRAO.exists()
    monkeypatch.setenv("TALDO_DB", str(PADRAO))
    with pytest.raises(BancoPadraoBloqueado, match="aponta para o banco padrão"):
        conectar()
    assert PADRAO.exists() == existia
