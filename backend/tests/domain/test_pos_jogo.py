"""Relatório pós-jogo (v2.2): as leituras do jogo, sem banco."""

from app.domain import pos_jogo


def _gol(minuto, clube, tipo="gol", jogador="X"):
    return {"minuto": minuto, "tipo": tipo, "jogador": jogador, "clube": clube}


def test_resultado_no_tempo_normal():
    assert pos_jogo.resultado(2, 1) == "vitoria"
    assert pos_jogo.resultado(1, 1) == "empate"
    assert pos_jogo.resultado(0, 3) == "derrota"


def test_expectativa_conta_o_mando():
    # mesma força: em casa ainda é equilibrado, a vantagem é só o mando
    assert pos_jogo.expectativa(80, 80, "casa") == {
        "nivel": "equilibrado", "texto": "Jogo equilibrado", "vantagem": 1.5,
    }
    # 1 ponto a mais em casa já é favorito; fora, ainda não
    assert pos_jogo.expectativa(81, 80, "casa")["nivel"] == "favorito"
    assert pos_jogo.expectativa(81, 80, "fora")["nivel"] == "equilibrado"
    assert pos_jogo.expectativa(79, 80, "fora")["nivel"] == "azarao"


def test_desempenho_compara_o_resultado_com_a_expectativa():
    assert pos_jogo.desempenho("vitoria", "favorito")["nivel"] == "esperado"
    assert pos_jogo.desempenho("empate", "favorito")["nivel"] == "abaixo"
    assert pos_jogo.desempenho("derrota", "favorito")["nivel"] == "muito_abaixo"
    assert pos_jogo.desempenho("vitoria", "azarao")["nivel"] == "muito_acima"
    assert pos_jogo.desempenho("empate", "azarao")["nivel"] == "acima"
    assert pos_jogo.desempenho("empate", "equilibrado")["nivel"] == "esperado"


def test_momento_decisivo_e_o_gol_que_pos_o_vencedor_a_frente_de_vez():
    # 1 x 0, 1 x 1, 2 x 1, 3 x 1 (mandante A): o decisivo é o 2º gol de A
    eventos = [_gol(10, "A", jogador="a1"), _gol(30, "B"), _gol(50, "A", jogador="a2"),
               _gol(80, "A", "penalti", "a3")]
    m = pos_jogo.momento_decisivo(eventos, 3, 1, "A")
    assert m["jogador"] == "a2" and m["minuto"] == 50 and m["tipo_momento"] == "gol_da_vitoria"
    # o visitante vencendo
    eventos = [_gol(10, "A"), _gol(60, "B", jogador="b1"), _gol(70, "B", jogador="b2")]
    assert pos_jogo.momento_decisivo(eventos, 1, 2, "A")["jogador"] == "b2"


def test_momento_decisivo_no_empate_e_no_zero_a_zero():
    eventos = [_gol(10, "A"), _gol(88, "B", jogador="b1")]
    m = pos_jogo.momento_decisivo(eventos, 1, 1, "A")
    assert m["jogador"] == "b1" and m["tipo_momento"] == "gol_do_empate"
    perdido = [{"minuto": 40, "tipo": "penalti_perdido", "jogador": "p", "clube": "A"}]
    assert pos_jogo.momento_decisivo(perdido, 0, 0, "A")["tipo_momento"] == "penalti_perdido"
    assert pos_jogo.momento_decisivo([], 0, 0, "A") is None


def _at(nome, clube, nota, titular=True, gols=0):
    return {"jogador": nome, "clube": clube, "titular": titular, "gols": gols,
            "assistencias": 0, "nota": nota}


def test_destaques_pelas_notas_do_motor():
    atuacoes = [_at("a", "Eu", 7.5), _at("b", "Eu", 6.1), _at("c", "Eu", 5.0, titular=False),
                _at("d", "Ele", 8.0), _at("e", "Eu", 7.5, gols=1)]
    d = pos_jogo.destaques(atuacoes, "Eu")
    assert d["melhor_em_campo"]["jogador"] == "d"
    # nota igual: desempata por gols + assistências
    assert d["melhor_do_time"]["jogador"] == "e"
    # o pior é entre os titulares
    assert d["pior_do_time"]["jogador"] == "b"
    assert pos_jogo.destaques([], "Eu")["melhor_em_campo"] is None


def test_tabela_pelos_criterios_do_motor():
    partidas = [
        {"mandante": "A", "visitante": "B", "gols_mandante": 2, "gols_visitante": 0},
        {"mandante": "C", "visitante": "D", "gols_mandante": 1, "gols_visitante": 1},
        {"mandante": "X", "visitante": "A", "gols_mandante": 5, "gols_visitante": 0},  # outra liga
    ]
    assert pos_jogo.tabela(["A", "B", "C", "D"], partidas) == {"A": 1, "C": 2, "D": 3, "B": 4}
    # sem jogos, a ordem dos clubes desempata
    assert pos_jogo.tabela(["B", "A"], []) == {"B": 1, "A": 2}
