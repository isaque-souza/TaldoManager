"""Atributos do jogador (v1.3): de onde vêm e como pesam nos lances."""

import random
import statistics

from app.domain import atributos
from app.domain.clube import Clube
from app.domain.jogador import Jogador
from app.domain.partida import Partida
from app.domain.posicoes import SETOR


def _j(nome="Fulano", funcao="Centroavante", overall=80):
    return Jogador(nome, 25, SETOR[funcao], overall, funcao=funcao)


def test_linha_tem_os_seis_e_goleiro_os_dele():
    assert set(_j().atributos) == set(atributos.LINHA)
    assert set(_j(funcao="Goleiro").atributos) == set(atributos.GOLEIRO)


def test_perfil_da_posicao():
    ca, zag = _j("A", "Centroavante"), _j("A", "Zagueiro")
    assert ca.atributo("finalizacao") > zag.atributo("finalizacao")
    assert zag.atributo("marcacao") > ca.atributo("marcacao")
    ponta = _j("A", "Ponta")
    assert ponta.atributo("velocidade") > zag.atributo("velocidade")


def test_estilo_vem_do_nome_e_e_o_mesmo_sempre():
    a1, a2 = _j("Leonardo Silva"), _j("Leonardo Silva")
    b = _j("Pedro Costa")
    assert a1.atributos == a2.atributos
    assert a1.atributos != b.atributos   # dois CAs de 80 jogam diferente


def test_estilo_nao_muda_o_nivel():
    # o estilo soma ~0: a média dos atributos acompanha o overall
    for nome in ("Ana", "Bruno", "Caio", "Davi", "Edu"):
        estilo = atributos._estilo(nome, 6)
        assert abs(sum(estilo)) <= 3
        assert all(abs(e) <= atributos.ESTILO_MAX + 1 for e in estilo)


def test_atributos_acompanham_o_overall():
    j = _j(overall=75)
    antes = j.atributos
    j.overall = 80
    assert all(j.atributos[a] == min(99, v + 5) for a, v in antes.items())


def test_limites():
    craque = _j(overall=99)
    assert max(craque.atributos.values()) <= atributos.MAXIMO
    fraco = _j(funcao="Zagueiro", overall=40)
    assert min(fraco.atributos.values()) >= atributos.MINIMO


def test_calcular_a_partir_do_banco_bate_com_o_jogador():
    j = _j("Fulano", "Lateral", 82)
    assert atributos.calcular("Fulano", "Defesa", "Lateral", 82) == j.atributos
    # save antigo, sem posição específica: a padrão do setor
    assert atributos.calcular("Fulano", "Defesa", None, 82) == _j("Fulano", "Zagueiro", 82).atributos


# ---------------------------------------------------------------------------
# no motor
# ---------------------------------------------------------------------------

def _partida():
    casa, fora = Clube("Casa", "Brasil", 1), Clube("Fora", "Brasil", 1)
    return Partida(casa, fora)


def test_duelo_e_pelo_estilo_nao_pelo_nivel():
    p = _partida()
    # mesmo estilo, níveis diferentes: o duelo não muda (o nível já pesa na força)
    forte, fraco = _j("X", "Ponta", 85), _j("X", "Ponta", 70)   # sem bater no 99
    zag = _j("Y", "Zagueiro", 80)
    assert p.duelo(forte, zag) == p.duelo(fraco, zag)
    assert p.duelo(None, zag) == 0.0


def test_duelo_favorece_quem_e_rapido_e_dribla_contra_quem_marca_pouco():
    p = _partida()
    ponta = _j("Ponta", "Ponta")
    contra_zagueiro = p.duelo(ponta, _j("Zag", "Zagueiro"))
    contra_meia = p.duelo(ponta, _j("Meia", "Meia-atacante"))
    assert contra_meia > contra_zagueiro
    assert -Partida.DUELO_MAX <= contra_zagueiro <= Partida.DUELO_MAX


def test_goleiro_defende_pelos_reflexos_e_posicionamento():
    g = _j("Goleiro", "Goleiro", 80)
    nivel = (g.atributo("reflexos") + g.atributo("posicionamento")) / 2
    assert Partida.nivel_goleiro(g) == nivel
    # de linha no gol: o overall na vaga
    improvisado = _j("Zag", "Zagueiro", 80)
    improvisado.vaga = "Goleiro"
    assert Partida.nivel_goleiro(improvisado) == improvisado.overall_em_campo()


def test_quem_finaliza_melhor_e_escolhido_mais_para_chutar():
    # dois centroavantes de mesmo overall, finalização diferente
    nomes = [f"Atacante {i}" for i in range(40)]
    js = sorted((_j(n, "Centroavante", 82) for n in nomes), key=lambda j: j.atributo("finalizacao"))
    pior, melhor = js[0], js[-1]
    assert melhor.atributo("finalizacao") > pior.atributo("finalizacao")
    assert melhor.peso_gol() > pior.peso_gol()


def test_fisico_acima_do_nivel_cansa_menos():
    nomes = [f"Volante {i}" for i in range(40)]
    js = sorted((_j(n, "Volante", 80) for n in nomes),
                key=lambda j: j.atributo("fisico"))
    fraco, forte = js[0], js[-1]
    gastos = []
    for j in (fraco, forte):
        random.seed(1)
        total = 0
        for _ in range(200):
            j.energia = 100
            j.reduzir_energia()
            total += 100 - j.energia
        gastos.append(total)
    assert gastos[1] < gastos[0]
    assert isinstance(forte.energia, int)


def test_referencias_centradas_na_liga():
    # o lance típico sai como antes: as referências batem com a seed
    from scripts.data_loader import carregar_campeonato
    c = carregar_campeonato()
    tit = []
    for clube in c.clubes:
        clube.escalar_time()
        tit += [j for j in clube.titulares if j.posicao != "Goleiro"]
    fisico = statistics.mean(j.atributo("fisico") - j.overall for j in tit)
    assert abs(fisico - 1) < 1.5   # REF_FISICO
