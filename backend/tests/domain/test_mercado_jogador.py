"""Dados de mercado do Jogador (v0.7): potencial, contrato, valor e salário."""

from app.domain.jogador import Jogador


def _jogador(idade=25, overall=80, potencial=None):
    return Jogador("Teste", idade, "Atacante", overall, potencial=potencial)


def test_potencial_padrao_e_o_proprio_overall():
    assert _jogador(overall=80).potencial == 80


def test_potencial_nunca_fica_abaixo_do_overall():
    assert _jogador(overall=80, potencial=70).potencial == 80


def test_contrato_padrao_de_tres_temporadas():
    assert _jogador().contrato_anos == 3


def test_overall_maior_vale_mais():
    assert _jogador(overall=85).valor_mercado() > _jogador(overall=80).valor_mercado()


def test_valor_cresce_mais_que_linearmente():
    # um 90 deve valer mais que dois 80 juntos
    assert _jogador(overall=90).valor_mercado() > 2 * _jogador(overall=80).valor_mercado()


def test_jovem_vale_mais_que_veterano_de_mesmo_overall():
    assert _jogador(idade=20).valor_mercado() > _jogador(idade=34).valor_mercado()


def test_potencial_alto_valoriza_jovem():
    sem_margem = _jogador(idade=19, overall=75, potencial=75)
    promessa = _jogador(idade=19, overall=75, potencial=88)
    assert promessa.valor_mercado() > sem_margem.valor_mercado()


def test_potencial_nao_pesa_para_quem_ja_passou_da_idade_de_evoluir():
    a = _jogador(idade=28, overall=80, potencial=80)
    b = _jogador(idade=28, overall=80, potencial=83)
    assert a.valor_mercado() == b.valor_mercado()


def test_valor_e_salario_tem_piso_e_sao_arredondados():
    fraco = _jogador(idade=36, overall=40)
    assert fraco.valor_mercado() >= 10_000
    assert fraco.salario_referencia() >= 1_000
    craque = _jogador(overall=92)
    assert craque.valor_mercado() % 10_000 == 0
    assert craque.salario_referencia() % 1_000 == 0


def test_salario_depende_do_overall_nao_da_idade():
    assert _jogador(idade=19).salario_referencia() == _jogador(idade=33).salario_referencia()
    assert _jogador(overall=88).salario_referencia() > _jogador(overall=78).salario_referencia()


def test_salario_e_bem_menor_que_o_valor():
    j = _jogador(overall=85)
    assert j.salario_referencia() < j.valor_mercado() / 5


def test_salario_de_contrato_comeca_no_de_referencia_e_fica_fixo():
    j = _jogador(overall=80)
    assert j.salario == j.salario_referencia()
    j.overall = 88   # evoluiu: o contrato não muda sozinho
    assert j.salario < j.salario_referencia()


def test_salario_de_contrato_informado():
    j = Jogador("Teste", 25, "Atacante", 80, salario=123_000)
    assert j.salario == 123_000
