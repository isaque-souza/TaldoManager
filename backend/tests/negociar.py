"""Ajuda dos testes (v1.7): fecha a etapa 2 de uma negociação com um
contrato que qualquer jogador aceita."""

from app.services import mercado_service


def fechar(sid, negociacao_id):
    d = mercado_service.ver_negociacao(sid, negociacao_id)
    salario = max(5 * d["salario_referencia"], 2 * (d["salario_atual"] or 0))
    r = mercado_service.propor_contrato(
        sid, negociacao_id, salario, min(2, d["duracao_max"]), "3x", d["papel_esperado"]
    )
    assert r["resposta"] == "aceita", r
    return r


def oferecer(sid, jogador_id, clube, valor, teto=None, espontanea=False):
    """Uma oferta da CPU (v1.7) gravada direto, sem o sorteio: para testar a
    venda com o clube e o valor que o teste quer. Devolve o id."""
    from app.db.conexao import conectar
    from app.repositories import oferta_repository, simulacao_repository

    conn = conectar()
    try:
        with conn:
            rodada = simulacao_repository.buscar(conn, sid)["rodada_atual"]
            return oferta_repository.inserir(
                conn, sid, rodada, jogador_id, clube, valor, teto or valor, espontanea,
            )
    finally:
        conn.close()
