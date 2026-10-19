"""Lista de transferências e dispensa (v1.7)."""

import pytest

from app.domain import fama, livres, mercado, torcida
from app.domain.clube import Clube
from app.domain.jogador import Jogador
from app.domain.mercado import TransferenciaInvalida

_POSICOES = ["Goleiro"] * 2 + ["Defesa"] * 6 + ["Meio-Campo"] * 5 + ["Atacante"] * 5


def _clube(nome="A", dinheiro=50_000_000, n=18):
    clube = Clube(nome, "Brasil", dinheiro)
    for i, pos in enumerate(_POSICOES[:n]):
        clube.contratar_jogador(Jogador(f"{nome} {i}", 25, pos, 75))
    return clube


def _atacante(clube):
    return next(j for j in clube.jogadores if j.posicao == "Atacante")


def test_rescisao_e_metade_dos_salarios_que_o_contrato_ainda_deve():
    jogador = Jogador("X", 25, "Atacante", 75, contrato_anos=3, salario=1_000_000)
    assert mercado.rescisao(jogador) == 1_500_000
    jogador.contrato_anos = 0
    assert mercado.rescisao(jogador) == 0


def test_dispensar_paga_a_rescisao_e_manda_para_os_livres():
    clube = _clube()
    jogador = _atacante(clube)
    jogador.a_venda = True
    clube.xi_preferido.add(jogador)
    custo = mercado.rescisao(jogador)
    lista = []

    assert livres.dispensar(jogador, clube, lista) == custo

    assert jogador not in clube.jogadores and jogador not in clube.xi_preferido
    assert lista == [jogador]
    assert clube.dinheiro == 50_000_000 - custo
    assert clube.despesa_salarios == custo
    # sem clube: sem contrato, sem tempo de casa, fora da lista
    assert jogador.contrato_anos == 0 and jogador.multa_rescisoria is None
    assert jogador.temporadas_no_clube == 0 and not jogador.a_venda


def test_dispensa_respeita_o_elenco_minimo_e_os_goleiros():
    clube = _clube(n=mercado.ELENCO_MIN)
    assert mercado.motivo_dispensa_bloqueada(clube, _atacante(clube))
    with pytest.raises(TransferenciaInvalida):
        livres.dispensar(_atacante(clube), clube, [])

    clube = _clube()
    goleiro = clube.jogadores[0]
    assert "goleiros" in mercado.motivo_dispensa_bloqueada(clube, goleiro)


def test_dispensa_precisa_de_caixa_para_a_rescisao():
    clube = _clube(dinheiro=10_000)
    jogador = _atacante(clube)
    assert "rescisão" in mercado.motivo_dispensa_bloqueada(clube, jogador)
    with pytest.raises(TransferenciaInvalida):
        livres.dispensar(jogador, clube, [])
    assert jogador in clube.jogadores


def test_so_dispensa_quem_e_do_clube():
    outro = _clube("B")
    with pytest.raises(TransferenciaInvalida):
        livres.dispensar(_atacante(outro), _clube(), [])


def test_dispensar_um_idolo_irrita_a_torcida():
    clube = _clube()
    clube.torcedores = 1_000_000
    comum, idolo = clube.jogadores[-1], clube.jogadores[-2]
    idolo.fama, idolo.temporadas_no_clube = fama.LIMIAR_IDOLO, fama.TEMPORADAS_IDOLO

    assert torcida.reagir_a_dispensa(clube, comum) is None
    assert clube.torcedores == 1_000_000

    antes, depois = torcida.reagir_a_dispensa(clube, idolo)
    assert antes == 1_000_000
    assert depois == round(1_000_000 * (1 + torcida.VENDA_IDOLO))


def test_quem_muda_de_clube_sai_da_lista_de_transferencias():
    vendedor, comprador = _clube("A"), _clube("B")
    jogador = _atacante(vendedor)
    jogador.a_venda = True
    mercado.transferir(jogador, vendedor, comprador, 1_000_000)
    assert not jogador.a_venda
