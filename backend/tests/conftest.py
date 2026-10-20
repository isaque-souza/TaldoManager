"""Cada teste roda contra um SQLite temporário e vazio, nunca o banco real."""

import pytest

from app.db.conexao import init_db


@pytest.fixture(autouse=True)
def banco_temporario(tmp_path, monkeypatch):
    monkeypatch.setenv("TALDO_DB", str(tmp_path / "teste.db"))
    init_db()
    yield


@pytest.fixture(autouse=True)
def sem_login():
    """As contas (v2.1) têm testes próprios (test_contas.py); nos outros a
    API responde sem login, como antes, e os saves ficam sem dono."""
    from app.api.contas import exigir_dono
    from app.main import app
    app.dependency_overrides[exigir_dono] = lambda: None
    yield
    app.dependency_overrides.pop(exigir_dono, None)


@pytest.fixture
def cargo_garantido(monkeypatch):
    """Para testes de virada que não são sobre a diretoria: com a seed
    fixa, o técnico pode acabar demitido (e a virada é recusada) a cada
    ajuste do motor que mexe nos resultados."""
    from app.services import simulacao_service
    monkeypatch.setattr(
        simulacao_service, "cargo_da_temporada",
        lambda conn, sim: {"estado": "mantido", "motivo": None},
    )
