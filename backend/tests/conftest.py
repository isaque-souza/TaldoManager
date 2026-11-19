"""Cada teste roda contra um SQLite temporário e vazio, nunca o banco real."""

import pytest

from app.db.conexao import init_db


@pytest.fixture(autouse=True)
def banco_temporario(tmp_path, monkeypatch):
    monkeypatch.setenv("TALDO_DB", str(tmp_path / "teste.db"))
    init_db()
    yield


@pytest.fixture(autouse=True)
def sem_login():
    """As contas (v2.1) têm testes próprios (test_contas.py); nos outros a
    API responde sem login, como antes, e os saves ficam sem dono."""
    from app.api.contas import exigir_dono
    from app.main import app
    app.dependency_overrides[exigir_dono] = lambda: None
    yield
    app.dependency_overrides.pop(exigir_dono, None)


@pytest.fixture
def cargo_garantido(monkeypatch):
    """Para testes de virada que não são sobre a diretoria: com a seed
    fixa, o técnico pode acabar demitido (e a virada é recusada) a cada
    ajuste do motor que mexe nos resultados."""
    from app.services import simulacao_service
    monkeypatch.setattr(
        simulacao_service, "cargo_da_temporada",
        lambda conn, sim: {"estado": "mantido", "motivo": None},
    )


@pytest.fixture
def mundos_temp(tmp_path, monkeypatch):
    """Mundos (v2.7) numa pasta temporária, com o v1 de verdade (o manifesto
    aponta para data/seeds/, só leitura). Os mundos criados no teste vão
    para lá; os caches de mundo são limpos na entrada e na saída."""
    import shutil

    from scripts import data_loader, mundos

    pasta = tmp_path / "mundos"
    (pasta / "v1").mkdir(parents=True)
    shutil.copyfile(mundos.MUNDOS_DIR / "v1" / "manifesto.json",
                    pasta / "v1" / "manifesto.json")

    def limpar():
        mundos.limpar_cache()
        data_loader.rivais_do_seed.cache_clear()

    limpar()
    monkeypatch.setattr(mundos, "MUNDOS_DIR", pasta)
    yield pasta
    monkeypatch.undo()
    limpar()


@pytest.fixture
def liga_alterada(tmp_path):
    """Monta, numa pasta de trabalho, uma cópia de uma liga do v1 com um
    clube renomeado: `liga_alterada("premier", "Chelsea", "Chelsea Novo")`
    devolve a pasta."""
    import json
    import shutil

    from scripts import mundos

    def montar(liga, de, para):
        origem = mundos.pasta_da_liga("v1", liga)
        destino = tmp_path / "obra" / liga
        destino.mkdir(parents=True)
        for nome in mundos.ARQUIVOS_DA_LIGA:
            if (origem / nome).is_file():
                shutil.copyfile(origem / nome, destino / nome)
        clubes = json.loads((destino / "clubes.json").read_text(encoding="utf-8"))
        alvo = next(c for c in clubes if c["nome"] == de)
        alvo["nome"] = para
        (destino / "clubes.json").write_text(
            json.dumps(clubes, ensure_ascii=False, indent=4), encoding="utf-8")
        return destino

    return montar
