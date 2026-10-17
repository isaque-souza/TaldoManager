import pytest

from app.db.conexao import conectar
from app.repositories import atuacao_repository as atuacao_repo
from app.repositories import clube_repository as clube_repo
from app.repositories import jogador_repository as jogador_repo
from app.repositories import lance_repository as lance_repo
from app.repositories import partida_repository as partida_repo
from app.repositories import simulacao_repository as simulacao_repo


@pytest.fixture
def conn():
    c = conectar()
    yield c
    c.close()


def _clube(nome, posicao):
    return {
        "nome": nome, "pais": "Brasil", "posicao_final": posicao,
        "pontos": 90 - posicao, "jogos": 38, "vitorias": 20,
        "empates": 10, "derrotas": 8, "gols_marcados": 60, "gols_sofridos": 40,
        "dinheiro_inicial": 10_000_000, "dinheiro": 12_500_000,
        "receita_tv": 1_500_000, "receita_bilheteria": 2_000_000,
        "receita_premiacao": 9_000_000, "despesa_salarios": 10_000_000,
    }


def _jogador(nome, clube):
    return {
        "clube": clube, "nome": nome, "posicao": "Atacante", "idade": 25,
        "overall": 82, "partidas": 38, "gols": 15, "assistencias": 5,
        "nota_media": 7.4, "melhor_nota": 9.1, "pior_nota": 5.2,
        "melhor_em_campo": 8, "clean_sheets": 0, "hat_tricks": 1,
        "amarelos": 3, "vermelhos": 0,
        "penaltis": 2, "penaltis_perdidos": 1, "faltas": 12,
        "potencial": 84, "contrato_anos": 3,
        "valor_mercado": 3_000_000, "salario": 250_000,
    }


def test_ciclo_completo_de_escrita_e_leitura(conn):
    with conn:
        sid = simulacao_repo.criar(
            conn, seed=7, campeao="A FC", rodadas=38, criada_em="2026-01-01"
        )
        mapa = clube_repo.inserir(conn, sid, [_clube("A FC", 1), _clube("B FC", 2)])
        jogador_repo.inserir(
            conn, sid, mapa, [_jogador("Craque", "A FC"), _jogador("Outro", "B FC")]
        )
        partida_repo.inserir(conn, sid, mapa, [{
            "rodada": 1, "mandante": "A FC", "visitante": "B FC",
            "gols_mandante": 3, "gols_visitante": 1, "posse_mandante": 60,
            "finalizacoes_mandante": 12, "finalizacoes_visitante": 6,
            "finalizacoes_gol_mandante": 5, "finalizacoes_gol_visitante": 2,
            "escanteios_mandante": 7, "escanteios_visitante": 3,
        }])

    assert len(mapa) == 2

    clubes = clube_repo.listar_por_simulacao(conn, sid)
    assert [c["nome"] for c in clubes] == ["A FC", "B FC"]  # ordena por posição
    assert clubes[0]["dinheiro"] == 12_500_000
    assert clubes[0]["receita_premiacao"] == 9_000_000

    elenco = jogador_repo.listar_por_clube(conn, mapa["A FC"])
    assert len(elenco) == 1
    assert elenco[0]["nome"] == "Craque"
    assert elenco[0]["clube"] == "A FC"  # veio pelo JOIN
    assert elenco[0]["potencial"] == 84
    assert elenco[0]["valor_mercado"] == 3_000_000

    jogos = partida_repo.listar_por_clube(conn, mapa["B FC"])
    assert len(jogos) == 1
    assert jogos[0]["mandante_nome"] == "A FC"
    assert jogos[0]["visitante_nome"] == "B FC"


def test_deletar_simulacao_apaga_em_cascata(conn):
    with conn:
        sid = simulacao_repo.criar(
            conn, seed=None, campeao="A FC", rodadas=38, criada_em="2026-01-01"
        )
        mapa = clube_repo.inserir(conn, sid, [_clube("A FC", 1)])
        jogador_repo.inserir(conn, sid, mapa, [_jogador("Craque", "A FC")])

    with conn:
        assert simulacao_repo.deletar(conn, sid) is True

    assert clube_repo.listar_por_simulacao(conn, sid) == []
    assert jogador_repo.listar_por_simulacao(conn, sid) == []
    assert simulacao_repo.buscar(conn, sid) is None


def test_deletar_simulacao_inexistente(conn):
    with conn:
        assert simulacao_repo.deletar(conn, 999) is False


def test_lance_e_atuacao_round_trip_e_cascata(conn):
    partida = {
        "rodada": 1, "mandante": "A FC", "visitante": "B FC",
        "gols_mandante": 2, "gols_visitante": 1, "posse_mandante": 55,
        "finalizacoes_mandante": 10, "finalizacoes_visitante": 7,
        "finalizacoes_gol_mandante": 4, "finalizacoes_gol_visitante": 3,
        "escanteios_mandante": 6, "escanteios_visitante": 4,
        "eventos": [
            {"minuto": 12, "tipo": "gol", "clube": "A FC",
             "jogador": "Craque", "detalhe": None},
            {"minuto": 70, "tipo": "substituicao", "clube": "A FC",
             "jogador": "Craque", "detalhe": "sai Outro"},
        ],
        "atuacoes": [
            {"clube": "A FC", "jogador": "Craque", "titular": True,
             "entrou_min": None, "saiu_min": None, "gols": 2,
             "assistencias": 0, "nota": 8.5},
            {"clube": "B FC", "jogador": "Outro", "titular": False,
             "entrou_min": 60, "saiu_min": None, "gols": 1,
             "assistencias": 0, "nota": 7.0},
        ],
    }

    with conn:
        sid = simulacao_repo.criar(
            conn, seed=1, campeao="A FC", rodadas=1, criada_em="2026-01-01"
        )
        mapa = clube_repo.inserir(conn, sid, [_clube("A FC", 1), _clube("B FC", 2)])
        mapa_jog = jogador_repo.inserir(
            conn, sid, mapa, [_jogador("Craque", "A FC"), _jogador("Outro", "B FC")]
        )
        ids = partida_repo.inserir(conn, sid, mapa, [partida])
        lance_repo.inserir(conn, ids, mapa, mapa_jog, [partida])
        atuacao_repo.inserir(conn, ids, mapa, mapa_jog, [partida])

    assert isinstance(mapa_jog[("A FC", "Craque")], int)

    lances = lance_repo.listar_por_partida(conn, ids[0])
    assert [x["tipo"] for x in lances] == ["gol", "substituicao"]  # ordenado por minuto
    assert lances[0]["jogador_nome"] == "Craque"
    assert lances[1]["detalhe"] == "sai Outro"

    atu = atuacao_repo.listar_por_partida(conn, ids[0])
    assert len(atu) == 2
    assert atu[0]["titular"] == 1 and atu[0]["nota"] == 8.5

    log = atuacao_repo.listar_por_jogador(conn, mapa_jog[("A FC", "Craque")])
    assert len(log) == 1
    assert log[0]["rodada"] == 1
    assert log[0]["mandante_nome"] == "A FC"

    # apagar a simulação leva lances e atuações junto
    with conn:
        simulacao_repo.deletar(conn, sid)
    assert lance_repo.listar_por_partida(conn, ids[0]) == []
    assert atuacao_repo.listar_por_partida(conn, ids[0]) == []
