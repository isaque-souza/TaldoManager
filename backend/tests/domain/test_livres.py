"""Jogadores sem clube na virada da carreira (v1.6)."""

import random

from app.domain import base, livres, mercado
from app.domain.carreira import aposentar, envelhecer
from scripts.data_loader import carregar_campeonato

SEMPRE, NUNCA = random.Random(), random.Random()
SEMPRE.random = lambda: 0.0
NUNCA.random = lambda: 0.999


def test_gerar_respeita_o_perfil_e_nao_repete_nome():
    rng = random.Random(1)
    proibidos = {"João Silva"}
    for perfil, (_, idades, overalls, margem) in livres.PERFIS.items():
        for _ in range(20):
            j = livres.gerar("Goleiro", perfil, proibidos, rng)
            assert idades[0] <= j["idade"] <= idades[1]
            assert overalls[0] <= j["overall"] <= overalls[1]
            assert j["overall"] + margem[0] <= j["potencial"] <= j["overall"] + margem[1]
            assert j["nome"] in proibidos and j["nome"] != "João Silva"


def test_completar_ate_quantos_sem_repetir_nomes():
    camp = carregar_campeonato()
    del camp.livres[10:]

    livres.completar(camp, set(), random.Random(2))

    assert len(camp.livres) == livres.QUANTOS
    nomes = [j.nome for j in camp.livres] + [j.nome for c in camp.clubes for j in c.jogadores]
    assert len(nomes) == len(set(nomes))
    assert all(j.contrato_anos == 0 for j in camp.livres)


def test_completar_corta_no_limite_ficando_os_melhores():
    camp = carregar_campeonato()
    extras = [livres.para_jogador(livres.gerar("Zagueiro", "jovem", set(), random.Random(i)))
              for i in range(livres.LIMITE)]
    for i, j in enumerate(extras):
        j.nome, j.overall = f"Extra {i}", 40
    camp.livres += extras

    livres.completar(camp, set(), random.Random(3))

    assert len(camp.livres) == livres.LIMITE
    assert min(j.overall for j in camp.livres) == 40   # os da seed ficaram
    assert sum(1 for j in camp.livres if j.overall == 40) == livres.LIMITE - livres.QUANTOS


def test_cpu_contrata_o_livre_que_rende_mais_que_a_base():
    camp = carregar_campeonato()
    clube = camp.clubes[5]
    goleiros = [j for j in clube.jogadores if j.posicao == "Goleiro"]
    clube.jogadores.remove(goleiros[0])          # falta 1 goleiro, elenco 22
    caixa = clube.dinheiro
    melhor = max((j for j in camp.livres if j.funcao == "Goleiro"), key=lambda j: j.overall)

    movs = livres.cpu_contrata(camp, camp.clubes[0].nome, random.Random(4))

    assert melhor in clube.jogadores and melhor not in camp.livres
    assert melhor.contrato_anos == mercado.CONTRATO_LIVRE_ANOS
    assert clube.dinheiro == caixa                 # na virada, sem luvas
    assert ("chegou_livre", melhor.nome, clube.nome) in {
        (m["tipo"], m["jogador"], m["clube"]) for m in movs
    }
    assert len(clube.jogadores) == base.TAMANHO_ALVO


def test_cpu_nao_contrata_livre_pior_que_a_base_nem_pelo_tecnico():
    camp = carregar_campeonato()
    for j in camp.livres:
        j.overall = 30
    for c in camp.clubes:
        del c.jogadores[20:]

    assert livres.cpu_contrata(camp, camp.clubes[0].nome, random.Random(5)) == []

    camp = carregar_campeonato()
    meu = camp.clubes[0]
    del meu.jogadores[20:]
    livres.cpu_contrata(camp, meu.nome, random.Random(5))
    assert len(meu.jogadores) == 20


def test_livres_envelhecem_e_sem_jogar_os_veteranos_caem():
    camp = carregar_campeonato()
    veterano = max(camp.livres, key=lambda j: j.idade)
    idade, overall = veterano.idade, veterano.overall

    envelhecer(camp, [], random.Random(6))

    assert veterano.idade == idade + 1
    assert veterano.overall <= overall


def test_livres_tambem_se_aposentam():
    camp = carregar_campeonato()
    for j in camp.livres:
        j.idade = 36
    aposentar(camp, SEMPRE)
    assert camp.livres == []

    camp = carregar_campeonato()
    aposentar(camp, NUNCA)
    assert len(camp.livres) == 50
