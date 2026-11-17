"""Auditoria 02 — o diagnóstico somente leitura
(`AUDITORIA/scripts/diagnostico_integridade.py`).

Valida as consultas nos dois sentidos, sempre no SQLite temporário do teste:
- numa base LIMPA, feita pelos fluxos normais do jogo, as checagens não
  acusam nada (sem falso positivo nesses fluxos);
- numa base com as duplicatas do R2 (montadas por SQL no banco temporário,
  sem depender de o R2 existir), as checagens certas acusam.
E as proteções: recusa de caminhos, authorizer e arquivo intacto.
"""

import importlib.util
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

import pytest

from app.db.conexao import conectar
from app.repositories import carreira_repository as carreira_repo
from app.repositories import simulacao_repository as simulacao_repo
from app.services import (
    carreira_service, mercado_service, simulacao_service, temporada_service,
)
from tests.negociar import oferecer

_SCRIPT = Path(__file__).resolve().parents[3] / "AUDITORIA" / "scripts" / "diagnostico_integridade.py"
_spec = importlib.util.spec_from_file_location("diagnostico_integridade", _SCRIPT)
diag = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = diag   # o dataclass procura o módulo aqui
_spec.loader.exec_module(diag)


def _banco():
    return os.environ["TALDO_DB"]


def _achados(rel):
    return {r["id"]: r for r in rel["resultados"]}


def _com_achados(rel):
    return {r["id"]: r["amostra"][:3] for r in rel["resultados"] if r["achados"]}


def _clube():
    return simulacao_service.listar_clubes()[0]["nome"]


# ---------------------------------------------------------------------------
# base limpa: os fluxos normais não acusam nada
# ---------------------------------------------------------------------------

def _base_limpa(cargo_garantido):
    # temporada em andamento, 3 rodadas
    a = temporada_service.iniciar(seed=5, clube_usuario=_clube())
    for _ in range(3):
        temporada_service.avancar(a)
    # venda aceita (regrava o blob por `_Contexto.gravar`) e mais uma rodada
    b = temporada_service.iniciar(seed=11, clube_usuario="Real Taldo")
    m = mercado_service.ver_mercado(b)
    vendido = next(f for f in m["elenco"] if f["bloqueio"] is None)
    comprador = next(f["clube"] for f in m["disponiveis"] if not f["rival"])
    mercado_service.aceitar_oferta(b, oferecer(b, vendido["jogador_id"], comprador, 1_000_000))
    temporada_service.avancar(b)
    # temporada inteira de uma vez, virada para a carreira e 2 rodadas
    c = simulacao_service.salvar_temporada(seed=3, clube_usuario=_clube())
    nova = carreira_service.proxima_temporada(c)["simulacao_id"]
    temporada_service.avancar(nova)
    temporada_service.avancar(nova)


def test_base_limpa_nao_tem_achado_forte(cargo_garantido):
    _base_limpa(cargo_garantido)
    rel = diag.diagnosticar(_banco())
    erros = {r["id"]: r["erro"] for r in rel["resultados"] if r["erro"]}
    assert not erros, erros
    fortes = {k: v for k, v in _com_achados(rel).items()
              if _achados(rel)[k]["forca"] == "forte"}
    assert not fortes, fortes


def test_base_limpa_sinais(cargo_garantido):
    """Os 'sinais' também devem ficar quietos nos fluxos normais; o que
    acusar aqui é falso positivo a documentar."""
    _base_limpa(cargo_garantido)
    rel = diag.diagnosticar(_banco())
    sinais = {k: v for k, v in _com_achados(rel).items()
              if _achados(rel)[k]["forca"] == "sinal"}
    assert not sinais, sinais


# ---------------------------------------------------------------------------
# base com as duplicatas do R2 (Auditoria 03, achados 5 e 7)
#
# As duplicatas são montadas por SQL direto no banco TEMPORÁRIO, a partir de
# um save jogado pelos fluxos normais: os testes conferem o DIAGNÓSTICO, não
# dependem de o R2 existir. Quando o R2 for corrigido (trava, checagem de
# versão ou índice UNIQUE), estes testes continuam valendo: um backup antigo
# tem as duplicatas mesmo que o código novo não as produza mais.
# `_como_backup_antigo` tira os UNIQUE que uma correção venha a criar — em
# índice (`CREATE UNIQUE INDEX`) ou dentro da própria tabela (reconstrução
# como `_refazer_transferencia`) —, deixando o esquema de um backup de antes.
# ---------------------------------------------------------------------------

_TABELAS_DO_R2 = ("partida", "lance", "atuacao", "simulacao", "carreira")
_UNIQUE_DE_TABELA = re.compile(
    r",\s*(?:CONSTRAINT\s+\w+\s+)?UNIQUE\s*\([^)]*\)(?:\s*ON\s+CONFLICT\s+\w+)?", re.I)
_UNIQUE_DE_COLUNA = re.compile(r"\s+UNIQUE\b(?:\s+ON\s+CONFLICT\s+\w+)?", re.I)


def _sql_da_tabela(conn, tabela):
    return conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (tabela,)).fetchone()[0]


def _reconstruir(conn, tabela, nova_sql, manter_unique=True):
    """Troca a definição de `tabela` (receita das 12 etapas do SQLite),
    mantendo dados e índices. Só no banco temporário do teste."""
    indices = [i for (i,) in conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'index' AND tbl_name = ? AND sql IS NOT NULL",
        (tabela,)).fetchall()
        if manter_unique or not i.upper().startswith("CREATE UNIQUE")]
    conn.commit()
    fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        temp = f"{tabela}__reconstruida"
        conn.execute("BEGIN")
        conn.execute(re.sub(rf'^(CREATE TABLE(?: IF NOT EXISTS)?\s+)"?{tabela}"?', rf"\g<1>{temp}",
                            nova_sql.strip(), count=1, flags=re.I))
        conn.execute(f"INSERT INTO {temp} SELECT * FROM {tabela}")
        conn.execute(f"DROP TABLE {tabela}")
        conn.execute(f"ALTER TABLE {temp} RENAME TO {tabela}")
        for i in indices:
            conn.execute(i)
        conn.execute("COMMIT")
    finally:
        conn.execute(f"PRAGMA foreign_keys = {'ON' if fk else 'OFF'}")


def _como_backup_antigo(conn):
    for (nome,) in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'index' AND sql LIKE 'CREATE UNIQUE INDEX%'"
    ).fetchall():
        conn.execute(f'DROP INDEX "{nome}"')
    conn.commit()
    for tabela in _TABELAS_DO_R2:
        sql = _sql_da_tabela(conn, tabela)
        sem = _UNIQUE_DE_COLUNA.sub("", _UNIQUE_DE_TABELA.sub("", sql))
        if sem != sql:
            _reconstruir(conn, tabela, sem, manter_unique=False)


def _colunas_sem_id(conn, tabela):
    return [r[1] for r in conn.execute(f"PRAGMA table_info({tabela})") if r[1] != "id"]


def _clonar(conn, tabela, rid, **trocas):
    """Copia a linha `rid` de `tabela` (id novo), trocando as colunas dadas."""
    cols = _colunas_sem_id(conn, tabela)
    linha = conn.execute(f"SELECT {', '.join(cols)} FROM {tabela} WHERE id = ?", (rid,)).fetchone()
    valores = [trocas.get(c, linha[i]) for i, c in enumerate(cols)]
    cur = conn.execute(
        f"INSERT INTO {tabela} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", valores)
    return cur.lastrowid


def _duplicar_rodada(sid, rodada):
    """O que o R2 deixa no banco: a mesma rodada gravada duas vezes (partidas,
    lances e atuações). O blob e as tabelas de clube ficam como estavam."""
    conn = conectar()
    try:
        _como_backup_antigo(conn)
        with conn:
            partidas = [r[0] for r in conn.execute(
                "SELECT id FROM partida WHERE simulacao_id = ? AND rodada = ?", (sid, rodada))]
            for pid in partidas:
                nova = _clonar(conn, "partida", pid)
                for tabela in ("lance", "atuacao"):
                    for (filho,) in conn.execute(
                            f"SELECT id FROM {tabela} WHERE partida_id = ?", (pid,)).fetchall():
                        _clonar(conn, tabela, filho, partida_id=nova)
        return len(partidas)
    finally:
        conn.close()


def _duplicar_virada(sid, carreira_nova):
    """O que a virada dupla deixa: uma segunda 'temporada seguinte' do save.
    `carreira_nova=False`: na mesma carreira. `True`: numa carreira à parte
    (a primeira virada de um save sem carreira)."""
    seguinte = carreira_service.proxima_temporada(sid)["simulacao_id"]
    conn = conectar()
    try:
        _como_backup_antigo(conn)
        with conn:
            sim = simulacao_repo.buscar(conn, seguinte)
            carreira = sim["carreira_id"]
            if carreira_nova:
                carreira = _clonar(conn, "carreira", carreira)
            _clonar(conn, "simulacao", seguinte, carreira_id=carreira)
    finally:
        conn.close()


def test_rodada_dupla_e_acusada():
    sid = temporada_service.iniciar(seed=5, clube_usuario=_clube())
    temporada_service.avancar(sid)
    assert _duplicar_rodada(sid, 1) == 10
    a = _achados(diag.diagnosticar(_banco()))
    assert a["C01"]["achados"] == 10        # cada mandante da rodada 1, duas vezes
    assert a["C02"]["achados"] == 20        # cada clube em dois jogos
    assert a["C04"]["achados"] == 1         # a rodada 1 com 20 jogos e não 10
    assert a["C17"]["achados"] == 20        # todo clube: 2 jogos gravados × 1 na tabela
    assert a["C03"]["achados"] == 0         # rodadas distintas batem: não acusa
    assert a["B01"]["achados"] == 0         # blob e tabelas concordam entre si


def test_virada_dupla_dentro_da_carreira_e_acusada(cargo_garantido):
    sid = simulacao_service.salvar_temporada(seed=3, clube_usuario=_clube())
    conn = conectar()
    try:
        with conn:
            sim = simulacao_repo.buscar(conn, sid)
            carreira = carreira_repo.criar(conn, sim["clube_usuario"], sim["seed"], "2026-11-17")
            simulacao_repo.vincular_carreira(conn, sid, carreira, 1)
    finally:
        conn.close()
    _duplicar_virada(sid, carreira_nova=False)
    a = _achados(diag.diagnosticar(_banco()))
    assert a["C05"]["achados"] == 1          # (carreira, temporada 2) duas vezes
    assert a["C07"]["achados"] == 1          # duas temporadas em andamento


def test_virada_dupla_sem_carreira_e_acusada(cargo_garantido):
    sid = simulacao_service.salvar_temporada(seed=3, clube_usuario=_clube())
    _duplicar_virada(sid, carreira_nova=True)
    a = _achados(diag.diagnosticar(_banco()))
    assert a["C05"]["achados"] == 0          # cada uma na sua carreira...
    assert a["C06"]["achados"] == 1          # ...mas uma ficou sem a temporada 1


def _corrigir_r2_com_unique(forma):
    conn = conectar()
    try:
        if forma == "indice":
            with conn:
                conn.execute("CREATE UNIQUE INDEX ux_r2_partida ON partida(simulacao_id, rodada, mandante_id)")
                conn.execute("CREATE UNIQUE INDEX ux_r2_temporada ON simulacao(carreira_id, temporada)")
        else:   # UNIQUE dentro da tabela, numa reconstrução
            for tabela, cols in (("partida", "simulacao_id, rodada, mandante_id"),
                                 ("simulacao", "carreira_id, temporada")):
                sql = _sql_da_tabela(conn, tabela).rstrip()
                assert sql.endswith(")")
                _reconstruir(conn, tabela, sql[:-1] + f", UNIQUE ({cols}))")
            assert "UNIQUE" in _sql_da_tabela(conn, "partida")
    finally:
        conn.close()


@pytest.mark.parametrize("forma", ["indice", "tabela"])
def test_r2_corrigido_com_unique_nao_quebra_os_testes_do_diagnostico(cargo_garantido, forma):
    """Simula a correção futura do R2 por UNIQUE — em índice ou dentro da
    tabela (2ª revisão): os fluxos normais seguem, as duplicatas de um backup
    antigo continuam sendo montadas e acusadas."""
    _corrigir_r2_com_unique(forma)
    sid = temporada_service.iniciar(seed=5, clube_usuario=_clube())
    temporada_service.avancar(sid)
    assert _duplicar_rodada(sid, 1) == 10
    outro = simulacao_service.salvar_temporada(seed=3, clube_usuario=_clube())
    _duplicar_virada(outro, carreira_nova=True)
    a = _achados(diag.diagnosticar(_banco()))
    assert (a["C01"]["achados"], a["C06"]["achados"]) == (10, 1)


def test_nenhum_teste_do_diagnostico_depende_da_corrida():
    """Guarda do achado 5: este arquivo não reproduz a corrida do R2."""
    fonte = Path(__file__).read_text(encoding="utf-8")
    for proibido in ("_sincronizar_" + "avanco", "_sincronizar_" + "virada",
                     "Fio" + "(", "threading" + ".Barrier"):
        assert proibido not in fonte, proibido


# ---------------------------------------------------------------------------
# backups estranhos (Auditoria 03, achados 8, 9 e 10)
# ---------------------------------------------------------------------------

def _gravar_blob(sid, blob_texto):
    conn = conectar()
    try:
        with conn:
            conn.execute("UPDATE simulacao SET estado_json = ? WHERE id = ?", (blob_texto, sid))
    finally:
        conn.close()


def _blob(sid):
    conn = conectar()
    try:
        return json.loads(conn.execute(
            "SELECT estado_json FROM simulacao WHERE id = ?", (sid,)).fetchone()[0])
    finally:
        conn.close()


def test_blob_malformado_nao_derruba_o_diagnostico():
    """Achado 8: JSON com topo em lista, `rng[1]` que não é lista e
    `jogadores` que não é objeto. Cada save estranho vira achado do B01; os
    outros saves e as outras checagens rodam. 2ª revisão: o defeito de um
    clube não apaga os outros achados do mesmo save."""
    lista, rng_ruim, jogadores_ruim, normal = (
        temporada_service.iniciar(seed=s, clube_usuario=_clube()) for s in (5, 6, 7, 8))
    for sid in (lista, rng_ruim, jogadores_ruim, normal):
        temporada_service.avancar(sid)
    _gravar_blob(lista, "[1, 2, 3]")
    b = _blob(rng_ruim)
    b["rng"] = [3, 5, None]                       # len(5) quebrava a checagem
    _gravar_blob(rng_ruim, json.dumps(b))
    b = _blob(jogadores_ruim)
    primeiro, segundo = list(b["clubes"])[:2]
    b["clubes"][primeiro]["jogadores"] = ["não", "é", "objeto"]   # .items() quebrava
    b["clubes"][segundo]["pontos"] += 7                            # divergência real
    b["rodada"] += 1                                               # outra divergência real
    _gravar_blob(jogadores_ruim, json.dumps(b))

    rel = diag.diagnosticar(_banco())
    erros = {r["id"]: r["erro"] for r in rel["resultados"] if r["erro"]}
    assert not erros, erros
    b01 = _achados(rel)["B01"]
    tipos = {(a["simulacao_id"], a["tipo"]) for a in b01["amostra"]}
    assert tipos == {
        (lista, "blob ilegível"),
        (rng_ruim, "rng malformado"),
        (jogadores_ruim, "blob ilegível"),   # o clube com 'jogadores' errado
        (jogadores_ruim, "clube"),           # a divergência do outro clube continua
        (jogadores_ruim, "rodada"),          # e a da rodada também
    }, b01["amostra"]
    clube_ruim = [a for a in b01["amostra"] if a["simulacao_id"] == jogadores_ruim
                  and a["tipo"] == "blob ilegível"]
    assert clube_ruim[0]["clube"] == primeiro


def test_clube_que_nao_e_objeto_no_blob_vira_achado():
    sid = temporada_service.iniciar(seed=5, clube_usuario=_clube())
    temporada_service.avancar(sid)
    b = _blob(sid)
    primeiro = next(iter(b["clubes"]))
    b["clubes"][primeiro] = [1, 2]
    _gravar_blob(sid, json.dumps(b))
    amostra = _achados(diag.diagnosticar(_banco()))["B01"]["amostra"]
    assert [(a["tipo"], a.get("clube")) for a in amostra] == [("blob ilegível", primeiro)], amostra


def test_erro_inesperado_num_save_vira_achado_e_os_outros_seguem():
    """Último recurso: um erro que nenhuma checagem de tipo previu vira
    'blob inesperado' daquele save; o diagnóstico termina."""
    for seed in (5, 6):
        temporada_service.avancar(temporada_service.iniciar(seed=seed, clube_usuario=_clube()))

    def quebra(rng):
        raise TypeError("defeito simulado")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(diag, "_rng_ok", quebra)
        rel = diag.diagnosticar(_banco())
    b01 = _achados(rel)["B01"]
    assert b01["erro"] is None
    assert [a["tipo"] for a in b01["amostra"]] == ["blob inesperado", "blob inesperado"]


def test_checagem_que_quebra_nao_derruba_as_outras():
    temporada_service.avancar(temporada_service.iniciar(seed=5, clube_usuario=_clube()))

    def quebra(conn):
        raise TypeError("defeito simulado na checagem")

    conn = diag.abrir(_banco())
    try:
        res = diag.executar(conn, [
            diag.Checagem("X1", "quebra", "forte", funcao=quebra),
            diag.Checagem("X2", "conta partidas", "forte", "SELECT id FROM partida"),
        ])
    finally:
        conn.close()
    assert "TypeError" in res[0].erro
    assert (res[1].erro, res[1].achados) == (None, 10)


def test_colunas_pelo_esquema_real_e_nao_por_trecho_de_texto(tmp_path):
    """Achado 9: 'idade' aparece dentro de 'cidade' e de um CHECK, e
    'numero' dentro de 'numero_camisa' — nenhuma das duas é coluna."""
    caminho = tmp_path / "antigo.db"
    c = sqlite3.connect(caminho)
    c.execute("CREATE TABLE jogador (id INTEGER PRIMARY KEY, cidade TEXT, "
              "numero_camisa INTEGER, CHECK (cidade != 'idade'))")
    c.commit()
    c.close()
    conn = diag.abrir(caminho)
    try:
        texto = conn.execute("SELECT sql FROM sqlite_master WHERE name = 'jogador'").fetchone()[0]
        assert "idade" in texto and "numero" in texto      # a armadilha está lá
        assert diag._colunas(conn, "jogador") == {"id", "cidade", "numero_camisa"}
        assert diag._colunas(conn, "nao_existe") == set()
    finally:
        conn.close()


def test_jogadores_homonimos_em_clubes_diferentes_nao_se_confundem():
    """Achado 10: dois jogadores com o mesmo nome em clubes diferentes,
    coerentes entre blob e tabelas. O B01 compara cada um com o seu; o C11
    continua acusando o nome repetido."""
    sid = temporada_service.iniciar(seed=5, clube_usuario=_clube())
    temporada_service.avancar(sid)
    conn = conectar()
    try:
        linhas = conn.execute(
            "SELECT j.id, j.nome, j.overall, j.idade, c.nome AS clube FROM jogador j "
            "JOIN clube c ON c.id = j.clube_id WHERE j.simulacao_id = ? ORDER BY c.nome, j.id",
            (sid,)).fetchall()
        clube_a = linhas[0]["clube"]
        pa = linhas[0]
        pb = next(r for r in linhas if r["clube"] != clube_a
                  and (r["overall"], r["idade"]) != (pa["overall"], pa["idade"]))
        with conn:
            conn.execute("UPDATE jogador SET nome = ? WHERE id = ?", (pa["nome"], pb["id"]))
    finally:
        conn.close()
    b = _blob(sid)
    dados = b["clubes"][pb["clube"]]
    dados["elenco"] = [pa["nome"] if n == pb["nome"] else n for n in dados["elenco"]]
    dados["jogadores"][pa["nome"]] = dados["jogadores"].pop(pb["nome"])
    _gravar_blob(sid, json.dumps(b))

    a = _achados(diag.diagnosticar(_banco()))
    assert a["B01"]["achados"] == 0, a["B01"]["amostra"]
    assert a["C11"]["achados"] == 1


def test_homonimos_no_mesmo_clube_ficam_ambiguos_e_nao_sao_comparados():
    sid = temporada_service.iniciar(seed=5, clube_usuario=_clube())
    temporada_service.avancar(sid)
    conn = conectar()
    try:
        clube_id = conn.execute(
            "SELECT clube_id FROM jogador WHERE simulacao_id = ? LIMIT 1", (sid,)).fetchone()[0]
        p1, p2 = conn.execute(
            "SELECT id, nome FROM jogador WHERE clube_id = ? ORDER BY id LIMIT 2",
            (clube_id,)).fetchall()
        with conn:
            conn.execute("UPDATE jogador SET nome = ? WHERE id = ?", (p1["nome"], p2["id"]))
    finally:
        conn.close()
    amostra = _achados(diag.diagnosticar(_banco()))["B01"]["amostra"]
    ambiguos = [x for x in amostra if x["tipo"] == "jogador ambíguo"]
    assert len(ambiguos) == 1 and ambiguos[0]["jogador"] == p1["nome"], amostra
    assert not [x for x in amostra if x["tipo"] == "jogador" and x["jogador"] == p1["nome"]], amostra


# ---------------------------------------------------------------------------
# proteções do script
# ---------------------------------------------------------------------------

def test_recusa_caminho_vazio_inexistente_padrao_e_producao(tmp_path):
    with pytest.raises(diag.Recusado):
        diag.validar_caminho("")
    with pytest.raises(diag.Recusado, match="não encontrado"):
        diag.validar_caminho(tmp_path / "nao_existe.db")
    assert diag.BANCO_PADRAO.name == "taldo_manager.db"
    assert diag.BANCO_PADRAO.parent.name == "database"
    if diag.BANCO_PADRAO.exists():   # só se houver um banco local de desenvolvimento
        with pytest.raises(diag.Recusado, match="banco padrão"):
            diag.validar_caminho(diag.BANCO_PADRAO)
    assert diag.main([str(tmp_path / "nao_existe.db")]) == 2


def test_authorizer_nega_toda_escrita_e_as_tabelas_de_conta():
    temporada_service.avancar(temporada_service.iniciar(seed=5, clube_usuario=_clube()))
    conn = diag.abrir(_banco())
    try:
        tentativas = [
            "DELETE FROM partida",
            "UPDATE simulacao SET campeao = 'x'",
            "INSERT INTO carreira (clube_usuario, criada_em) VALUES ('x', 'y')",
            "CREATE INDEX ix_teste ON partida(rodada)",
            "CREATE UNIQUE INDEX ux_teste ON partida(simulacao_id, rodada, mandante_id)",
            "DROP TABLE lance",
            "PRAGMA query_only = OFF",
            "ATTACH DATABASE ':memory:' AS outro",
            "SELECT * FROM usuario",
            "SELECT * FROM sessao",
        ]
        res = diag.executar(conn, [diag.Checagem(f"X{i}", sql, "forte", sql)
                                   for i, sql in enumerate(tentativas)])
    finally:
        conn.close()
    assert all(r.erro for r in res), [(r.titulo, r.erro) for r in res if not r.erro]
    conn = conectar()
    try:
        assert conn.execute("SELECT COUNT(*) FROM partida").fetchone()[0] == 10
    finally:
        conn.close()


def test_o_arquivo_nao_muda():
    temporada_service.avancar(temporada_service.iniciar(seed=5, clube_usuario=_clube()))
    antes = diag.sha256(_banco())
    rel = diag.diagnosticar(_banco())
    assert rel["sha256"] == antes == diag.sha256(_banco())
