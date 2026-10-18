"""Caixa de entrada do técnico (v1.3): ler as mensagens dos setores do
clube. Quem escreve são os outros serviços (mercado, rodada, carreira),
com os textos de app.domain.caixa."""

from app.db.conexao import conectar
from app.domain.caixa import SETORES
from app.repositories import mensagem_repository as mensagem_repo
from app.repositories import simulacao_repository as simulacao_repo


def _caixa(conn, simulacao_id):
    mensagens = mensagem_repo.listar(conn, simulacao_id)
    return {
        "mensagens": mensagens,
        "nao_lidas": sum(not m["lida"] for m in mensagens),
        "setores": list(SETORES),
    }


def listar(simulacao_id):
    """{mensagens, nao_lidas, setores}; None se a simulação não existe."""
    conn = conectar()
    try:
        if simulacao_repo.buscar(conn, simulacao_id) is None:
            return None
        return _caixa(conn, simulacao_id)
    finally:
        conn.close()


def ler(simulacao_id, mensagem_id):
    """Marca uma mensagem como lida. None se ela não existe nesse save."""
    conn = conectar()
    try:
        with conn:
            if not mensagem_repo.marcar_lida(conn, simulacao_id, mensagem_id):
                return None
        return _caixa(conn, simulacao_id)
    finally:
        conn.close()


def ler_todas(simulacao_id):
    conn = conectar()
    try:
        if simulacao_repo.buscar(conn, simulacao_id) is None:
            return None
        with conn:
            mensagem_repo.marcar_todas(conn, simulacao_id)
        return _caixa(conn, simulacao_id)
    finally:
        conn.close()
