"""Posições específicas e overall por posição (v1.3)."""

import pytest

from app.domain import posicoes
from app.domain.clube import Clube
from app.domain.jogador import Jogador
from app.domain.partida import Partida, motivo_goleiro
from scripts.data_loader import carregar_campeonato


def _j(nome, funcao, overall=80, secundarias=()):
    return Jogador(nome, 25, posicoes.SETOR[funcao], overall,
                   funcao=funcao, secundarias=secundarias)


def _time_completo(nome="FC Teste", overall=80):
    """4-3-3 com cada um na sua posição, mais um reserva por posição."""
    clube = Clube(nome, "Brasil", 1_000_000)
    for f, n in (("Goleiro", 2), ("Zagueiro", 3), ("Lateral", 3),
                 ("Volante", 2), ("Meia", 3), ("Ponta", 3),
                 ("Centroavante", 2)):
        for i in range(n):
            # o primeiro de cada posição é o melhor (titular natural)
            clube.contratar_jogador(_j(f"{nome} {f} {i}", f, overall - 5 * i))
    return clube


# ---------------------------------------------------------------------------
# tabela de perdas
# ---------------------------------------------------------------------------

def test_volante_de_zagueiro_perde_seis():
    volante = _j("V", "Volante", 80)
    assert volante.overall_em("Volante") == 80
    assert volante.overall_em("Zagueiro") == 74


def test_perda_e_simetrica_e_cresce_com_a_distancia():
    for (a, b), p in posicoes._PERDA.items():
        assert posicoes.perda(a, b) == posicoes.perda(b, a) == p
    assert posicoes.perda("Zagueiro", "Lateral") < posicoes.perda("Zagueiro", "Ponta")


def test_secundaria_perde_pouco():
    lateral = _j("L", "Lateral", 80, secundarias=("Ponta",))
    assert lateral.overall_em("Ponta") == 80 - posicoes.PERDA_SECUNDARIA
    assert lateral.overall_em("Centroavante") == 80 - 16


def test_goleiro_na_linha_e_linha_no_gol_perdem_muito():
    assert _j("G", "Goleiro").overall_em("Zagueiro") == 80 - posicoes.PERDA_GOLEIRO
    assert _j("Z", "Zagueiro").overall_em("Goleiro") == 80 - posicoes.PERDA_GOLEIRO


def test_vagas_batem_com_os_setores_de_cada_formacao():
    for formacao, (n_def, n_mei, n_ata) in Clube.FORMACOES.items():
        setores = [posicoes.SETOR[v] for v in posicoes.VAGAS[formacao]]
        assert setores.count("Defesa") == n_def, formacao
        assert setores.count("Meio-Campo") == n_mei, formacao
        assert setores.count("Atacante") == n_ata, formacao
        assert posicoes.vagas(formacao)[0] == "Goleiro"


def test_jogador_sem_posicao_especifica_joga_em_todo_o_setor():
    # jovens da base de saves de antes da v1.3
    j = Jogador("Antigo", 20, "Defesa", 75)
    assert j.funcao == "Zagueiro"
    assert j.overall_em("Lateral") == 75 - posicoes.PERDA_SECUNDARIA
    assert j.overall_em("Volante") == 75 - 6


def test_posicao_fora_do_setor_e_recusada():
    with pytest.raises(ValueError):
        Jogador("Errado", 20, "Defesa", 75, funcao="Ponta")


# ---------------------------------------------------------------------------
# escalação por vagas
# ---------------------------------------------------------------------------

def test_escala_cada_um_na_sua_posicao():
    clube = _time_completo()
    clube.escalar_time()

    assert len(clube.titulares) == 11
    assert [j.vaga for j in clube.titulares] == list(posicoes.vagas("4-3-3"))
    assert all(j.vaga == j.funcao for j in clube.titulares)
    assert all(j.vaga is None for j in clube.reservas)


def test_escolher_um_volante_no_lugar_do_zagueiro_improvisa_ele_na_zaga():
    clube = _time_completo()
    clube.escalar_time()
    titulares = list(clube.titulares)
    zagueiro = next(j for j in titulares if j.vaga == "Zagueiro")
    volante_reserva = next(
        j for j in clube.reservas if j.funcao == "Volante"
    )
    xi = [j for j in titulares if j is not zagueiro] + [volante_reserva]
    clube.xi_preferido = set(xi)

    clube.escalar_time()

    assert volante_reserva in clube.titulares
    assert zagueiro not in clube.titulares
    assert volante_reserva.vaga == "Zagueiro"
    assert volante_reserva.overall_em_campo() == volante_reserva.overall - 6


def test_qualquer_jogador_de_linha_pode_ir_para_qualquer_vaga():
    clube = _time_completo()
    clube.escalar_time()
    titulares = list(clube.titulares)
    lateral = next(j for j in titulares if j.vaga == "Lateral")
    centroavante = next(j for j in clube.reservas if j.funcao == "Centroavante")
    clube.xi_preferido = set(
        [j for j in titulares if j is not lateral] + [centroavante]
    )

    clube.escalar_time()

    assert centroavante in clube.titulares
    assert len(clube.titulares) == 11


def test_improvisado_derruba_a_forca():
    natural = _time_completo()
    natural.escalar_time()

    improvisado = _time_completo()
    improvisado.escalar_time()
    ponta = next(j for j in improvisado.titulares if j.vaga == "Ponta")
    zagueiro = next(j for j in improvisado.reservas if j.funcao == "Zagueiro")
    zagueiro.overall = ponta.overall   # mesmo overall: só a posição pesa
    improvisado.xi_preferido = set(
        [j for j in improvisado.titulares if j is not ponta] + [zagueiro]
    )
    improvisado.escalar_time()

    # três zagueiros para duas vagas: um deles joga fora da posição
    assert any(j.vaga != j.funcao for j in improvisado.titulares)
    assert improvisado.calcular_forca() < natural.calcular_forca()


def test_goleiro_escolhido_nao_vai_para_a_linha():
    clube = _time_completo()
    goleiros = [j for j in clube.jogadores if j.funcao == "Goleiro"]
    clube.xi_preferido = set(goleiros)

    clube.escalar_time()

    no_xi = [j for j in clube.titulares if j.funcao == "Goleiro"]
    assert len(no_xi) == 1 and no_xi[0].vaga == "Goleiro"


def test_sem_goleiro_disponivel_um_jogador_de_linha_vai_para_o_gol():
    clube = _time_completo()
    for g in [j for j in clube.jogadores if j.funcao == "Goleiro"]:
        g.rodadas_lesao = 3

    clube.escalar_time()

    assert len(clube.titulares) == 11
    assert clube.titulares[0].vaga == "Goleiro"
    assert clube.titulares[0].funcao != "Goleiro"


def test_faltando_zagueiro_improvisa_quem_sabe_jogar_ali():
    clube = _time_completo()
    for z in [j for j in clube.jogadores if j.funcao == "Zagueiro"]:
        z.jogos_suspensao = 1

    clube.escalar_time()

    na_zaga = [j for j in clube.titulares if j.vaga == "Zagueiro"]
    assert len(na_zaga) == 2
    # vizinhos da zaga (lateral, volante) perdem 6; um meia perderia 14
    assert all(j.funcao in ("Lateral", "Volante") for j in na_zaga)


def test_xi_mantido_numa_formacao_nova_perde_o_minimo_somado():
    # o XI do 4-3-3 (com 2 pontas) mantido num 5-3-2, que não tem ponta:
    # o melhor é um ponta no ataque, o outro na lateral e um lateral
    # recuando para a zaga — não um ponta de zagueiro (perde 18)
    clube = _time_completo()
    clube.escalar_time()
    clube.xi_preferido = set(clube.titulares)
    clube.formacao = "5-3-2"

    clube.escalar_time()

    assert set(clube.titulares) == clube.xi_preferido
    perda = sum(j.overall - j.overall_em_campo() for j in clube.titulares)
    assert perda == 5 + 8 + 6   # PON→CA, PON→LAT, LAT→ZAG
    assert not any(
        j.funcao == "Ponta" and j.vaga == "Zagueiro" for j in clube.titulares
    )


def test_menor_custo_acha_o_otimo_que_o_guloso_perde():
    # guloso pegaria o 1 da linha 0 e pagaria 9 na linha 1; o ótimo é 2 + 2
    assert posicoes.menor_custo([[1, 2], [9, 2]]) == [0, 1]
    assert posicoes.menor_custo([[1, 2], [2, 9]]) == [1, 0]


def test_formacao_muda_as_vagas():
    clube = _time_completo()
    clube.formacao = "4-4-2"
    clube.escalar_time()
    assert sum(j.vaga == "Centroavante" for j in clube.titulares) == 2
    assert sum(j.vaga == "Ponta" for j in clube.titulares) == 0


# ---------------------------------------------------------------------------
# substituição
# ---------------------------------------------------------------------------

def test_quem_entra_herda_a_vaga_de_quem_sai():
    casa, fora = _time_completo("Casa"), _time_completo("Fora")
    casa.escalar_time()
    fora.escalar_time()
    p = Partida(casa, fora)
    p.preparar_partida()
    p.criar_estatisticas()
    sai = next(j for j in casa.titulares if j.vaga == "Lateral")
    entra = next(j for j in casa.reservas if j.funcao == "Ponta")

    p._trocar(casa, sai, entra, 60)

    assert entra.vaga == "Lateral"
    assert sai.vaga is None
    assert entra.overall_em_campo() == entra.overall - 8


def test_goleiro_so_troca_com_goleiro():
    assert motivo_goleiro("Goleiro", "Goleiro") is None
    assert motivo_goleiro("Defesa", "Atacante") is None
    assert motivo_goleiro("Goleiro", "Defesa")
    assert motivo_goleiro("Meio-Campo", "Goleiro")

    casa, fora = _time_completo("Casa"), _time_completo("Fora")
    casa.escalar_time()
    fora.escalar_time()
    p = Partida(casa, fora)
    p.preparar_partida()
    p.criar_estatisticas()
    goleiro = casa.titulares[0]
    linha = next(j for j in casa.reservas if j.posicao != "Goleiro")
    assert p.motivo_substituicao_invalida(casa, goleiro.nome, linha.nome)


# ---------------------------------------------------------------------------
# seed
# ---------------------------------------------------------------------------

def test_todo_elenco_da_seed_cabe_em_qualquer_formacao():
    # gente de cada posição para todas as vagas, sem precisar improvisar
    # (o motor ainda pode improvisar um craque, quando rende mais)
    for clube in carregar_campeonato().clubes:
        tem = {f: sum(j.funcao == f for j in clube.jogadores) for f in posicoes.FUNCOES}
        for formacao in Clube.FORMACOES:
            vagas = posicoes.vagas(formacao)
            for f in posicoes.FUNCOES:
                assert tem[f] >= vagas.count(f), (clube.nome, formacao, f)
            clube.formacao = formacao
            clube.escalar_time()
            assert len(clube.titulares) == 11
