"""Relatório pós-jogo (v2.2): as leituras do jogo, sem banco."""

from app.domain import pos_jogo


def test_resultado_no_tempo_normal():
    assert pos_jogo.resultado(2, 1) == "vitoria"
    assert pos_jogo.resultado(1, 1) == "empate"
    assert pos_jogo.resultado(0, 3) == "derrota"


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
