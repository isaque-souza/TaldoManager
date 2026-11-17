"""Auditoria 02 — diagnóstico de integridade histórica, SOMENTE LEITURA.

Uso:
    python -I diagnostico_integridade.py /caminho/para/COPIA_do_backup.db [--json saida.json]

Roda numa CÓPIA local do banco. Nada aqui escreve:

1. o arquivo abre com `mode=ro&immutable=1` (o SQLite nem tenta travar ou
   criar -journal/-wal);
2. `PRAGMA query_only = ON`;
3. um authorizer do SQLite nega toda operação que não seja leitura
   (INSERT, UPDATE, DELETE, CREATE, DROP, ALTER, ATTACH, PRAGMA de escrita...);
4. recusa o banco padrão do projeto, o caminho de produção do container
   (`/dados/...`) e arquivos que não existem;
5. confere o SHA-256 do arquivo antes e depois.

Achado não é veredito: toda checagem lista seus falsos positivos
conhecidos (ver AUDITORIA/02_INTEGRIDADE_HISTORICA.md). As tabelas de conta
(`usuario`, `sessao`) não são lidas.

Só biblioteca padrão; não importa o código do jogo.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
BANCO_PADRAO = (RAIZ / "backend" / "data" / "database" / "taldo_manager.db").resolve()
AMOSTRA = 20   # linhas de exemplo por checagem


class Recusado(Exception):
    """O caminho não é uma cópia local aceitável."""


# ---------------------------------------------------------------------------
# conexão somente leitura
# ---------------------------------------------------------------------------

_LEITURA = {
    sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION,
    getattr(sqlite3, "SQLITE_RECURSIVE", 33),
}


def _autorizador(acao, arg1, arg2, banco, gatilho):
    if acao in _LEITURA:
        # as tabelas de conta ficam de fora (hash de senha e de sessão)
        if acao == sqlite3.SQLITE_READ and arg1 in ("usuario", "sessao"):
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


def validar_caminho(caminho):
    if not caminho:
        raise Recusado("informe o caminho de uma CÓPIA local do banco")
    p = Path(caminho).expanduser()
    if not p.is_file():
        raise Recusado(f"arquivo não encontrado: {p}")
    real = p.resolve()
    if real == BANCO_PADRAO:
        raise Recusado("este é o banco padrão do projeto; use uma cópia em outro lugar")
    if str(real).startswith("/dados/"):
        raise Recusado("caminho de produção do container; copie o backup para fora antes")
    return real


def sha256(caminho):
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def abrir(caminho):
    real = validar_caminho(caminho)
    conn = sqlite3.connect(f"file:{real}?mode=ro&immutable=1", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    conn.set_authorizer(_autorizador)
    return conn


# ---------------------------------------------------------------------------
# checagens
# ---------------------------------------------------------------------------

@dataclass
class Checagem:
    id: str
    titulo: str
    forca: str          # "forte": não deveria existir | "sinal": investigar
    sql: str = ""
    funcao: object = None
    falsos_positivos: str = ""


@dataclass
class Resultado:
    id: str
    titulo: str
    forca: str
    achados: int = 0
    amostra: list = field(default_factory=list)
    erro: str | None = None


SQL = [
    # --- R2: rodadas e viradas em dobro -----------------------------------
    Checagem(
        "C01", "Partida repetida (simulação, rodada, mandante)", "forte",
        """SELECT simulacao_id, rodada, mandante_id, COUNT(*) AS n, GROUP_CONCAT(id) AS partidas
           FROM partida GROUP BY simulacao_id, rodada, mandante_id HAVING n > 1""",
        falsos_positivos="nenhum conhecido: um clube manda um jogo por rodada",
    ),
    Checagem(
        "C02", "Clube em mais de um jogo na mesma rodada", "forte",
        """WITH j AS (
             SELECT simulacao_id, rodada, mandante_id AS clube_id, id FROM partida
             UNION ALL
             SELECT simulacao_id, rodada, visitante_id, id FROM partida)
           SELECT simulacao_id, rodada, clube_id, COUNT(*) AS n, GROUP_CONCAT(id) AS partidas
           FROM j GROUP BY simulacao_id, rodada, clube_id HAVING n > 1""",
        falsos_positivos="nenhum conhecido: a copa não grava em `partida`",
    ),
    Checagem(
        "C03", "Rodadas gravadas × rodada do save", "forte",
        """SELECT s.id AS simulacao_id, s.estado, s.rodada_atual, s.rodadas,
                  COUNT(DISTINCT p.rodada) AS rodadas_gravadas, MAX(p.rodada) AS maior_rodada
           FROM simulacao s LEFT JOIN partida p ON p.simulacao_id = s.id
           GROUP BY s.id
           HAVING (s.estado = 'em_andamento' AND rodadas_gravadas != s.rodada_atual - 1)
               OR (s.estado = 'concluida' AND rodadas_gravadas != s.rodadas)""",
        falsos_positivos="saves muito antigos de antes do `estado` (todos 'concluida' por padrão) "
                         "que não gravaram partidas",
    ),
    Checagem(
        "C04", "Partidas por rodada × clubes do save", "forte",
        """WITH n_clubes AS (SELECT simulacao_id, COUNT(*) AS clubes FROM clube GROUP BY simulacao_id),
                por_rodada AS (SELECT simulacao_id, rodada, COUNT(*) AS jogos
                               FROM partida GROUP BY simulacao_id, rodada)
           SELECT r.simulacao_id, r.rodada, r.jogos, c.clubes / 2 AS esperado
           FROM por_rodada r JOIN n_clubes c USING (simulacao_id)
           WHERE r.jogos != c.clubes / 2""",
        falsos_positivos="liga com número ímpar de clubes (folga) — hoje todas têm 20",
    ),
    Checagem(
        "C05", "Temporada repetida dentro de uma carreira", "forte",
        """SELECT carreira_id, temporada, COUNT(*) AS n, GROUP_CONCAT(id) AS simulacoes
           FROM simulacao WHERE carreira_id IS NOT NULL
           GROUP BY carreira_id, temporada HAVING n > 1""",
        falsos_positivos="nenhum conhecido: `sucessora()` supõe uma por temporada",
    ),
    Checagem(
        "C06", "Carreira com buraco ou sem a temporada 1", "sinal",
        """SELECT carreira_id, MIN(temporada) AS primeira, MAX(temporada) AS ultima,
                  COUNT(DISTINCT temporada) AS distintas, GROUP_CONCAT(id) AS simulacoes
           FROM simulacao WHERE carreira_id IS NOT NULL
           GROUP BY carreira_id HAVING primeira != 1 OR distintas != ultima""",
        falsos_positivos="o técnico apagou uma temporada antiga da carreira (apagar é permitido)",
    ),
    Checagem(
        "C07", "Carreira com mais de uma temporada em andamento", "forte",
        """SELECT carreira_id, COUNT(*) AS n, GROUP_CONCAT(id) AS simulacoes
           FROM simulacao WHERE carreira_id IS NOT NULL AND estado = 'em_andamento'
           GROUP BY carreira_id HAVING n > 1""",
        falsos_positivos="nenhum conhecido",
    ),
    Checagem(
        "C08", "Carreira sem nenhuma temporada", "sinal",
        """SELECT c.id AS carreira_id, c.clube_usuario, c.criada_em
           FROM carreira c LEFT JOIN simulacao s ON s.carreira_id = c.id
           WHERE s.id IS NULL""",
        falsos_positivos="todas as temporadas da carreira foram apagadas pelo técnico "
                         "(o `ON DELETE SET NULL` deixa a carreira para trás)",
    ),
    Checagem(
        "C09", "Temporada com clube diferente do da carreira", "sinal",
        """SELECT s.id AS simulacao_id, s.carreira_id, s.clube_usuario, c.clube_usuario AS da_carreira
           FROM simulacao s JOIN carreira c ON c.id = s.carreira_id
           WHERE s.clube_usuario IS NOT c.clube_usuario""",
        falsos_positivos="clube renomeado numa migração de nomes",
    ),
    # --- estado do save -----------------------------------------------------
    Checagem(
        "C10", "Estado do save incoerente", "forte",
        """SELECT id AS simulacao_id, estado, rodada_atual,
                  estado_json IS NOT NULL AS tem_blob, campeao
           FROM simulacao
           WHERE (estado = 'em_andamento' AND (estado_json IS NULL OR rodada_atual IS NULL OR campeao != ''))
              OR (estado = 'concluida' AND (estado_json IS NOT NULL OR campeao = ''))
              OR estado NOT IN ('em_andamento', 'concluida')""",
        falsos_positivos="temporada neutra concluída sem campeão gravado em saves muito antigos",
    ),
    # --- duplicidades por nome (R4) ------------------------------------------
    Checagem(
        "C11", "Jogador com nome repetido no mesmo save", "forte",
        """SELECT simulacao_id, nome, COUNT(*) AS n, GROUP_CONCAT(id) AS jogadores,
                  GROUP_CONCAT(livre) AS livres
           FROM jogador GROUP BY simulacao_id, nome HAVING n > 1""",
        falsos_positivos="nenhum: o UPDATE por (simulacao_id, nome) atinge as duas linhas",
    ),
    Checagem(
        "C12", "Clube com nome repetido no mesmo save", "forte",
        """SELECT simulacao_id, nome, COUNT(*) AS n FROM clube
           GROUP BY simulacao_id, nome HAVING n > 1""",
        falsos_positivos="nenhum conhecido",
    ),
    Checagem(
        "C13", "Jovem da base com nome de jogador do save, ou repetido", "sinal",
        """SELECT b.simulacao_id, b.nome, 'jogador do save' AS conflito FROM jovem_base b
           JOIN jogador j ON j.simulacao_id = b.simulacao_id AND j.nome = b.nome
           UNION ALL
           SELECT simulacao_id, nome, 'repetido na base' FROM jovem_base
           GROUP BY simulacao_id, nome HAVING COUNT(*) > 1""",
        falsos_positivos="nenhum conhecido; ao promover, viraria C11",
    ),
    # --- partidas: filhos repetidos e referências cruzadas -------------------
    Checagem(
        "C14", "Atuação repetida (partida, jogador)", "forte",
        """SELECT partida_id, jogador_id, COUNT(*) AS n FROM atuacao
           GROUP BY partida_id, jogador_id HAVING n > 1""",
        falsos_positivos="nenhum conhecido: uma atuação por jogador por jogo",
    ),
    Checagem(
        "C15", "Lance idêntico repetido na mesma partida", "sinal",
        """SELECT l.partida_id, l.minuto, l.tipo, l.jogador_id, l.detalhe, COUNT(*) AS n FROM lance l
           GROUP BY l.partida_id, l.minuto, l.tipo, l.jogador_id, l.detalhe
           HAVING n > 1
              -- o motor pode dar dois amarelos ao mesmo jogador no mesmo minuto (com ou sem
              -- expulsão: partida.py:682-685). Não é gravação dupla; fica de fora
              AND NOT (l.tipo = 'cartao_amarelo' AND n = 2)""",
        falsos_positivos="dois amarelos no mesmo minuto (o motor faz isso; já excluído); "
                         "dois lances iguais legítimos no mesmo minuto",
    ),
    Checagem(
        "C16", "Partida, lance ou atuação apontando para outro save", "forte",
        """SELECT 'partida' AS tabela, p.id, p.simulacao_id, c.simulacao_id AS save_do_clube
           FROM partida p JOIN clube c ON c.id IN (p.mandante_id, p.visitante_id)
           WHERE c.simulacao_id != p.simulacao_id
           UNION ALL
           SELECT 'atuacao', a.id, p.simulacao_id, j.simulacao_id
           FROM atuacao a JOIN partida p ON p.id = a.partida_id JOIN jogador j ON j.id = a.jogador_id
           WHERE j.simulacao_id != p.simulacao_id
           UNION ALL
           SELECT 'lance', l.id, p.simulacao_id, j.simulacao_id
           FROM lance l JOIN partida p ON p.id = l.partida_id JOIN jogador j ON j.id = l.jogador_id
           WHERE j.simulacao_id != p.simulacao_id""",
        falsos_positivos="nenhum conhecido",
    ),
    # --- tabela × partidas -----------------------------------------------------
    Checagem(
        "C17", "Jogos e pontos do clube × partidas gravadas", "forte",
        """WITH r AS (
             SELECT simulacao_id, mandante_id AS clube_id,
                    gols_mandante > gols_visitante AS v, gols_mandante = gols_visitante AS e
             FROM partida
             UNION ALL
             SELECT simulacao_id, visitante_id,
                    gols_visitante > gols_mandante, gols_mandante = gols_visitante
             FROM partida)
           SELECT c.simulacao_id, c.id AS clube_id, c.nome, c.jogos, COUNT(r.clube_id) AS jogos_gravados,
                  c.pontos, COALESCE(SUM(3 * r.v + r.e), 0) AS pontos_gravados
           FROM clube c LEFT JOIN r ON r.clube_id = c.id
           GROUP BY c.id
           HAVING c.jogos != jogos_gravados OR c.pontos != pontos_gravados""",
        falsos_positivos="saves antigos com regra de pontos diferente; "
                         "a tabela de clubes não guarda a copa, só a liga",
    ),
    Checagem(
        "C18", "Gols do jogador × atuações gravadas", "sinal",
        """SELECT j.simulacao_id, j.id AS jogador_id, j.nome, j.gols, SUM(a.gols) AS gols_gravados,
                  j.partidas, COUNT(a.id) AS atuacoes
           FROM jogador j JOIN atuacao a ON a.jogador_id = j.id
           GROUP BY j.id
           HAVING j.gols != gols_gravados""",
        falsos_positivos="gols de saves anteriores à tabela `atuacao`; zero achados na base limpa dos testes",
    ),
    # --- outras tabelas que podem duplicar --------------------------------------
    Checagem(
        "C19", "Transferência repetida", "sinal",
        """SELECT simulacao_id, rodada, jogador_id, de_clube_id, para_clube_id, tipo, COUNT(*) AS n
           FROM transferencia
           GROUP BY simulacao_id, rodada, jogador_id, de_clube_id, para_clube_id, tipo HAVING n > 1""",
        falsos_positivos="ida e volta do mesmo jogador na mesma janela com os mesmos clubes",
    ),
    Checagem(
        "C20", "Oferta aberta repetida (jogador, clube)", "sinal",
        """SELECT simulacao_id, jogador_id, clube, COUNT(*) AS n, GROUP_CONCAT(id) AS ofertas
           FROM oferta_recebida WHERE status = 'aberta'
           GROUP BY simulacao_id, jogador_id, clube HAVING n > 1""",
        falsos_positivos="nenhum conhecido",
    ),
    Checagem(
        "C21", "Negociação aberta repetida para o mesmo jogador", "sinal",
        """SELECT simulacao_id, jogador, COUNT(*) AS n, GROUP_CONCAT(id) AS negociacoes
           FROM negociacao WHERE status = 'aberta'
           GROUP BY simulacao_id, jogador HAVING n > 1""",
        falsos_positivos="compra e empréstimo do mesmo jogador abertos juntos, se a regra permitir",
    ),
    Checagem(
        "C22", "Mais de um plano padrão no save", "forte",
        """SELECT simulacao_id, COUNT(*) AS n FROM plano WHERE padrao = 1
           GROUP BY simulacao_id HAVING n > 1""",
        falsos_positivos="nenhum conhecido",
    ),
    Checagem(
        "C23", "Movimento de virada repetido", "sinal",
        """SELECT simulacao_id, tipo, jogador, clube, COUNT(*) AS n FROM movimento_virada
           GROUP BY simulacao_id, tipo, jogador, clube HAVING n > 1""",
        falsos_positivos="nenhum conhecido",
    ),
    Checagem(
        "C24", "Mensagem idêntica repetida na mesma rodada", "sinal",
        """SELECT simulacao_id, rodada, setor, assunto, COUNT(*) AS n FROM mensagem
           GROUP BY simulacao_id, rodada, setor, assunto, corpo HAVING n > 1""",
        falsos_positivos="dois avisos legítimos com o mesmo texto (ex.: duas lesões iguais)",
    ),
]


# ---------------------------------------------------------------------------
# blob (estado_json) × tabelas
# ---------------------------------------------------------------------------

CAMPOS_CLUBE = ("pontos", "gols_marcados", "gols_sofridos", "vitorias", "empates",
                "derrotas", "dinheiro", "torcedores", "capacidade", "nivel_base",
                "nivel_olheiro")
CAMPOS_JOGADOR = ("gols", "assistencias", "partidas", "amarelos", "vermelhos",
                  "overall", "idade", "salario", "contrato_anos", "numero")


def _colunas(conn, tabela):
    """Nomes reais das colunas (Auditoria 03, achado 9).

    PRAGMA é negado pelo authorizer; `SELECT * ... LIMIT 0` só lê o esquema e
    devolve os nomes em `cursor.description`, sem confundir `idade` com
    `cidade` nem com texto de um CHECK. Tabela ausente → conjunto vazio."""
    if not tabela.isidentifier():
        raise ValueError(f"nome de tabela inesperado: {tabela!r}")
    existe = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (tabela,)
    ).fetchone()
    if not existe:
        return set()
    cur = conn.execute(f'SELECT * FROM "{tabela}" LIMIT 0')
    return {d[0] for d in cur.description}


def _rng_ok(rng):
    return (isinstance(rng, list) and len(rng) == 3
            and isinstance(rng[1], (list, tuple)) and len(rng[1]) == 625)


def _blob_de_um_save(conn, s, tem, temj, tem_livre):
    sid = s["id"]
    achados = []
    try:
        blob = json.loads(s["estado_json"])
    except ValueError as e:
        return [{"simulacao_id": sid, "tipo": "blob ilegível", "detalhe": str(e)[:120]}]
    if not isinstance(blob, dict):
        return [{"simulacao_id": sid, "tipo": "blob ilegível",
                 "detalhe": f"o topo do JSON é {type(blob).__name__}, não objeto"}]

    if blob.get("rodada") != s["rodada_atual"]:
        achados.append({"simulacao_id": sid, "tipo": "rodada",
                        "blob": blob.get("rodada"), "tabela": s["rodada_atual"]})

    if not _rng_ok(blob.get("rng")):
        achados.append({"simulacao_id": sid, "tipo": "rng malformado"})

    clubes = {r["nome"]: r for r in conn.execute(
        "SELECT * FROM clube WHERE simulacao_id = ?", (sid,))}
    clubes_blob = blob.get("clubes", {})
    if not isinstance(clubes_blob, dict):
        achados.append({"simulacao_id": sid, "tipo": "blob ilegível",
                        "detalhe": "'clubes' não é objeto"})
        return achados
    nomes_blob = set(clubes_blob)
    if nomes_blob != set(clubes):
        achados.append({"simulacao_id": sid, "tipo": "clubes",
                        "so_no_blob": sorted(nomes_blob - set(clubes))[:10],
                        "so_na_tabela": sorted(set(clubes) - nomes_blob)[:10]})

    # chave (clube, nome): homônimos em clubes diferentes não se confundem
    # (Auditoria 03, achado 10). Homônimos no MESMO clube não têm como ser
    # casados com o blob (lá o jogador é chave de um objeto): ficam como
    # "jogador ambíguo", sem comparação — e o C11 já os acusa.
    filtro = " AND j.livre = 0" if tem_livre else ""
    elenco_tab = {}
    jogadores_tab = {}
    ambiguos = set()
    for r in conn.execute(
        "SELECT j.*, c.nome AS clube FROM jogador j JOIN clube c ON c.id = j.clube_id "
        "WHERE j.simulacao_id = ?" + filtro, (sid,)
    ):
        chave = (r["clube"], r["nome"])
        elenco_tab.setdefault(r["clube"], set()).add(r["nome"])
        if chave in jogadores_tab:
            ambiguos.add(chave)
        jogadores_tab[chave] = r
    for clube, nome in sorted(ambiguos):
        achados.append({"simulacao_id": sid, "tipo": "jogador ambíguo", "clube": clube,
                        "jogador": nome, "detalhe": "mesmo nome duas vezes no clube; não comparado"})

    for nome, dados in clubes_blob.items():
        c = clubes.get(nome)
        if not isinstance(dados, dict):   # 3ª revisão: não some do relatório
            achados.append({"simulacao_id": sid, "tipo": "blob ilegível", "clube": nome,
                            "detalhe": f"o clube é {type(dados).__name__}, não objeto"})
            continue
        if c is None:
            continue
        for campo in CAMPOS_CLUBE:
            if tem[campo] and campo in dados and dados[campo] != c[campo]:
                achados.append({"simulacao_id": sid, "tipo": "clube", "clube": nome,
                                "campo": campo, "blob": dados[campo], "tabela": c[campo]})
        # tipo errado num clube vira achado desse clube; o resto do save segue
        # sendo comparado (2ª revisão)
        elenco_blob, jogadores_blob = dados.get("elenco"), dados.get("jogadores", {})
        for chave_blob, valor, tipo in (("elenco", elenco_blob, list), ("jogadores", jogadores_blob, dict)):
            if valor is not None and not isinstance(valor, tipo):
                achados.append({"simulacao_id": sid, "tipo": "blob ilegível", "clube": nome,
                                "detalhe": f"'{chave_blob}' não é {tipo.__name__}"})
        if not isinstance(elenco_blob, list):
            elenco_blob = None
        if not isinstance(jogadores_blob, dict):
            jogadores_blob = {}
        if elenco_blob is not None and set(map(str, elenco_blob)) != elenco_tab.get(nome, set()):
            no_blob = set(map(str, elenco_blob))
            na_tab = elenco_tab.get(nome, set())
            achados.append({"simulacao_id": sid, "tipo": "elenco", "clube": nome,
                            "so_no_blob": sorted(no_blob - na_tab)[:10],
                            "so_na_tabela": sorted(na_tab - no_blob)[:10]})
        for jnome, campos in jogadores_blob.items():
            chave = (nome, jnome)
            if chave in ambiguos:
                continue
            j = jogadores_tab.get(chave)
            if j is None or not isinstance(campos, dict):
                continue
            for campo in CAMPOS_JOGADOR:
                if temj[campo] and campo in campos and campos[campo] != j[campo]:
                    achados.append({"simulacao_id": sid, "tipo": "jogador", "clube": nome,
                                    "jogador": jnome, "campo": campo,
                                    "blob": campos[campo], "tabela": j[campo]})
    return achados


def blob_x_tabelas(conn):
    achados = []
    col_clube, col_jogador = _colunas(conn, "clube"), _colunas(conn, "jogador")
    tem = {c: c in col_clube for c in CAMPOS_CLUBE}
    temj = {c: c in col_jogador for c in CAMPOS_JOGADOR}
    tem_livre = "livre" in col_jogador
    # um blob por vez (2ª revisão): um backup com muitos saves grandes não
    # vai inteiro para a memória
    ids = [r[0] for r in conn.execute(
        "SELECT id FROM simulacao WHERE estado = 'em_andamento' AND estado_json IS NOT NULL")]
    for sid in ids:
        s = conn.execute("SELECT id, rodada_atual, estado_json FROM simulacao WHERE id = ?",
                         (sid,)).fetchone()
        try:
            achados += _blob_de_um_save(conn, s, tem, temj, tem_livre)
        except sqlite3.DatabaseError:
            raise   # problema do banco (tabela/coluna ausente, authorizer): a checagem toda
        except Exception as e:   # noqa: BLE001 — um save estranho não derruba os outros (achado 8)
            achados.append({"simulacao_id": s["id"], "tipo": "blob inesperado",
                            "detalhe": f"{type(e).__name__}: {e}"[:160]})
    return achados


FUNCOES = [
    Checagem(
        "B01", "Estado serializado (estado_json) × tabelas", "forte",
        funcao=blob_x_tabelas,
        falsos_positivos="campos que o blob guarda em escala diferente da tabela (nenhum entre os "
                         "comparados); saves antigos sem algumas chaves (são pulados)",
    ),
]

TODAS = SQL + FUNCOES


# ---------------------------------------------------------------------------
# execução
# ---------------------------------------------------------------------------

def _linha(r):
    return {k: r[k] for k in r.keys()}


def executar(conn, checagens=TODAS):
    resultados = []
    for c in checagens:
        res = Resultado(c.id, c.titulo, c.forca)
        try:
            if c.funcao is not None:
                linhas = c.funcao(conn)
            else:
                linhas = [_linha(r) for r in conn.execute(c.sql)]
            res.achados = len(linhas)
            res.amostra = linhas[:AMOSTRA]
        except sqlite3.DatabaseError as e:
            # banco antigo sem a tabela/coluna, ou o authorizer negou
            res.erro = f"{type(e).__name__}: {e}"
        except Exception as e:   # noqa: BLE001 — uma checagem quebrada não derruba as outras (achado 8)
            res.erro = f"erro na checagem: {type(e).__name__}: {e}"
        resultados.append(res)
    return resultados


def diagnosticar(caminho):
    """Valida o caminho, roda tudo e confere que o arquivo não mudou."""
    real = validar_caminho(caminho)
    antes = sha256(real)
    conn = abrir(real)
    try:
        versao = conn.execute("SELECT sqlite_version()").fetchone()[0]
        resultados = executar(conn)
    finally:
        conn.close()
    depois = sha256(real)
    if antes != depois:   # não deveria acontecer nunca
        raise RuntimeError("o arquivo mudou durante o diagnóstico")
    return {"arquivo": str(real), "sha256": antes, "sqlite": versao,
            "resultados": [r.__dict__ for r in resultados]}


def _imprimir(rel):
    print(f"arquivo: {rel['arquivo']}\nsha256:  {rel['sha256']} (igual antes e depois)\n")
    for r in rel["resultados"]:
        if r["erro"]:
            estado = f"não rodou ({r['erro']})"
        elif r["achados"]:
            estado = f"{r['achados']} achado(s)"
        else:
            estado = "ok"
        print(f"[{r['id']}] {r['titulo']} ({r['forca']}): {estado}")
        for linha in r["amostra"][:5]:
            print(f"      {linha}")
    fortes = sum(1 for r in rel["resultados"] if r["forca"] == "forte" and r["achados"])
    print(f"\n{fortes} checagem(ns) forte(s) com achados. Achado não é veredito: "
          "leia os falsos positivos de cada uma.")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("banco", help="caminho de uma CÓPIA local do banco")
    ap.add_argument("--json", help="grava o relatório completo neste arquivo")
    args = ap.parse_args(argv)
    try:
        rel = diagnosticar(args.banco)
    except Recusado as e:
        print(f"recusado: {e}", file=sys.stderr)
        return 2
    _imprimir(rel)
    if args.json:
        Path(args.json).write_text(json.dumps(rel, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
