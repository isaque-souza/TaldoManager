"""Mundos versionados (v2.7): manifesto, hashes, imutabilidade e a carga
das seeds pelo mundo."""

import json

import pytest

from scripts import data_loader, mundos

CAMPOS_DO_MANIFESTO = {
    "id", "formato", "nome", "criado_em", "base", "raiz", "ligas", "totais",
    "arquivos", "gerado_por", "midia", "alteracoes",
}
CAMPOS_DA_LIGA = {
    "nome", "pasta", "pais", "divisao", "origem", "temporada",
    "clubes", "jogadores", "livres",
}


# ---------------------------------------------------------------------------
# os mundos do repositório
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mundo", mundos.ids())
def test_todo_mundo_instalado_bate_com_o_manifesto(mundo):
    """Editar um arquivo de qualquer mundo quebra este teste: corrigir dado
    é criar um mundo novo, nunca reescrever um que algum save usa."""
    assert mundos.problemas(mundo) == []

    m = mundos.manifesto(mundo)
    assert set(m) == CAMPOS_DO_MANIFESTO
    assert m["id"] == mundo
    assert m["formato"] == mundos.FORMATO
    totais = {"ligas": 0, "clubes": 0, "jogadores": 0, "livres": 0}
    for liga, info in m["ligas"].items():
        assert set(info) == CAMPOS_DA_LIGA, liga
        pasta = mundos.pasta_da_liga(mundo, liga)
        for chave in ("clubes", "jogadores", "livres"):
            caminho = pasta / f"{chave}.json"
            reais = len(json.loads(caminho.read_text(encoding="utf-8"))) if caminho.exists() else 0
            assert info[chave] == reais, (liga, chave)
            totais[chave] += reais
        totais["ligas"] += 1
    assert m["totais"] == totais
    if m["base"]:
        assert mundos.existe(m["base"])


def test_v1_sao_as_seeds_de_sempre():
    m = mundos.manifesto("v1")
    assert m["raiz"] == "seeds" and m["base"] is None
    assert mundos.pasta_da_liga("v1", "taldo") == data_loader.SEEDS_DIR
    assert mundos.pasta_da_liga("v1", "premier") == data_loader.SEEDS_DIR / "premier"
    # a ordem das tabelas e os nomes de sempre
    assert data_loader.TODAS_AS_LIGAS == (
        "taldo", "premier", "taldo_b", "championship", "laliga", "segunda",
        "brasileirao", "brasileirao_b",
    )
    assert data_loader.LIGAS["brasileirao"][0] == "Brasileirão"
    assert m["ligas"]["brasileirao"]["temporada"] == "2017"
    assert m["totais"] == {"ligas": 8, "clubes": 160, "jogadores": 3679, "livres": 150}
    assert mundos.MUNDO_INICIAL == "v1"


def test_o_hash_ignora_o_fim_de_linha(tmp_path):
    """O mesmo mundo tem o mesmo hash no Windows (CRLF) e no Linux (LF)."""
    lf, crlf = tmp_path / "lf.json", tmp_path / "crlf.json"
    lf.write_bytes(b'[\n  {"nome": "A"}\n]\n')
    crlf.write_bytes(b'[\r\n  {"nome": "A"}\r\n]\r\n')
    assert mundos.hash_arquivo(lf) == mundos.hash_arquivo(crlf)
    lf.write_bytes(b'[\n  {"nome": "B"}\n]\n')
    assert mundos.hash_arquivo(lf) != mundos.hash_arquivo(crlf)


def test_mundo_do_save():
    assert data_loader.mundo_do_save({"mundo": "v2"}) == "v2"
    assert data_loader.mundo_do_save({"mundo": None}) == "v1"
    assert data_loader.mundo_do_save({}) == "v1"     # linha de antes da coluna


# ---------------------------------------------------------------------------
# criar mundos (em pasta temporária)
# ---------------------------------------------------------------------------

def test_mundo_novo_copia_o_base_e_registra_o_que_mudou(mundos_temp, liga_alterada):
    obra = liga_alterada("premier", "Chelsea", "Chelsea Novo")
    m = mundos.criar_mundo("teste", "Teste", base="v1", trocar={"premier": obra},
                           resumo="Chelsea renomeado")

    assert mundos.ids() == ["teste", "v1"]
    assert mundos.problemas("teste") == []
    assert list(m["ligas"]) == list(mundos.manifesto("v1")["ligas"])
    assert m["base"] == "v1" and m["midia"] == {}
    assert m["alteracoes"]["clubes"] == {"entraram": ["Chelsea Novo"], "sairam": ["Chelsea"]}
    assert m["alteracoes"]["ligas"] == {"entraram": [], "sairam": []}
    assert m["alteracoes"]["jogadores"] == {"entraram": 0, "sairam": 0}
    # as ligas que não mudaram são cópias exatas (mesmo hash do v1)
    v1 = mundos.manifesto("v1")["arquivos"]
    assert m["arquivos"]["ligas/laliga/clubes.json"] == v1["laliga/clubes.json"]
    assert m["arquivos"]["ligas/taldo/jogadores.json"] == v1["jogadores.json"]
    assert m["arquivos"]["ligas/premier/clubes.json"] != v1["premier/clubes.json"]

    campeonato = data_loader.carregar_campeonato(("taldo", "premier"), "teste")
    nomes = {c.nome for c in campeonato.clubes}
    assert "Chelsea Novo" in nomes and "Chelsea" not in nomes
    assert campeonato.mundo == "teste"
    # e o v1 segue igual
    nomes_v1 = {c.nome for c in data_loader.carregar_campeonato(("premier",)).clubes}
    assert "Chelsea" in nomes_v1 and "Chelsea Novo" not in nomes_v1


def test_mundo_nunca_e_sobrescrito(mundos_temp):
    mundos.criar_mundo("teste", "Teste", base="v1")
    with pytest.raises(FileExistsError):
        mundos.criar_mundo("teste", "Outro", base="v1")
    with pytest.raises(FileExistsError):
        mundos.gravar_manifesto({**mundos.manifesto("v1")})


def test_mundo_sem_ligas_do_base(mundos_temp):
    tirar = ("championship", "laliga", "segunda", "brasileirao", "brasileirao_b")
    mundos.criar_mundo("mini", "Mini", base="v1", tirar=tirar)
    assert data_loader.todas_as_ligas("mini") == ("taldo", "premier", "taldo_b")
    assert mundos.manifesto("mini")["alteracoes"]["ligas"]["sairam"] == sorted(tirar)
    with pytest.raises(ValueError, match="laliga"):
        data_loader.carregar_campeonato(("laliga",), "mini")


def test_arquivo_alterado_nao_carrega(mundos_temp):
    mundos.criar_mundo("teste", "Teste", base="v1")
    clubes = mundos_temp / "teste" / "ligas" / "premier" / "clubes.json"
    clubes.write_text(clubes.read_text(encoding="utf-8").replace("Chelsea", "Chelsea X"),
                      encoding="utf-8")
    mundos.limpar_cache()

    with pytest.raises(mundos.MundoAlterado, match="premier/clubes.json foi alterado"):
        data_loader.carregar_campeonato(("premier",), "teste")


def test_arquivo_que_sumiu_ou_sobra_e_acusado(mundos_temp):
    mundos.criar_mundo("teste", "Teste", base="v1")
    liga = mundos_temp / "teste" / "ligas"
    (liga / "taldo" / "livres.json").unlink()
    sem_livres = next(l for l, i in mundos.manifesto("teste")["ligas"].items() if i["livres"] == 0)
    (liga / sem_livres / "livres.json").write_text("[]", encoding="utf-8")
    achados = mundos.problemas("teste")
    assert "falta ligas/taldo/livres.json" in achados
    assert f"ligas/{sem_livres}/livres.json não está no manifesto" in achados


def test_mundo_ausente():
    with pytest.raises(mundos.MundoAusente, match="v99"):
        data_loader.carregar_campeonato(("taldo",), "v99")


def test_scripts_nao_gravam_dentro_de_um_mundo(tmp_path):
    for pasta in (data_loader.SEEDS_DIR, data_loader.SEEDS_DIR / "premier",
                  data_loader.SEEDS_DIR / "premier" / "clubes.json"):
        with pytest.raises(PermissionError, match="imutável"):
            mundos.exigir_fora_dos_mundos(pasta)
    mundos.exigir_fora_dos_mundos(tmp_path / "trabalho")    # fora: pode
