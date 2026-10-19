"""Acesso à tabela `negociacao` (contratações do técnico em duas etapas, v1.7)."""


def inserir(conn, simulacao_id, rodada, jogador, valor, jogador_id=None, clube=None):
    cur = conn.execute(
        """
        INSERT INTO negociacao
            (simulacao_id, rodada, jogador_id, jogador, clube, valor, status)
        VALUES (?, ?, ?, ?, ?, ?, 'aberta')
        """,
        (simulacao_id, rodada, jogador_id, jogador, clube, valor),
    )
    return cur.lastrowid


def buscar(conn, negociacao_id):
    return conn.execute(
        "SELECT * FROM negociacao WHERE id = ?", (negociacao_id,)
    ).fetchone()


def listar_da_janela(conn, simulacao_id, rodada):
    """As negociações desta janela, na ordem em que começaram."""
    return conn.execute(
        """
        SELECT * FROM negociacao
        WHERE simulacao_id = ? AND rodada = ?
        ORDER BY id
        """,
        (simulacao_id, rodada),
    ).fetchall()


def registrar_tentativa(conn, negociacao_id, status, contra=None):
    """Mais uma proposta de contrato; `contra` = (salário, anos, multa,
    papel) da contraproposta, ou None."""
    salario, anos, multa, papel = contra or (None, None, None, None)
    conn.execute(
        """
        UPDATE negociacao
           SET tentativas = tentativas + 1, status = ?,
               contra_salario = ?, contra_anos = ?, contra_multa = ?, contra_papel = ?
         WHERE id = ?
        """,
        (status, salario, anos, multa, papel, negociacao_id),
    )


def expirar_abertas(conn, simulacao_id, rodada):
    """A rodada foi jogada: os acordos abertos desta janela caem. Devolve
    as que expiraram."""
    abertas = conn.execute(
        """
        SELECT * FROM negociacao
        WHERE simulacao_id = ? AND rodada = ? AND status = 'aberta'
        """,
        (simulacao_id, rodada),
    ).fetchall()
    conn.execute(
        """
        UPDATE negociacao SET status = 'expirada'
        WHERE simulacao_id = ? AND rodada = ? AND status = 'aberta'
        """,
        (simulacao_id, rodada),
    )
    return abertas
