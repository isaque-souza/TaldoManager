"""Proteção do banco padrão para os testes de auditoria (ver `conftest.py`)."""

import os
from pathlib import Path

from app.core import config


class BancoPadraoBloqueado(RuntimeError):
    """Um teste de auditoria tentou abrir o banco padrão."""


def _padrao():
    return Path(config._DB_PADRAO).resolve()


def caminho_protegido():
    caminho = os.environ.get("TALDO_DB")
    if not caminho:
        raise BancoPadraoBloqueado(
            "TALDO_DB não está definido: a conexão iria para o banco padrão "
            f"({_padrao()}). O banco temporário do conftest foi desfeito?"
        )
    if caminho != ":memory:" and Path(caminho).resolve() == _padrao():
        raise BancoPadraoBloqueado(f"TALDO_DB aponta para o banco padrão ({_padrao()})")
    return caminho
