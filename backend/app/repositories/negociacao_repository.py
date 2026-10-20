"""Acesso à tabela `negociacao` (contratações do técnico em duas etapas, v1.7)."""


def inserir(conn, simulacao_id, rodada, jogador, valor, jogador_id=None, clube=None,
            emprestimo_id=None, concorrente=None):
    """`concorrente` (v1.9): (clube, salário, fator) de quem disputa o
    jogador, ou None."""
    nome, salario, fator = concorrente or (None, None, None)
    cur = conn.execute(
        """
        INSERT INTO negociacao
            (simulacao_id, rodada, jogador_id, jogador, clube, valor, status,
             emprestimo_id, concorrente, concorrente_salario, concorrente_fator)
        VALUES (?, ?, ?, ?, ?, ?, 'aberta', ?, ?, ?, ?)
        """,
        (simulacao_id, rodada, jogador_id, jogador, clube, valor, emprestimo_id,
         nome, salario, fator),
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


def listar_disputas_perdidas(conn, simulacao_id, rodada):
    """As negociações desta janela com concorrente que o técnico não fechou:
    abertas (a rodada vai ser jogada) ou em que o jogador desistiu (v1.9)."""
    return conn.execute(
        """
        SELECT * FROM negociacao
        WHERE simulacao_id = ? AND rodada = ? AND concorrente IS NOT NULL
          AND status IN ('aberta', 'desistiu')
        ORDER BY id
        """,
        (simulacao_id, rodada),
    ).fetchall()


def marcar_perdida(conn, negociacao_id):
    conn.execute(
        "UPDATE negociacao SET status = 'perdida' WHERE id = ?", (negociacao_id,)
    )
