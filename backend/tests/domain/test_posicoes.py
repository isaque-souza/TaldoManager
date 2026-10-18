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
    """Cada posição com gente para o 4-3-3 e para o 4-2-3-1, todos com o
    mesmo overall: só a posição decide quem joga onde."""
    clube = Clube(nome, "Brasil", 1_000_000)
    for f, n in (("Goleiro", 2), ("Zagueiro", 3), ("Lateral", 3),
                 ("Volante", 2), ("Meia central", 3), ("Meia-atacante", 2),
                 ("Ponta", 3), ("Segundo atacante", 2), ("Centroavante", 2)):
        for i in range(n):
            clube.contratar_jogador(_j(f"{nome} {f} {i}", f, overall))
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
    clube.formacao = "4-2-3-1"
    clube.escalar_time()
    vagas = [j.vaga for j in clube.titulares]
    assert vagas.count("Volante") == 2
    assert vagas.count("Meia-atacante") == 1
    assert vagas.count("Centroavante") == 1
    assert "Meia central" not in vagas


def test_desenho_de_cada_formacao():
    for formacao, desenho in posicoes.DESENHO.items():
        assert len(desenho) == 10, formacao
        for funcao, x, y, rotulo in posicoes.desenho(formacao):
            assert funcao in posicoes.FUNCOES
            assert 0 <= x <= 100 and 0 <= y <= 100
            assert rotulo


def test_desenho_segue_as_regras_de_profundidade_e_largura():
    def onde(formacao, rotulo):
        return [(x, y) for _, x, y, r in posicoes.desenho(formacao) if r == rotulo]

    # laterais na linha da zaga, um pouco à frente e abertos
    (le_x, le_y), = onde("4-3-3", "LE")
    zag = onde("4-3-3", "ZAG")
    assert all(le_y > y and le_x < x for x, y in zag)
    # volante atrás do meia central; meia-atacante à frente dos dois
    vol_y = max(y for _, y in onde("4-1-2-1-2", "VOL"))
    mc_y = min(y for _, y in onde("4-1-2-1-2", "MC"))
    (_, mei_y), = onde("4-1-2-1-2", "MEI")
    assert vol_y < mc_y < mei_y
    # segundo atacante entre o meio e o centroavante
    (_, sa_y), = onde("4-4-1-1", "SA")
    (_, ca_y), = onde("4-4-1-1", "CA")
    assert max(y for _, y in onde("4-4-1-1", "MC")) < sa_y < ca_y
    # pontas abertos; alas de um 5 atrás mais à frente que os laterais de 4
    assert all(x < 20 or x > 80 for x, _ in onde("4-3-3", "PE") + onde("4-3-3", "PD"))
    assert min(y for _, y in onde("5-3-2", "ALA")) > le_y


def test_nome_antigo_de_meia_vira_meia_central():
    j = Jogador("Antigo", 25, "Meio-Campo", 80, funcao="Meia", secundarias=["Meia"])
    assert j.funcao == "Meia central"
    assert j.secundarias == ("Meia central",)


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


# ---------------------------------------------------------------------------
# posicionamento do técnico
# ---------------------------------------------------------------------------

def _posicionado(clube):
    return {"formacao": clube.formacao, "nomes": [j.nome for j in _por_slot(clube)]}


def _por_slot(clube):
    return sorted(clube.titulares, key=lambda j: j.slot)


def test_trocar_dois_titulares_de_vaga_e_respeitado():
    clube = _time_completo()
    clube.escalar_time()
    clube.xi_preferido = set(clube.titulares)
    pos = _posicionado(clube)
    # o lateral esquerdo (vaga 1) e o ponta direito trocam de lugar
    i = pos["nomes"].index(next(j.nome for j in clube.titulares if j.vaga == "Lateral"))
    k = max(n for n, v in enumerate(posicoes.vagas("4-3-3")) if v == "Ponta")
    pos["nomes"][i], pos["nomes"][k] = pos["nomes"][k], pos["nomes"][i]
    clube.posicionamento = pos

    clube.escalar_time()

    assert [j.nome for j in _por_slot(clube)] == pos["nomes"]
    lateral = next(j for j in clube.titulares if j.funcao == "Lateral" and j.slot == k)
    assert lateral.vaga == "Ponta"


def test_posicionamento_de_outra_formacao_e_ignorado():
    clube = _time_completo()
    clube.escalar_time()
    clube.xi_preferido = set(clube.titulares)
    pos = _posicionado(clube)
    pos["nomes"][1], pos["nomes"][-1] = pos["nomes"][-1], pos["nomes"][1]
    clube.posicionamento = pos
    clube.formacao = "4-2-3-1"

    clube.escalar_time()

    # no desenho novo, o motor distribui pela menor perda
    assert all(j.vaga == j.funcao or j.funcao == "Meia central" for j in clube.titulares)


def test_goleiro_posicionado_na_linha_nao_vale():
    clube = _time_completo()
    clube.escalar_time()
    clube.xi_preferido = set(clube.titulares)
    pos = _posicionado(clube)
    pos["nomes"][0], pos["nomes"][1] = pos["nomes"][1], pos["nomes"][0]
    clube.posicionamento = pos

    clube.escalar_time()

    assert _por_slot(clube)[0].funcao == "Goleiro"
    assert all(j.vaga != "Goleiro" for j in clube.titulares if j.funcao != "Goleiro")


def test_vaga_de_quem_esta_exausto_fica_com_outro():
    clube = _time_completo()
    clube.escalar_time()
    clube.xi_preferido = set(clube.titulares)
    clube.posicionamento = _posicionado(clube)
    cansado = _por_slot(clube)[2]
    cansado.energia = 10
    cansado.atualizar_condicao()

    clube.escalar_time()

    assert cansado not in clube.titulares
    assert len(clube.titulares) == 11
