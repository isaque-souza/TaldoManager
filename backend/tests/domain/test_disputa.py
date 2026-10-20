"""Disputa pela contratação (v1.9, passo 3): regras puras."""

import random

from app.domain import contrato, disputa, papeis
from app.domain.clube import Clube
from app.domain.jogador import Jogador

_POSICOES = ["Goleiro"] * 2 + ["Defesa"] * 6 + ["Meio-Campo"] * 6 + ["Atacante"] * 4


def _clube(nome, overall=75, torcedores=1_000_000, dinheiro=500_000_000):
    clube = Clube(nome, "Brasil", dinheiro, torcedores)
    for i, pos in enumerate(_POSICOES):
        clube.contratar_jogador(Jogador(f"{nome} {i}", 25, pos, overall + i % 3))
    return clube


def _cenario():
    """O técnico (médio) compra o craque do vendedor; dois clubes da CPU
    poderiam entrar: um gigante e um pequeno."""
    tecnico, vendedor = _clube("Técnico", 75), _clube("Vendedor", 75)
    gigante = _clube("Gigante", 80, torcedores=9_000_000)
    pequeno = _clube("Pequeno", 70, torcedores=100_000)
    craque = Jogador("Craque", 26, "Atacante", 88)
    vendedor.contratar_jogador(craque)
    return craque, vendedor, tecnico, [tecnico, vendedor, gigante, pequeno]


class _SempreEntra(random.Random):
    def random(self):
        return 0.0


def test_craque_tem_mais_chance_de_ter_disputa():
    comum = Jogador("Comum", 25, "Atacante", 75)
    craque = Jogador("Craque", 25, "Atacante", disputa.OVERALL_CRAQUE)
    assert disputa.chance(craque) == disputa.chance(comum) + disputa.CHANCE_CRAQUE


def test_entra_o_clube_que_o_jogador_mais_quer():
    craque, vendedor, tecnico, clubes = _cenario()
    c = disputa.concorrente(craque, vendedor, tecnico, 1_000_000, clubes, _SempreEntra(1))
    assert c.clube.nome == "Gigante"
    assert c.salario > 0 and c.fator < 1   # ele gosta do gigante


def test_sem_sorte_ou_sem_quem_possa_pagar_nao_ha_disputa():
    craque, vendedor, tecnico, clubes = _cenario()

    class _NuncaEntra(random.Random):
        def random(self):
            return 0.99

    assert disputa.concorrente(craque, vendedor, tecnico, 1_000_000, clubes, _NuncaEntra(1)) is None
    # ninguém tem caixa para o valor acertado
    assert disputa.concorrente(craque, vendedor, tecnico, 10**12, clubes, _SempreEntra(1)) is None


def test_quem_nao_vem_nao_entra_na_disputa():
    craque, vendedor, tecnico, clubes = _cenario()
    gigante = clubes[2]
    rival_do_gigante = clubes[3]
    gigante.rivais = {"Pequeno"}
    craque.clube_historia = rival_do_gigante.nome   # fez história no Pequeno
    c = disputa.concorrente(craque, vendedor, tecnico, 1_000_000, clubes, _SempreEntra(1))
    assert c is None or c.clube is not gigante


def test_o_mesmo_save_sorteia_o_mesmo_concorrente():
    craque, vendedor, tecnico, clubes = _cenario()
    a = disputa.concorrente(craque, vendedor, tecnico, 1_000_000, clubes, disputa.semente(7, 1, "Craque"))
    b = disputa.concorrente(craque, vendedor, tecnico, 1_000_000, clubes, disputa.semente(7, 1, "Craque"))
    assert (a and (a.clube.nome, a.salario)) == (b and (b.clube.nome, b.salario))


def test_para_bater_pesa_os_dois_interesses():
    # ele adora o concorrente (0,85) e resiste ao técnico (1,2)
    assert disputa.salario_para_bater(10_000_000, 0.85, 1.2) == 14_118_000
    # gostando igual, basta igualar
    assert disputa.salario_para_bater(10_000_000, 1.0, 1.0) == 10_000_000


def test_o_tecnico_ve_o_salario_arredondado():
    assert disputa.aproximado(827_000) == 830_000
    assert disputa.aproximado(12_340_000) == 12_000_000
    assert disputa.aproximado(95_000) == 95_000


def test_contrato_abaixo_do_concorrente_perde_para_ele():
    craque, vendedor, tecnico, _ = _cenario()
    pedido = contrato.salario_pedido_chegada(craque, tecnico, vendedor, "3x", papeis.TITULAR)
    bater = pedido * 2
    perde = contrato.avaliar_chegada(
        craque, tecnico, vendedor, pedido, 3, "3x", papeis.TITULAR,
        para_bater=bater, concorrente="Gigante",
    )
    assert perde.tipo == "recusada" and perde.valor == bater
    assert "prefere a proposta do Gigante" in perde.motivo
    ganha = contrato.avaliar_chegada(
        craque, tecnico, vendedor, bater, 3, "3x", papeis.TITULAR,
        para_bater=bater, concorrente="Gigante",
    )
    assert ganha.tipo == "aceita"


def test_concorrente_mais_barato_que_o_pedido_nao_muda_nada():
    craque, vendedor, tecnico, _ = _cenario()
    pedido = contrato.salario_pedido_chegada(craque, tecnico, vendedor, "3x", papeis.TITULAR)
    r = contrato.avaliar_chegada(
        craque, tecnico, vendedor, pedido, 3, "3x", papeis.TITULAR,
        para_bater=pedido // 2, concorrente="Gigante",
    )
    assert r.tipo == "aceita"
