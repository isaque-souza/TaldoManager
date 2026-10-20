"""Olheiro profissional (v2.0): a faixa do potencial e o custo da troca."""

import pytest

from app.domain import olheiro
from app.domain.clube import Clube
from app.domain.evolucao import IDADE_DECLINIO
from app.domain.jogador import Jogador


def _jovem(nome="Joia", overall=70, potencial=84, idade=19):
    return Jogador(nome, idade, "Atacante", overall, potencial=potencial)


@pytest.mark.parametrize("nivel", olheiro.NIVEIS)
def test_a_faixa_sempre_contem_o_potencial_verdadeiro(nivel):
    for i in range(200):
        j = _jovem(f"Jogador {i}", overall=60 + i % 20, potencial=75 + i % 20)
        minimo, maximo = olheiro.faixa(j, nivel)
        assert minimo <= j.potencial <= maximo
        assert j.overall <= minimo and maximo <= olheiro.POTENCIAL_MAX


def test_a_faixa_tem_a_largura_do_nivel():
    j = _jovem(overall=50, potencial=75)   # longe dos limites
    for nivel, (meia, _) in olheiro.NIVEIS.items():
        minimo, maximo = olheiro.faixa(j, nivel)
        assert maximo - minimo == 2 * meia


def test_o_verdadeiro_nao_fica_sempre_no_meio():
    meios = {
        olheiro.faixa(_jovem(f"J{i}", overall=50, potencial=75), 1)[0] for i in range(50)
    }
    assert len(meios) > 3


def test_subir_de_nivel_so_encolhe_a_faixa():
    for i in range(100):
        j = _jovem(f"J{i}", overall=50, potencial=75)
        anterior = olheiro.faixa(j, 1)
        for nivel in range(2, 6):
            atual = olheiro.faixa(j, nivel)
            assert anterior[0] <= atual[0] and atual[1] <= anterior[1]
            anterior = atual


def test_a_faixa_nao_muda_entre_chamadas():
    j = _jovem()
    assert olheiro.faixa(j, 2) == olheiro.faixa(_jovem(), 2)


def test_nivel_5_ainda_deixa_duvida():
    minimo, maximo = olheiro.faixa(_jovem(overall=50, potencial=75), 5)
    assert maximo - minimo == 2


def test_veterano_e_exato():
    velho = _jovem(idade=IDADE_DECLINIO, overall=80, potencial=80)
    assert olheiro.faixa(velho, 1) is None
    assert olheiro.estimativa(velho, 1) == {"potencial": 80, "potencial_faixa": None}


def test_estimativa_mostra_o_meio_da_faixa():
    j = _jovem(overall=50, potencial=75)
    minimo, maximo = olheiro.faixa(j, 1)
    assert olheiro.estimativa(j, 1) == {
        "potencial": round((minimo + maximo) / 2), "potencial_faixa": [minimo, maximo],
    }


def test_subir_paga_a_diferenca_pelo_resto_da_temporada():
    total = 38
    cheio = olheiro.custo_temporada(3) - olheiro.custo_temporada(1)
    assert olheiro.custo_da_troca(1, 3, 0, total) == cheio
    assert olheiro.custo_da_troca(1, 3, 19, total) == round(cheio / 2)
    assert olheiro.custo_da_troca(1, 3, total, total) == 0


def test_descer_e_de_graca():
    assert olheiro.custo_da_troca(5, 1, 0, 38) == 0
    assert olheiro.custo_da_troca(4, 2, 10, 38) == 0


def test_troca_bloqueada():
    clube = Clube("Casa", "Brasil", 100_000)
    assert "já é" in olheiro.motivo_troca_bloqueada(clube, 1, 0)
    assert "caixa" in olheiro.motivo_troca_bloqueada(clube, 5, 4_000_000)
    assert olheiro.motivo_troca_bloqueada(clube, 2, 50_000) is None


def test_nivel_invalido():
    with pytest.raises(olheiro.NivelInvalido):
        olheiro.validar(6)
