"""Relatório pós-jogo (v2.2): lido do que a rodada gravou, sem jogar de novo."""

import pytest
from fastapi.testclient import TestClient

from app.db.conexao import conectar
from app.main import app
from app.services import pos_jogo_service, temporada_service
from scripts.data_loader import TODAS_AS_LIGAS

client = TestClient(app)


@pytest.fixture(autouse=True)
def _sem_demissao(cargo_garantido):
    """Não é sobre a diretoria."""


def _foto_do_banco():
    """Tudo o que um relatório não pode mexer: tabela, caixa, elencos,
    partidas, mensagens e o estado do save."""
    conn = conectar()
    try:
        return {
            t: [tuple(r) for r in conn.execute(f"SELECT * FROM {t} ORDER BY id").fetchall()]
            for t in ("simulacao", "clube", "jogador", "partida", "lance", "atuacao", "mensagem")
        }
    finally:
        conn.close()


def test_sem_jogo_ainda_e_simulacao_que_nao_existe():
    sid = temporada_service.iniciar(seed=3, clube_usuario="Real Taldo")
    with pytest.raises(pos_jogo_service.SemJogo):
        pos_jogo_service.ver(sid)
    assert client.get(f"/simulacoes/{sid}/pos-jogo").status_code == 409
    assert client.get("/simulacoes/999/pos-jogo").status_code == 404


def test_vitoria_empate_e_derrota_batem_com_a_tabela_rodada_a_rodada():
    sid = temporada_service.iniciar(seed=3, clube_usuario="Real Taldo")
    anterior = None
    vistos = set()
    for _ in range(38):
        res = temporada_service.avancar(sid)
        r = pos_jogo_service.ver(sid)
        meu = next(p for p in res["resultados"]
                   if "Real Taldo" in (p["mandante"], p["visitante"]))
        # o relatório é o jogo que acabou de ser gravado
        assert r["partida_id"] == meu["partida_id"]
        assert (r["gols_mandante"], r["gols_visitante"]) == (meu["gols_mandante"], meu["gols_visitante"])
        pro, contra = ((r["gols_mandante"], r["gols_visitante"]) if r["mando"] == "casa"
                       else (r["gols_visitante"], r["gols_mandante"]))
        esperado = "vitoria" if pro > contra else "derrota" if pro < contra else "empate"
        assert r["resultado"] == esperado
        vistos.add(esperado)

        t = r["tabela"]
        assert t["pontos_ganhos"] == {"vitoria": 3, "empate": 1, "derrota": 0}[esperado]
        assert t["pontos"] == t["pontos_antes"] + t["pontos_ganhos"]
        linha = next(c for c in res["classificacao"] if c["clube"] == "Real Taldo")
        assert (t["posicao"], t["pontos"]) == (linha["posicao"], linha["pontos"])
        # o "antes" é o "depois" do jogo anterior
        if anterior is not None:
            assert (t["posicao_antes"], t["pontos_antes"]) == (anterior["posicao"], anterior["pontos"])
        anterior = t

        assert r["destaques"]["melhor_em_campo"]["nota"] == max(a["nota"] for a in r["atuacoes"])
        if res["concluida"]:
            break
    assert vistos == {"vitoria", "empate", "derrota"}
    # temporada encerrada: sem próximo compromisso, com o cargo avaliado
    assert r["temporada_concluida"] and r["proximo"] is None and r["cargo"]["estado"] == "mantido"


def test_abrir_o_relatorio_nao_mexe_em_nada_e_repete_o_mesmo():
    sid = temporada_service.iniciar(seed=5, clube_usuario="Real Taldo")
    for _ in range(3):
        temporada_service.avancar(sid)
    antes = _foto_do_banco()
    primeiro = client.get(f"/simulacoes/{sid}/pos-jogo").json()
    segundo = client.get(f"/simulacoes/{sid}/pos-jogo").json()
    assert primeiro == segundo
    assert _foto_do_banco() == antes
    # e a próxima rodada joga igual a um save em que ninguém abriu o relatório
    gemeo = temporada_service.iniciar(seed=5, clube_usuario="Real Taldo")
    for _ in range(3):
        temporada_service.avancar(gemeo)
    a = temporada_service.avancar(sid)["resultados"]
    b = temporada_service.avancar(gemeo)["resultados"]
    assert [(p["mandante"], p["gols_mandante"], p["gols_visitante"]) for p in a] == \
           [(p["mandante"], p["gols_mandante"], p["gols_visitante"]) for p in b]


def test_retomar_o_save_devolve_o_relatorio_do_ultimo_jogo():
    sid = temporada_service.iniciar(seed=4, clube_usuario="Real Taldo")
    temporada_service.avancar(sid)
    temporada_service.avancar(sid)
    r = client.get(f"/simulacoes/{sid}/pos-jogo").json()
    assert r["rodada"] == 2 and r["competicao"] == "liga"
    # o próximo compromisso é o da rodada 3, que o hub também mostra
    prox = client.get(f"/simulacoes/{sid}/rodadas/proxima").json()
    assert r["proximo"]["rodada"] == prox["rodada"] == 3
    assert r["proximo"]["adversario"] == prox["adversario"]
    assert r["proximo"]["mando"] == prox["mando"]


def test_jogo_da_copa_e_a_liga_depois_dele():
    sid = temporada_service.iniciar(seed=6, clube_usuario="Arsenal", ligas=TODAS_AS_LIGAS)
    for _ in range(8):
        temporada_service.avancar(sid)
    da_rodada_8 = pos_jogo_service.ver(sid)
    assert da_rodada_8["competicao"] == "liga"
    # com a copa esperando, o próximo compromisso é ela, na quarta
    proximo = da_rodada_8["proximo"]
    assert proximo["copa"]["fase"] == "oitavas" and proximo["rodada"] == 9

    res = temporada_service.avancar(sid)
    assert res["copa_jogada"]
    r = pos_jogo_service.ver(sid)
    jogo = next(j for j in res["copa"]["jogos"] if "Arsenal" in (j["mandante"], j["visitante"]))
    assert r["competicao"] == "copa" and r["copa"]["fase"] == "oitavas"
    assert (r["gols_mandante"], r["gols_visitante"]) == (jogo["gols_mandante"], jogo["gols_visitante"])
    assert r["copa"]["classificado"] == (jogo["vencedor"] == "Arsenal")
    assert r["copa"]["premio"] == (500_000 if r["copa"]["classificado"] else 0)
    assert bool(r["copa"]["penaltis"]) == (r["gols_mandante"] == r["gols_visitante"])
    # a copa agora guarda notas e números do jogo; a tabela da liga não muda
    assert r["tabela"] is None and r["estatisticas"] and r["atuacoes"]
    # a mensagem da copa é a do dia do jogo (a da rodada 8 tem outra data)
    assert any("copa" in m["corpo"] for m in r["mensagens"])
    assert not {m["id"] for m in r["mensagens"]} & {m["id"] for m in da_rodada_8["mensagens"]}
    # depois da copa, a rodada 9 da liga, no sábado
    assert r["proximo"]["rodada"] == 9 and r["proximo"]["copa"] is None

    temporada_service.avancar(sid)
    depois = pos_jogo_service.ver(sid)
    assert depois["competicao"] == "liga" and depois["rodada"] == 9


def test_jogo_da_copa_de_save_antigo_so_com_os_gols():
    """Saves anteriores à v2.2 não guardam notas nem números na copa."""
    import json
    sid = temporada_service.iniciar(seed=6, clube_usuario="Arsenal", ligas=TODAS_AS_LIGAS)
    for _ in range(9):
        temporada_service.avancar(sid)
    conn = conectar()
    try:
        with conn:
            estado = json.loads(conn.execute(
                "SELECT estado_json FROM simulacao WHERE id = ?", (sid,)).fetchone()[0])
            for j in estado["copa"]["fases"]["oitavas"]:
                for k in ("estatisticas", "eventos", "atuacoes"):
                    j.pop(k)
            conn.execute("UPDATE simulacao SET estado_json = ? WHERE id = ?",
                         (json.dumps(estado), sid))
    finally:
        conn.close()
    r = client.get(f"/simulacoes/{sid}/pos-jogo")
    assert r.status_code == 200
    r = r.json()
    assert r["estatisticas"] is None and r["atuacoes"] == []
    assert len(r["eventos"]) == r["gols_mandante"] + r["gols_visitante"]
    assert r["destaques"]["melhor_em_campo"] is None
