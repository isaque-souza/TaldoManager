"""Passa os saves sem dono (de antes das contas, v2.1) para uma conta.

Uso (a partir da pasta backend/, com a conta já criada no jogo):
    python -m scripts.dar_saves <nome-da-conta>
"""

import sys

from app.db.conexao import conectar, init_db
from app.repositories import usuario_repository as usuario_repo


def main(nome):
    init_db()
    conn = conectar()
    try:
        u = usuario_repo.buscar_por_nome(conn, nome)
        if u is None:
            sys.exit(f"Conta '{nome}' não existe: crie no jogo primeiro.")
        n = usuario_repo.dar_saves_sem_dono(conn, u["id"])
        conn.commit()
    finally:
        conn.close()
    print(f"{n} save(s) agora são de {u['nome']}.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
