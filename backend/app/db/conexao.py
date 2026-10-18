"""Conexão com o SQLite e criação do schema."""

import sqlite3
from pathlib import Path

from app.core.config import caminho_banco

_SCHEMA = Path(__file__).with_name("schema.sql")


def conectar():
    """Abre uma conexão com `row_factory` (linhas viram dict-like) e as
    foreign keys ligadas — o SQLite deixa desligado por padrão."""

    caminho = caminho_banco()

    if caminho != ":memory:":
        Path(caminho).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(caminho)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn=None):
    """Cria as tabelas se não existirem e aplica as migrações. Idempotente."""

    proprio = conn is None
    conn = conn or conectar()

    try:
        conn.executescript(_SCHEMA.read_text(encoding="utf-8"))
        _migrar(conn)
        conn.commit()
    finally:
        if proprio:
            conn.close()


# colunas adicionadas depois do schema inicial — o SQLite não tem
# "ALTER TABLE ... ADD COLUMN IF NOT EXISTS", então a gente checa antes
_COLUNAS_NOVAS = {
    "simulacao": (
        ("clube_usuario", "TEXT"),
        ("tatica", "TEXT"),
        ("formacao", "TEXT"),
        ("xi_preferido", "TEXT"),
        ("estado", "TEXT NOT NULL DEFAULT 'concluida'"),
        ("rodada_atual", "INTEGER"),
        ("estado_json", "TEXT"),
        ("carreira_id", "INTEGER REFERENCES carreira(id) ON DELETE SET NULL"),
        ("temporada", "INTEGER NOT NULL DEFAULT 1"),
        ("atualizada_em", "TEXT"),
        ("meta_posicao", "INTEGER"),
        ("ranking_forca", "INTEGER"),
        # decisões da partida transmitida em curso (v1.2)
        ("ao_vivo_json", "TEXT"),
        # plano de jogo carregado para a próxima partida (v1.2)
        ("plano_em_uso", "INTEGER"),
    ),
    "clube": tuple(
        (c, "INTEGER NOT NULL DEFAULT 0")
        for c in (
            "dinheiro_inicial", "dinheiro", "receita_tv",
            "receita_bilheteria", "receita_premiacao", "despesa_salarios",
            "receita_vendas", "despesa_compras",
        )
    ) + (
        ("historico_caixa", "TEXT NOT NULL DEFAULT '[]'"),
        # torcida (v1.4); saves antigos ficam com 0 = "sem registro"
        ("torcedores", "INTEGER NOT NULL DEFAULT 0"),
        ("torcedores_inicial", "INTEGER NOT NULL DEFAULT 0"),
        ("despesa_marketing", "INTEGER NOT NULL DEFAULT 0"),
    ),
    "jogador": (
        ("penaltis", "INTEGER NOT NULL DEFAULT 0"),
        ("penaltis_perdidos", "INTEGER NOT NULL DEFAULT 0"),
        ("faltas", "INTEGER NOT NULL DEFAULT 0"),
        ("potencial", "INTEGER NOT NULL DEFAULT 0"),
        ("contrato_anos", "INTEGER NOT NULL DEFAULT 0"),
        ("valor_mercado", "INTEGER NOT NULL DEFAULT 0"),
        ("salario", "INTEGER NOT NULL DEFAULT 0"),
        ("multa_rescisoria", "INTEGER"),
        ("numero", "INTEGER"),
        # posição específica (v1.3); secundarias é uma lista JSON
        ("funcao", "TEXT"),
        ("secundarias", "TEXT"),
        # fama (v1.4); saves antigos ficam com NULL = "sem registro"
        ("fama", "INTEGER"),
        ("temporadas_no_clube", "INTEGER"),
    ),
    # onde o técnico pôs cada titular no plano (v1.3), JSON
    "plano": (("posicionamento", "TEXT"),),
    "partida": (
        ("finalizacoes_gol_mandante", "INTEGER NOT NULL DEFAULT 0"),
        ("finalizacoes_gol_visitante", "INTEGER NOT NULL DEFAULT 0"),
        ("escanteios_mandante", "INTEGER NOT NULL DEFAULT 0"),
        ("escanteios_visitante", "INTEGER NOT NULL DEFAULT 0"),
        ("acrescimos", "INTEGER"),
    ),
}


def _migrar(conn):
    for tabela, colunas in _COLUNAS_NOVAS.items():
        existentes = {
            r["name"] for r in conn.execute(f"PRAGMA table_info({tabela})")
        }
        for nome, tipo in colunas:
            if nome not in existentes:
                conn.execute(
                    f"ALTER TABLE {tabela} ADD COLUMN {nome} {tipo}"
                )

    # saves de antes do autosave: a última mudança conhecida é a criação
    conn.execute(
        "UPDATE simulacao SET atualizada_em = criada_em "
        "WHERE atualizada_em IS NULL"
    )
