"""Empréstimos (v1.7): regras puras."""

import pytest

from app.domain import emprestimo, financas, mercado
from app.domain.campeonato import Campeonato
from app.domain.clube import Clube
from app.domain.emprestimo import EmprestimoInvalido
from app.domain.jogador import Jogador

_POSICOES = ["Goleiro"] * 2 + ["Defesa"] * 6 + ["Meio-Campo"] * 5 + ["Atacante"] * 5


def _clube(nome, dinheiro=500_000_000, overall=75):
    clube = Clube(nome, "Brasil", dinheiro)
    for i, pos in enumerate(_POSICOES):
        clube.contratar_jogador(Jogador(f"{nome} {i}", 25, pos, overall))
    return clube


def _reserva(clube):
    """Um atacante a mais, pior que os titulares: o clube empresta."""
    j = Jogador(f"{clube.nome} reserva", 20, "Atacante", 68, potencial=82)
    clube.contratar_jogador(j)
    return j


def test_duracoes_por_janela():
    assert emprestimo.duracoes(1) == (emprestimo.TURNO, emprestimo.TEMPORADA)
    assert emprestimo.duracoes(20) == (emprestimo.TEMPORADA,)
    assert emprestimo.duracoes(5) == ()
    assert emprestimo.volta(emprestimo.TURNO, 38) == 20
    assert emprestimo.volta(emprestimo.TEMPORADA, 38) == 39


def test_validar():
    emprestimo.validar(1, "turno", 75)
    with pytest.raises(EmprestimoInvalido, match="fim da temporada"):
        emprestimo.validar(20, "turno", 75)
    with pytest.raises(EmprestimoInvalido, match="fechada"):
        emprestimo.validar(7, "temporada", 75)
    with pytest.raises(EmprestimoInvalido, match="parte do salário"):
        emprestimo.validar(1, "temporada", 60)


def test_quem_o_clube_empresta():
    cedente, tomador = _clube("A"), _clube("B")
    reserva = _reserva(cedente)
    assert emprestimo.motivo_nao_empresta(reserva, cedente, tomador) is None

    titular = next(j for j in cedente.jogadores if j.posicao == "Atacante")
    titular.overall = 90
    assert "titular" in emprestimo.motivo_nao_empresta(titular, cedente, tomador)

    reserva.fama, reserva.temporadas_no_clube = 100, 10   # ídolo
    assert "ídolo" in emprestimo.motivo_nao_empresta(reserva, cedente, tomador)
    reserva.fama, reserva.temporadas_no_clube = 0, 0

    cedente.rivais = {"B"}
    assert "rival" in emprestimo.motivo_nao_empresta(reserva, cedente, tomador)


def test_taxa_cai_com_o_salario_bancado_e_com_o_tempo():
    j = Jogador("X", 20, "Atacante", 75)
    total = 38
    taxas = [emprestimo.taxa_base(j, 1, "temporada", total, p) for p in (50, 75, 100)]
    assert taxas[0] > taxas[1] > taxas[2]
    assert emprestimo.taxa_base(j, 1, "turno", total, 75) < taxas[1]
    # 10% do valor pela temporada inteira, pagando 75% do salário
    assert taxas[1] == pytest.approx(j.valor_mercado() * 0.10, abs=10_000)


def test_avaliar_aceita_contrapropoe_ou_recusa():
    cedente, tomador = _clube("A"), _clube("B")
    j = _reserva(cedente)
    pedido = emprestimo.taxa_pedida(j, cedente, tomador, 1, "temporada", 38, 75)
    assert emprestimo.avaliar(j, cedente, tomador, 1, "temporada", 38, 75, pedido).fechou
    contra = emprestimo.avaliar(j, cedente, tomador, 1, "temporada", 38, 75, int(pedido * 0.9))
    assert contra.tipo == "contraproposta" and contra.valor == pedido
    assert emprestimo.avaliar(j, cedente, tomador, 1, "temporada", 38, 75, pedido // 3).tipo == "recusada"


def test_vai_jogar_no_tomador_baixa_a_taxa():
    cedente = _clube("A")
    j = _reserva(cedente)
    fraco = _clube("Fraco", overall=60)
    forte = _clube("Forte", overall=80)
    assert emprestimo.taxa_pedida(j, cedente, fraco, 1, "temporada", 38, 75) < \
        emprestimo.taxa_pedida(j, cedente, forte, 1, "temporada", 38, 75)


def test_opcao_de_compra_acima_do_preco_de_venda_e_ate_a_multa():
    cedente, tomador = _clube("A"), _clube("B")
    j = _reserva(cedente)
    assert emprestimo.preco_opcao(j, cedente, tomador) > mercado.preco_pedido(j, cedente, tomador)
    j.multa_rescisoria = 100_000
    assert emprestimo.preco_opcao(j, cedente, tomador) == 100_000


def test_emprestar_e_devolver():
    cedente, tomador = _clube("A"), _clube("B")
    j = _reserva(cedente)
    caixa_c, caixa_t = cedente.dinheiro, tomador.dinheiro
    emprestimo.emprestar(j, cedente, tomador, 20, 75, 300_000, opcao=5_000_000, emprestimo_id=7)

    assert j in tomador.jogadores and j not in cedente.jogadores
    assert j.emprestimo == {"de": "A", "volta": 20, "parte": 75, "opcao": 5_000_000, "id": 7}
    assert tomador.dinheiro == caixa_t - 300_000 and cedente.dinheiro == caixa_c + 300_000
    # o contrato é de lá: não vende, não dispensa
    assert "emprestado" in mercado.motivo_saida_bloqueada(tomador, j)
    with pytest.raises(EmprestimoInvalido, match="já está emprestado"):
        emprestimo.emprestar(j, tomador, cedente, 20, 75, 300_000)

    assert emprestimo.devolver_vencidos([cedente, tomador], 19) == []
    assert emprestimo.devolver_vencidos([cedente, tomador], 20) == [(j, tomador, cedente)]
    assert j in cedente.jogadores and j.emprestimo is None


def test_salario_dividido():
    cedente, tomador = _clube("A"), _clube("B")
    j = _reserva(cedente)
    j.salario = 100_000
    folha_c, folha_t = financas.folha_salarial(cedente), financas.folha_salarial(tomador)
    emprestimo.emprestar(j, cedente, tomador, 20, 75, 10_000)

    cedidos = financas.salarios_cedidos([cedente, tomador])
    assert cedidos == {"A": 25_000}
    assert financas.folha_salarial(tomador) == folha_t + 75_000
    assert financas.folha_salarial(cedente, cedidos["A"]) == folha_c - 75_000


def test_o_campeonato_devolve_na_rodada_certa():
    a, b, c, d = (_clube(n) for n in "ABCD")
    camp = Campeonato("Liga", [a, b, c, d])
    j = _reserva(a)
    emprestimo.emprestar(j, a, b, 3, 100, 10_000)   # joga as rodadas 1 e 2

    camp.jogar_rodada()
    assert j in b.jogadores and camp.devolvidos == []
    camp.jogar_rodada()
    assert j in a.jogadores and camp.devolvidos == [(j, b, a)]


# --- o técnico empresta os dele (parte 2) ---

def test_quem_quer_o_jogador_do_tecnico():
    tecnico = _clube("T")
    fraco, forte, rival = _clube("Fraco", overall=60), _clube("Forte", overall=90), _clube("Rival", overall=60)
    tecnico.rivais = {"Rival"}
    j = _reserva(tecnico)

    propostas = emprestimo.propostas_de_cessao(j, tecnico, [tecnico, fraco, forte, rival], 1, "temporada", 38)
    clubes = [p.clube.nome for p in propostas]
    assert "Rival" not in clubes and "T" not in clubes
    assert clubes[0] == "Fraco" and propostas[0].titular
    assert all(p.taxa >= emprestimo.TAXA_MINIMA for p in propostas)


def test_a_parte_do_salario_vem_do_caixa():
    j = Jogador("X", 20, "Atacante", 70)
    j.salario = 1_000_000
    assert emprestimo.parte_que_banca(_clube("Rico", dinheiro=50_000_000), j) == 100
    assert emprestimo.parte_que_banca(_clube("Medio", dinheiro=10_000_000), j) == 75
    assert emprestimo.parte_que_banca(_clube("Pobre", dinheiro=1_000_000), j) == 50


def test_o_tecnico_empresta_ate_titular_mas_nao_idolo():
    tecnico, outro = _clube("T"), _clube("O", overall=60)
    titular = next(j for j in tecnico.jogadores if j.posicao == "Atacante")
    assert emprestimo.motivo_nao_cede(titular, tecnico) is None
    emprestimo.emprestar(titular, tecnico, outro, 20, 100, 10_000, pelo_tecnico=True)
    assert titular in outro.jogadores and titular.emprestimo["de"] == "T"
    assert "já está emprestado" in emprestimo.motivo_nao_cede(titular, outro)

    idolo = next(j for j in tecnico.jogadores if j.posicao == "Meio-Campo")
    idolo.fama, idolo.temporadas_no_clube = 100, 10
    assert "ídolo" in emprestimo.motivo_nao_cede(idolo, tecnico)
