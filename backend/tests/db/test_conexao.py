from app.db.conexao import conectar, init_db


def test_init_db_cria_as_tabelas():
    init_db()  # idempotente — o conftest já chamou uma vez

    conn = conectar()
    try:
        tabelas = {
            r["name"]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    finally:
        conn.close()

    assert {"simulacao", "clube", "jogador", "partida"} <= tabelas


def test_foreign_keys_ligadas():
    conn = conectar()
    try:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        conn.close()


def test_linhas_vem_como_dict():
    conn = conectar()
    try:
        conn.execute(
            "INSERT INTO simulacao (seed, criada_em, campeao, rodadas) "
            "VALUES (1, '2026-01-01', 'FC Taldo', 38)"
        )
        linha = conn.execute("SELECT * FROM simulacao").fetchone()
        assert linha["campeao"] == "FC Taldo"
        assert linha["seed"] == 1
    finally:
        conn.close()


def test_migracao_adiciona_colunas_de_temporada_em_andamento(tmp_path, monkeypatch):
    import sqlite3

    caminho = tmp_path / "antigo.db"
    monkeypatch.setenv("TALDO_DB", str(caminho))

    # simula um banco antigo: tabela simulacao sem as colunas novas
    velho = sqlite3.connect(caminho)
    velho.execute(
        "CREATE TABLE simulacao (id INTEGER PRIMARY KEY, seed INTEGER, "
        "criada_em TEXT NOT NULL, campeao TEXT NOT NULL, rodadas INTEGER NOT NULL)"
    )
    velho.execute(
        "INSERT INTO simulacao (seed, criada_em, campeao, rodadas) "
        "VALUES (1, '2026-01-01', 'FC Taldo', 38)"
    )
    velho.commit()
    velho.close()

    init_db()

    conn = conectar()
    try:
        colunas = {r["name"] for r in conn.execute("PRAGMA table_info(simulacao)")}
        assert {"estado", "rodada_atual", "estado_json"} <= colunas

        linha = conn.execute("SELECT * FROM simulacao WHERE id = 1").fetchone()
        assert linha["estado"] == "concluida"
        assert linha["rodada_atual"] is None
        # autosave (v0.9): saves antigos assumem a criação como última mudança
        assert linha["atualizada_em"] == "2026-01-01"
    finally:
        conn.close()


def test_migracao_adiciona_colunas_de_disciplina_ao_jogador(tmp_path, monkeypatch):
    import sqlite3

    caminho = tmp_path / "antigo_jogador.db"
    monkeypatch.setenv("TALDO_DB", str(caminho))

    velho = sqlite3.connect(caminho)
    velho.executescript(
        """
        CREATE TABLE simulacao (id INTEGER PRIMARY KEY, seed INTEGER,
            criada_em TEXT NOT NULL, campeao TEXT NOT NULL, rodadas INTEGER NOT NULL);
        CREATE TABLE clube (id INTEGER PRIMARY KEY, simulacao_id INTEGER,
            nome TEXT, pais TEXT, posicao_final INTEGER, pontos INTEGER, jogos INTEGER,
            vitorias INTEGER, empates INTEGER, derrotas INTEGER,
            gols_marcados INTEGER, gols_sofridos INTEGER);
        CREATE TABLE jogador (id INTEGER PRIMARY KEY, simulacao_id INTEGER,
            clube_id INTEGER, nome TEXT, posicao TEXT, idade INTEGER, overall INTEGER,
            partidas INTEGER, gols INTEGER, assistencias INTEGER, nota_media REAL,
            melhor_nota REAL, pior_nota REAL, melhor_em_campo INTEGER,
            clean_sheets INTEGER, hat_tricks INTEGER, amarelos INTEGER, vermelhos INTEGER);
        INSERT INTO jogador (nome, amarelos, vermelhos) VALUES ('Velho', 4, 1);
        """
    )
    velho.commit()
    velho.close()

    init_db()

    conn = conectar()
    try:
        colunas = {r["name"] for r in conn.execute("PRAGMA table_info(jogador)")}
        assert {"penaltis", "penaltis_perdidos", "faltas"} <= colunas
        linha = conn.execute("SELECT * FROM jogador WHERE nome = 'Velho'").fetchone()
        assert linha["faltas"] == 0
        assert linha["penaltis"] == 0
    finally:
        conn.close()


def test_migracao_adiciona_stats_avancadas_a_partida(tmp_path, monkeypatch):
    import sqlite3

    caminho = tmp_path / "antiga_partida.db"
    monkeypatch.setenv("TALDO_DB", str(caminho))

    velho = sqlite3.connect(caminho)
    velho.executescript(
        """
        CREATE TABLE simulacao (id INTEGER PRIMARY KEY, seed INTEGER,
            criada_em TEXT NOT NULL, campeao TEXT NOT NULL, rodadas INTEGER NOT NULL);
        CREATE TABLE clube (id INTEGER PRIMARY KEY, simulacao_id INTEGER,
            nome TEXT, pais TEXT, posicao_final INTEGER, pontos INTEGER, jogos INTEGER,
            vitorias INTEGER, empates INTEGER, derrotas INTEGER,
            gols_marcados INTEGER, gols_sofridos INTEGER);
        CREATE TABLE partida (id INTEGER PRIMARY KEY, simulacao_id INTEGER,
            rodada INTEGER, mandante_id INTEGER, visitante_id INTEGER,
            gols_mandante INTEGER, gols_visitante INTEGER, posse_mandante INTEGER,
            finalizacoes_mandante INTEGER, finalizacoes_visitante INTEGER);
        INSERT INTO partida (rodada, finalizacoes_mandante, finalizacoes_visitante)
            VALUES (1, 10, 8);
        """
    )
    velho.commit()
    velho.close()

    init_db()

    conn = conectar()
    try:
        colunas = {r["name"] for r in conn.execute("PRAGMA table_info(partida)")}
        assert {
            "finalizacoes_gol_mandante", "finalizacoes_gol_visitante",
            "escanteios_mandante", "escanteios_visitante", "acrescimos",
        } <= colunas
        linha = conn.execute("SELECT * FROM partida WHERE id = 1").fetchone()
        assert linha["escanteios_mandante"] == 0
        assert linha["finalizacoes_gol_visitante"] == 0
    finally:
        conn.close()
