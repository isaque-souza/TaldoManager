"""Proteção do banco padrão para os testes de auditoria (Auditoria 02).

O `conftest.py` da raiz aponta `TALDO_DB` para um SQLite temporário com o
`monkeypatch` de cada teste. Se um teste chamar `monkeypatch.undo()` (ou
apagar `TALDO_DB`), `caminho_banco()` volta ao banco padrão
(`backend/data/database/taldo_manager.db`) e a próxima conexão abre — ou
cria — esse arquivo. Isso aconteceu na Auditoria 01.

Aqui `app.db.conexao.caminho_banco` é trocado por uma versão que RECUSA o
banco padrão. A troca é feita à mão (não pelo `monkeypatch`), então um
`monkeypatch.undo()` não a desfaz. Vale só para os módulos desta pasta
(escopo de módulo) e é desfeita no fim de cada um: os testes de fora não
mudam.
"""

import pytest

from app.db import conexao
from tests.auditoria.protecao import caminho_protegido


@pytest.fixture(autouse=True, scope="module")
def protecao_do_banco_padrao():
    original = conexao.caminho_banco
    conexao.caminho_banco = caminho_protegido
    try:
        yield
    finally:
        conexao.caminho_banco = original
