"""Conexão com o SQLite e criação do schema."""

import re
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

    # timeout: com vários técnicos jogando ao mesmo tempo, uma escrita
    # espera a outra terminar em vez de falhar com "database is locked"
    conn = sqlite3.connect(caminho, timeout=15)
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
        # calendário (v2.0)
        ("data_atual", "TEXT"),
        # decisões da partida transmitida em curso (v1.2)
        ("ao_vivo_json", "TEXT"),
        # plano de jogo carregado para a próxima partida (v1.2)
        ("plano_em_uso", "INTEGER"),
        # livres no fim da temporada (v1.6), JSON: o estado_json é apagado
        # ao concluir e a virada da carreira precisa deles
        ("livres_json", "TEXT"),
        # ligas do save (v1.6), JSON; NULL = só a Taldo (saves antigos)
        ("ligas", "TEXT"),
        # a copa entre as ligas no fim da temporada (v1.6), JSON: o
        # estado_json é apagado ao concluir; NULL = sem copa
        ("copa_json", "TEXT"),
        # dono do save (v2.1); NULL = save de antes das contas
        ("usuario_id", "INTEGER REFERENCES usuario(id) ON DELETE CASCADE"),
        # a peneira da base (v2.0) já aconteceu nesta temporada
        ("peneira_feita", "INTEGER NOT NULL DEFAULT 0"),
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
        # tamanho natural da torcida (v1.4); 0 = "sem registro" (o da seed)
        ("torcedores_base", "INTEGER NOT NULL DEFAULT 0"),
        # estádio (v1.5); 0 = "sem registro" (o da seed na virada)
        ("capacidade", "INTEGER NOT NULL DEFAULT 0"),
        ("ingresso", "TEXT NOT NULL DEFAULT 'normal'"),
        # liga do clube (v1.6); saves antigos só têm a Taldo
        ("liga", "TEXT NOT NULL DEFAULT 'taldo'"),
        # ampliação do estádio (v1.5)
        ("obra_lugares", "INTEGER NOT NULL DEFAULT 0"),
        ("obra_rodadas", "INTEGER NOT NULL DEFAULT 0"),
        ("lugares_ampliados", "INTEGER NOT NULL DEFAULT 0"),
        ("despesa_estadio", "INTEGER NOT NULL DEFAULT 0"),
        # olheiro profissional (v2.0)
        ("nivel_olheiro", "INTEGER NOT NULL DEFAULT 1"),
        ("despesa_olheiros", "INTEGER NOT NULL DEFAULT 0"),
        # categorias de base (v2.0)
        ("nivel_base", "INTEGER NOT NULL DEFAULT 1"),
        ("despesa_base", "INTEGER NOT NULL DEFAULT 0"),
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
        # lista de transferências e dispensa (v1.7)
        ("a_venda", "INTEGER NOT NULL DEFAULT 0"),
        ("livre", "INTEGER NOT NULL DEFAULT 0"),
        # papel no elenco (v1.7)
        ("papel", "TEXT"),
        ("humor", "TEXT NOT NULL DEFAULT 'contente'"),
        ("titularidades", "INTEGER NOT NULL DEFAULT 0"),
        ("jogos_disponivel", "INTEGER NOT NULL DEFAULT 0"),
        # vontade (v1.9): nomes de clubes; NULL em saves antigos
        ("formador", "TEXT"),
        ("clube_historia", "TEXT"),
        ("sonho", "TEXT"),
    ),
    # onde o técnico pôs cada titular no plano (v1.3), JSON
    "plano": (("posicionamento", "TEXT"),),
    # papel prometido na renovação (v1.7)
    "renovacao": (("papel", "TEXT"),),
    # opção de compra de um empréstimo (v1.7)
    "negociacao": (
        ("emprestimo_id", "INTEGER REFERENCES emprestimo(id) ON DELETE CASCADE"),
        # disputa pela contratação (v1.9)
        ("concorrente", "TEXT"),
        ("concorrente_salario", "INTEGER"),
        ("concorrente_fator", "REAL"),
    ),
    # oferta do clube do sonho do jogador (v1.9)
    "oferta_recebida": (("sonho", "INTEGER NOT NULL DEFAULT 0"),),
    "mensagem": (("data", "TEXT"),),   # o dia no calendário (v2.0)
    "partida": (
        ("finalizacoes_gol_mandante", "INTEGER NOT NULL DEFAULT 0"),
        ("finalizacoes_gol_visitante", "INTEGER NOT NULL DEFAULT 0"),
        ("escanteios_mandante", "INTEGER NOT NULL DEFAULT 0"),
        ("escanteios_visitante", "INTEGER NOT NULL DEFAULT 0"),
        ("acrescimos", "INTEGER"),
        ("publico", "INTEGER"),   # pagantes (v1.5)
    ),
}


def _refazer_transferencia(conn):
    """v1.7: a `transferencia` ganha `tipo` e os clubes passam a ser
    opcionais (livres e dispensas). O SQLite não tira o NOT NULL de uma
    coluna: a tabela é recriada com o CREATE do schema.sql e as linhas de
    antes são copiadas (todas compras e vendas)."""

    colunas = {r["name"] for r in conn.execute("PRAGMA table_info(transferencia)")}
    if "tipo" in colunas:
        return
    create = re.search(
        r"CREATE TABLE IF NOT EXISTS transferencia \(.*?\n\);",
        _SCHEMA.read_text(encoding="utf-8"), re.S,
    ).group(0)
    campos = "id, simulacao_id, rodada, jogador_id, de_clube_id, para_clube_id, valor"
    # a receita do SQLite para recriar tabela: chaves desligadas durante a
    # cópia (o PRAGMA não vale dentro de transação, daí o commit antes de
    # religar)
    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.execute("ALTER TABLE transferencia RENAME TO transferencia_antiga")
        conn.execute(create)
        conn.execute(
            f"INSERT INTO transferencia ({campos}) SELECT {campos} FROM transferencia_antiga"
        )
        conn.execute("DROP TABLE transferencia_antiga")
        conn.commit()
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def _migrar(conn):
    _refazer_transferencia(conn)
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
