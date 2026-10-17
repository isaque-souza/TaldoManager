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


def _jogadores(sid):
    conn = conectar()
    try:
        return {
            r["nome"]: dict(r)
            for r in conn.execute(
                "SELECT nome, idade, overall, potencial FROM jogador"
                " WHERE simulacao_id = ?", (sid,)
            )
        }
    finally:
        conn.close()


def test_virada_envelhece_e_evolui_os_jogadores():
    sid = _temporada_concluida(seed=3)
    nova = carreira_service.proxima_temporada(sid)["simulacao_id"]

    t1, t2 = _jogadores(sid), _jogadores(nova)
    # quem se aposentou (ou deixou a liga) não está na temporada 2
    ficaram = [n for n in t1 if n in t2]
    assert all(t2[n]["idade"] == t1[n]["idade"] + 1 for n in ficaram)

    jovens = [n for n in ficaram if t1[n]["potencial"] - t1[n]["overall"] >= 5]
    velhos = [n for n in ficaram if t1[n]["idade"] >= 32]
    assert any(t2[n]["overall"] > t1[n]["overall"] for n in jovens)
    assert all(t2[n]["overall"] < t1[n]["overall"] for n in velhos)


def test_evolucao_nao_se_perde_ao_jogar_rodadas():
    # overall/idade entram no snapshot: sem isso, a rodada 1 recarregaria
    # os valores da seed e a evolução sumiria
    sid = _temporada_concluida(seed=3)
    nova = carreira_service.proxima_temporada(sid)["simulacao_id"]
    antes = _jogadores(nova)

    temporada_service.avancar(nova)
    temporada_service.avancar(nova)

    assert _jogadores(nova) == antes


def test_mesma_seed_evolui_igual():
    a = carreira_service.proxima_temporada(_temporada_concluida(seed=3))
    b = carreira_service.proxima_temporada(_temporada_concluida(seed=3))
    assert _jogadores(a["simulacao_id"]) == _jogadores(b["simulacao_id"])


# --- aposentadoria e contratos (passo 3) ---

def _virada(seed=3):
    sid = _temporada_concluida(seed=seed)
    nova = carreira_service.proxima_temporada(sid)["simulacao_id"]
    return sid, nova


def test_movimentos_da_virada_ficam_na_visao():
    _, nova = _virada()
    movs = simulacao_service.carregar_temporada(nova)["movimentos_virada"]

    tipos = {m["tipo"] for m in movs}
    assert "renovou" in tipos          # a CPU renovou quem venceu
    assert "aposentou" in tipos        # seed tem 40 jogadores com 34+
    assert all(m["idade"] >= 34 for m in movs if m["tipo"] == "aposentou")


def test_aposentados_somem_da_temporada_seguinte():
    sid, nova = _virada()
    movs = simulacao_service.carregar_temporada(nova)["movimentos_virada"]
    t2 = _jogadores(nova)
    for m in movs:
        if m["tipo"] == "aposentou" or m["detalhe"] == "deixou a liga":
            assert m["jogador"] not in t2


def test_contrato_vencido_do_tecnico_sai_ou_fica_por_emergencia():
    sid, nova = _virada()
    clube = simulacao_service.carregar_temporada(sid)["clube_usuario"]

    conn = conectar()
    try:
        vencendo = [r["nome"] for r in conn.execute(
            "SELECT j.nome FROM jogador j JOIN clube c ON c.id = j.clube_id"
            " WHERE j.simulacao_id = ? AND c.nome = ? AND j.contrato_anos = 1",
            (sid, clube),
        )]
    finally:
        conn.close()
    assert vencendo, "a seed deveria ter contratos de 1 temporada"

    movs = {
        m["jogador"]: m for m in
        simulacao_service.carregar_temporada(nova)["movimentos_virada"]
        if m["clube"] == clube
    }
    for nome in vencendo:
        m = movs[nome]
        assert m["tipo"] in ("saiu_livre", "aposentou") or (
            m["tipo"] == "renovou" and "emergência" in m["detalhe"]
        )


def test_elencos_continuam_validos_depois_de_varias_viradas():
    sid = _temporada_concluida(seed=5)
    for _ in range(3):
        sid = carreira_service.proxima_temporada(sid)["simulacao_id"]
        conn = conectar()
        try:
            elencos = conn.execute(
                "SELECT c.nome, COUNT(*) AS n,"
                " SUM(j.posicao = 'Goleiro') AS goleiros"
                " FROM jogador j JOIN clube c ON c.id = j.clube_id"
                " WHERE j.simulacao_id = ? GROUP BY c.nome", (sid,),
            ).fetchall()
        finally:
            conn.close()
        assert len(elencos) == 20
        for e in elencos:
            assert 16 <= e["n"] <= 25, e["nome"]
            assert e["goleiros"] >= 2, e["nome"]
        while not temporada_service.avancar(sid)["concluida"]:
            pass


# --- jovens da base (passo 4) ---

from app.domain import contrato  # noqa: E402
from app.services import contrato_service, mercado_service  # noqa: E402


def _jovens_da_base(sid):
    return [m for m in simulacao_service.carregar_temporada(sid)["movimentos_virada"]
            if m["tipo"] == "subiu_da_base"]


def test_virada_sobe_jovens_em_todos_os_clubes():
    _, nova = _virada()
    jovens = _jovens_da_base(nova)

    assert {m["clube"] for m in jovens} == {
        c["clube"] for c in simulacao_service.carregar_temporada(nova)["classificacao"]
    }
    t2 = _jogadores(nova)
    for m in jovens:
        assert m["jogador"] in t2
        assert 16 <= t2[m["jogador"]]["idade"] <= 18


def test_jovem_da_base_sobrevive_as_rodadas_e_a_proxima_virada():
    _, nova = _virada()
    jovem = _jovens_da_base(nova)[0]["jogador"]

    while not temporada_service.avancar(nova)["concluida"]:
        pass
    assert jovem in _jogadores(nova)

    t3 = carreira_service.proxima_temporada(nova)["simulacao_id"]
    assert _jogadores(t3)[jovem]["idade"] == _jogadores(nova)[jovem]["idade"] + 1


def test_jovem_da_base_pode_ser_renovado_e_vendido():
    _, nova = _virada()
    clube = simulacao_service.carregar_temporada(nova)["clube_usuario"]
    meu_jovem = next(m["jogador"] for m in _jovens_da_base(nova) if m["clube"] == clube)

    elenco = mercado_service.ver_mercado(nova)["elenco"]
    ficha = next(f for f in elenco if f["nome"] == meu_jovem)

    conn = conectar()
    try:
        ctx = mercado_service._carregar(conn, nova)
        jogador, _ = ctx.jogador(ficha["jogador_id"])
        pedido = contrato.salario_pedido(jogador, ctx.alvo, "3x")
    finally:
        conn.close()
    r = contrato_service.renovar(nova, ficha["jogador_id"], pedido, 5, "3x")
    assert r["resposta"] == "aceita"

    ofertas = mercado_service.ofertas(nova, ficha["jogador_id"])["ofertas"]
    if ofertas:   # um jovem fraco pode não ter comprador
        feita = mercado_service.vender(nova, ficha["jogador_id"], ofertas[0]["clube"])
        assert feita["para_clube"] == ofertas[0]["clube"]

    temporada_service.avancar(nova)
    assert meu_jovem in _jogadores(nova)


def test_nomes_nao_se_repetem_na_carreira():
    sid = _temporada_concluida(seed=5)
    vistos = set(_jogadores(sid))
    for _ in range(2):
        sid = carreira_service.proxima_temporada(sid)["simulacao_id"]
        novos = {m["jogador"] for m in _jovens_da_base(sid)}
        assert not novos & vistos
        vistos |= set(_jogadores(sid))
        while not temporada_service.avancar(sid)["concluida"]:
            pass
