import random

from app.domain import mercado
from app.domain.base import (
    COMPOSICAO_IDEAL,
    DESCONTO_OVERALL,
    TAMANHO_ALVO,
    gerar_jovem,
    gerar_nome,
    posicao_carente,
    quantos_sobem,
    subir_jovens,
)
from app.domain.nomes import NOMES, SOBRENOMES
from scripts.data_loader import carregar_campeonato


def _clube(n_jogadores=18):
    clube = carregar_campeonato().clubes[0]
    del clube.jogadores[n_jogadores:]
    return clube


def test_quantos_sobem_completa_ate_18_com_minimo_de_1():
    assert quantos_sobem(_clube(16)) == 2
    assert quantos_sobem(_clube(18)) == 1      # sempre revela alguém

    cheio = _clube(18)
    cheio.jogadores += cheio.jogadores[:7]     # 25 = ELENCO_MAX
    assert quantos_sobem(cheio) == 0


def test_posicao_carente_e_a_que_falta():
    # FC Taldo da seed: 6 meias e 5 defensores → falta defensor
    assert posicao_carente(_clube(), random.Random(1)) == "Defesa"


def test_posicao_carente_repoe_o_goleiro():
    clube = _clube()
    goleiros = [j for j in clube.jogadores if j.posicao == "Goleiro"]
    clube.jogadores.remove(goleiros[0])
    assert posicao_carente(clube, random.Random(1)) == "Goleiro"


def test_posicao_carente_empata_na_sorte_entre_as_carentes():
    # o Real Taldo tem a composição ideal: empate geral (déficit 0). O FC
    # Taldo não serve: tem 6 meias e 5 defensores
    clube = carregar_campeonato().clubes[1]
    vistas = {posicao_carente(clube, random.Random(s)) for s in range(40)}
    assert vistas == set(COMPOSICAO_IDEAL)


def test_gerar_nome_nao_repete_e_registra():
    proibidos = {"João Silva"}
    rng = random.Random(1)
    nomes = [gerar_nome(proibidos, rng) for _ in range(100)]
    assert len(set(nomes)) == 100
    assert "João Silva" not in nomes
    assert set(nomes) <= proibidos


def test_gerar_nome_esgotado_ganha_sufixo():
    proibidos = {f"{n} {s}" for n in NOMES for s in SOBRENOMES}
    assert gerar_nome(proibidos, random.Random(1)).endswith(" Jr.")


def test_jovem_tem_idade_de_base_e_potencial_acima_do_overall():
    clube = _clube()
    media = sum(j.overall for j in clube.jogadores) / len(clube.jogadores)
    rng = random.Random(3)
    for _ in range(50):
        j = gerar_jovem(clube, set(), rng)
        assert 16 <= j.idade <= 18
        assert abs(j.overall - (round(media) - DESCONTO_OVERALL)) <= 4
        assert j.overall + 8 <= j.potencial <= min(99, j.overall + 22)
        assert (j.contrato_anos, j.multa_rescisoria) == (3, None)
        assert j.salario == j.salario_referencia()


def test_base_de_clube_grande_e_melhor():
    camp = carregar_campeonato()
    por_nome = {c.nome: c for c in camp.clubes}
    rng = random.Random(4)
    elite = [gerar_jovem(por_nome["Taldo City"], set(), rng).overall for _ in range(30)]
    fraco = [gerar_jovem(por_nome["Taldo FC"], set(), rng).overall for _ in range(30)]
    assert sum(elite) / 30 > sum(fraco) / 30 + 5


def test_subir_jovens_em_todos_os_clubes():
    camp = carregar_campeonato()
    camp.clubes[0].jogadores = camp.clubes[0].jogadores[:16]

    movs = subir_jovens(camp, set(), random.Random(5))

    assert len(camp.clubes[0].jogadores) == TAMANHO_ALVO
    assert all(len(c.jogadores) >= TAMANHO_ALVO for c in camp.clubes)
    assert all(m["tipo"] == "subiu_da_base" for m in movs)
    assert len(movs) == 2 + 19              # 2 no desfalcado, 1 nos outros
    nomes = [j.nome for c in camp.clubes for j in c.jogadores]
    assert len(nomes) == len(set(nomes))    # nada repetido na liga
    assert len(camp.clubes[0].jogadores) <= mercado.ELENCO_MAX
