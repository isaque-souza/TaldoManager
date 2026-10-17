import pytest

from app.db.conexao import conectar
from app.services import carreira_service, simulacao_service, temporada_service
from app.services.carreira_service import CarreiraInvalida


def _um_clube():
    return simulacao_service.listar_clubes()[0]["nome"]


def _temporada_concluida(seed=3, clube=None):
    """Um save concluído com clube dirigido (o "simular tudo" é o jeito
    mais rápido de ter um)."""
    return simulacao_service.salvar_temporada(
        seed=seed, clube_usuario=clube or _um_clube()
    )


def test_continuar_cria_carreira_e_temporada_2_em_andamento():
    sid = _temporada_concluida(seed=3)

    r = carreira_service.proxima_temporada(sid)
    assert r["temporada"] == 2

    t1 = simulacao_service.carregar_temporada(sid)
    t2 = simulacao_service.carregar_temporada(r["simulacao_id"])

    assert t1["carreira_id"] == t2["carreira_id"] == r["carreira_id"]
    assert (t1["temporada"], t2["temporada"]) == (1, 2)
    assert t1["proxima_temporada_id"] == r["simulacao_id"]
    assert t2["proxima_temporada_id"] is None

    assert t2["estado"] == "em_andamento"
    assert t2["rodada_atual"] == 1
    assert t2["seed"] == 4                       # seed + (2 − 1)
    assert t2["clube_usuario"] == t1["clube_usuario"]


def test_temporada_2_zera_estatisticas_e_herda_o_caixa():
    sid = _temporada_concluida(seed=3)
    nova = carreira_service.proxima_temporada(sid)["simulacao_id"]

    t1 = simulacao_service.carregar_temporada(sid)
    t2 = simulacao_service.carregar_temporada(nova)

    assert all(c["jogos"] == 0 and c["pontos"] == 0 for c in t2["classificacao"])
    assert t2["artilharia"] == []

    final = {f["clube"]: f for f in t1["financas"]}
    for f in t2["financas"]:
        assert f["caixa_inicial"] == final[f["clube"]]["caixa"]
        assert f["caixa"] == f["caixa_inicial"]
        assert f["receitas"] == f["despesas"] == f["saldo"] == 0


def test_jogador_transferido_continua_no_clube_novo():
    sid = _temporada_concluida(seed=3)
    conn = conectar()
    try:
        with conn:
            # simula uma transferência gravada na temporada 1
            de, para = conn.execute(
                "SELECT id FROM clube WHERE simulacao_id = ? LIMIT 2", (sid,)
            ).fetchall()
            jogador = conn.execute(
                "SELECT nome FROM jogador WHERE clube_id = ? LIMIT 1", (de["id"],)
            ).fetchone()["nome"]
            conn.execute(
                "UPDATE jogador SET clube_id = ?, contrato_anos = 3, salario = 1"
                " WHERE simulacao_id = ? AND nome = ?",
                (para["id"], sid, jogador),
            )
            destino = conn.execute(
                "SELECT nome FROM clube WHERE id = ?", (para["id"],)
            ).fetchone()["nome"]
    finally:
        conn.close()

    nova = carreira_service.proxima_temporada(sid)["simulacao_id"]

    conn = conectar()
    try:
        r = conn.execute(
            "SELECT c.nome AS clube, j.salario FROM jogador j"
            " JOIN clube c ON c.id = j.clube_id"
            " WHERE j.simulacao_id = ? AND j.nome = ?",
            (nova, jogador),
        ).fetchone()
    finally:
        conn.close()
    assert (r["clube"], r["salario"]) == (destino, 1)


def test_temporada_2_pode_ser_jogada():
    sid = _temporada_concluida(seed=3)
    nova = carreira_service.proxima_temporada(sid)["simulacao_id"]

    r = temporada_service.avancar(nova)
    assert r["rodada_jogada"] == 1
    assert r["temporada"] == 2


def test_nao_continua_temporada_em_andamento():
    sid = temporada_service.iniciar(seed=1, clube_usuario=_um_clube())
    with pytest.raises(CarreiraInvalida):
        carreira_service.proxima_temporada(sid)


def test_nao_continua_temporada_sem_clube_dirigido():
    sid = simulacao_service.salvar_temporada(seed=3)
    with pytest.raises(CarreiraInvalida):
        carreira_service.proxima_temporada(sid)


def test_so_a_ultima_temporada_continua():
    sid = _temporada_concluida(seed=3)
    carreira_service.proxima_temporada(sid)
    with pytest.raises(CarreiraInvalida, match="já foi continuada"):
        carreira_service.proxima_temporada(sid)


def test_simulacao_inexistente():
    assert carreira_service.proxima_temporada(999) is None
    assert carreira_service.detalhe_carreira(999) is None


def test_temporada_3_e_historico_de_campeoes():
    sid = _temporada_concluida(seed=3)
    r2 = carreira_service.proxima_temporada(sid)
    while not temporada_service.avancar(r2["simulacao_id"])["concluida"]:
        pass
    r3 = carreira_service.proxima_temporada(r2["simulacao_id"])

    assert r3["temporada"] == 3
    assert r3["carreira_id"] == r2["carreira_id"]

    carreira = carreira_service.detalhe_carreira(r2["carreira_id"])
    temporadas = carreira["temporadas"]
    assert [t["temporada"] for t in temporadas] == [1, 2, 3]
    assert [t["seed"] for t in temporadas] == [3, 4, 5]
    assert temporadas[0]["campeao"] and temporadas[1]["campeao"]
    assert temporadas[2]["campeao"] is None
    assert temporadas[2]["estado"] == "em_andamento"
