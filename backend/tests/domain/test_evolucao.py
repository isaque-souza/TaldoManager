import random

import pytest

from app.domain.evolucao import evoluir, revisar_potencial


class SorteFixa:
    """rng de teste: `choice` sempre devolve o mesmo valor."""

    def __init__(self, valor=0):
        self.valor = valor

    def choice(self, _opcoes):
        return self.valor


SEM_SORTE = SorteFixa(0)


def test_fica_um_ano_mais_velho():
    assert evoluir(18, 70, 85, 20, SEM_SORTE)[0] == 19
    assert evoluir(36, 80, 80, 20, SEM_SORTE)[0] == 37


def test_jovem_titular_cresce_mais_que_o_do_banco():
    # margem 15 × 35%: × 1,25 (titular) ≈ 7; × 0,6 (banco, e com o
    # potencial revisado para 83) ≈ 3
    _, titular, _ = evoluir(18, 70, 85, 30, SEM_SORTE)
    _, normal, _ = evoluir(18, 70, 85, 15, SEM_SORTE)
    _, banco, _ = evoluir(18, 70, 85, 2, SEM_SORTE)
    assert (titular, normal, banco) == (77, 75, 73)


def test_crescimento_desacelera_com_a_idade():
    ganhos = [evoluir(idade, 70, 80, 15, SEM_SORTE)[1] - 70
              for idade in (19, 22, 26)]
    assert ganhos == [4, 3, 2]          # 35%, 30%, 25% de 10 (arredondado)


def test_nunca_passa_do_potencial():
    rng = random.Random(3)
    for _ in range(200):
        _, ovr, pot = evoluir(19, 84, 85, 38, rng)
        assert ovr <= pot <= 86


def test_sem_margem_nao_cresce_nem_com_sorte():
    assert evoluir(27, 80, 80, 38, SorteFixa(1))[1] == 80


@pytest.mark.parametrize("idade,queda", [(30, 1), (31, 1), (32, 2), (33, 2), (34, 3), (37, 3)])
def test_veterano_cai_conforme_a_idade(idade, queda):
    assert evoluir(idade, 90, 90, 30, SEM_SORTE)[1] == 90 - queda


def test_sorte_nunca_faz_veterano_subir():
    assert evoluir(30, 90, 90, 30, SorteFixa(-1))[1] == 90


def test_a_partir_dos_30_o_potencial_acompanha_o_overall():
    _, ovr, pot = evoluir(33, 90, 90, 30, SEM_SORTE)
    assert pot == ovr == 88
    # quem faz 30 agora também passa a ter potencial = overall
    _, ovr, pot = evoluir(29, 80, 83, 30, SEM_SORTE)
    assert pot == ovr


def test_overall_fica_entre_40_e_99():
    assert evoluir(36, 41, 41, 30, SEM_SORTE)[1] == 40
    assert evoluir(18, 98, 99, 38, SorteFixa(1))[1] == 99


def test_com_rng_real_e_deterministico():
    a = [evoluir(18, 70, 85, 20, random.Random(5)) for _ in range(3)]
    b = [evoluir(18, 70, 85, 20, random.Random(5)) for _ in range(3)]
    assert a == b


# --- potencial revisado ---

def test_potencial_revisado_usa_a_sorte():
    assert revisar_potencial(19, 70, 85, 20, SorteFixa(-3)) == 82
    assert revisar_potencial(19, 70, 85, 20, SorteFixa(1)) == 86


def test_quem_quase_nao_joga_perde_mais_potencial():
    assert revisar_potencial(19, 70, 85, 5, SorteFixa(0)) == 83


def test_potencial_revisado_nunca_abaixo_do_overall():
    assert revisar_potencial(19, 84, 85, 0, SorteFixa(-3)) == 84


def test_sem_margem_ou_veterano_o_potencial_nao_e_revisado():
    assert revisar_potencial(25, 80, 80, 0, SorteFixa(-3)) == 80
    assert revisar_potencial(31, 80, 85, 0, SorteFixa(-3)) == 85


def test_em_media_o_potencial_encolhe():
    rng = random.Random(7)
    novos = [revisar_potencial(19, 70, 85, 20, rng) for _ in range(2000)]
    assert 83.5 < sum(novos) / len(novos) < 84.5      # média −1
