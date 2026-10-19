"""A seed da Premier League 2023/24 (v1.6, scripts/importar_premier.py)."""

import collections
import json
import statistics
from pathlib import Path

import pytest

from app.domain import posicoes
from app.domain.jogador import Jogador
from scripts import importar_premier

SEEDS = Path(__file__).resolve().parent.parent / "data" / "seeds"


def _ler(*partes):
    return json.loads(SEEDS.joinpath(*partes).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def seed():
    clubes = _ler("premier", "clubes.json")
    jogadores = {j["id"]: j for j in _ler("premier", "jogadores.json")}
    return clubes, jogadores, _ler("premier", "livres.json")


def _elenco(clube, jogadores):
    return [jogadores[i] for i in clube["titulares"] + clube["reservas"]]


def test_reimportar_gera_os_mesmos_arquivos(seed):
    clubes, jogadores, livres = importar_premier.importar()
    assert (clubes, {j["id"]: j for j in jogadores}, livres) == seed


def test_vinte_clubes_de_23_com_11_titulares(seed):
    clubes, jogadores, _ = seed
    assert len(clubes) == 20 and len(jogadores) == 460
    for c in clubes:
        assert len(c["titulares"]) == 11
        assert len(_elenco(c, jogadores)) == 23


def test_tabela_de_2023_24(seed):
    clubes, _, _ = seed
    ordem = [c["nome"] for c in sorted(clubes, key=lambda c: c["posicao_2023_24"])]
    assert ordem[:3] == ["Manchester City", "Arsenal", "Liverpool"]
    assert ordem[-3:] == ["Luton Town", "Burnley", "Sheffield United"]


def test_todo_elenco_cabe_em_qualquer_formacao(seed):
    """3 goleiros e o mínimo de cada posição (o que a formação mais
    exigente pede), como na Taldo."""
    clubes, jogadores, _ = seed
    for c in clubes:
        conta = collections.Counter(j["funcao"] for j in _elenco(c, jogadores))
        assert conta["Goleiro"] == 3, c["nome"]
        for funcao, minimo in posicoes.MINIMO_POR_POSICAO.items():
            assert conta[funcao] >= minimo, (c["nome"], funcao)


def test_ids_e_nomes_nao_colidem_com_a_taldo(seed):
    _, jogadores, livres = seed
    assert min(jogadores) >= importar_premier.PRIMEIRO_ID
    assert not set(jogadores) & {j["id"] for j in _ler("jogadores.json")}

    nomes = [j["nome"] for j in jogadores.values()] + [j["nome"] for j in livres]
    assert len(nomes) == len(set(nomes))
    taldo = {j["nome"] for j in _ler("jogadores.json")} | {j["nome"] for j in _ler("livres.json")}
    assert not set(nomes) & taldo
    assert "João Gomes (BRA)" in nomes          # o real ganhou a nacionalidade


def test_estrelas_entram_com_os_valores_do_arquivo(seed):
    _, jogadores, _ = seed
    por_nome = {j["nome"]: j for j in jogadores.values()}
    estrelas = json.loads(importar_premier.ESTRELAS.read_text(encoding="utf-8"))
    for nome, valores in estrelas.items():
        if nome.startswith("_"):
            continue
        assert nome in por_nome, nome
        for campo, valor in valores.items():
            assert por_nome[nome][campo] == valor, (nome, campo)
    assert por_nome["Erling Håland"]["posicao"] == "Atacante"
    assert por_nome["Bukayo Saka"]["posicao"] == "Atacante"   # MF no arquivo, ponta aqui


def test_campeao_bem_mais_forte_que_o_lanterna_e_na_faixa_da_taldo(seed):
    clubes, jogadores, _ = seed
    xi = {
        c["nome"]: statistics.mean(jogadores[i]["overall"] for i in c["titulares"])
        for c in clubes
    }
    assert xi["Manchester City"] - xi["Sheffield United"] >= 8
    assert 70 <= min(xi.values()) and max(xi.values()) <= 90


def test_jogadores_e_livres_viram_jogador_do_motor(seed):
    _, jogadores, livres = seed
    for j in list(jogadores.values()) + livres:
        jogador = Jogador(
            j["nome"], j["idade"], j["posicao"], j["overall"],
            potencial=j["potencial"], funcao=j["funcao"],
            secundarias=j["secundarias"],
        )
        assert posicoes.SETOR[jogador.funcao] == jogador.posicao
        assert jogador.potencial >= jogador.overall
    assert len(livres) == 50
