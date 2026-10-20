"""Vontade do jogador (v1.9): prestígio, formador, clube da história e sonho."""

import random
from types import SimpleNamespace

from app.domain import base, mercado, vontade
from app.domain.clube import Clube
from app.domain.jogador import Jogador
from app.domain.temporada import restaurar_estado, snapshot_estado
from scripts.data_loader import TODAS_AS_LIGAS, carregar_campeonato

POSICOES = ["Goleiro"] * 2 + ["Defesa"] * 6 + ["Meio-Campo"] * 6 + ["Atacante"] * 4


def _clube(nome, pais="Itália", overall=75, torcedores=1_000_000):
    clube = Clube(nome, pais, 50_000_000, torcedores)
    for i, posicao in enumerate(POSICOES):
        clube.contratar_jogador(Jogador(f"{nome} {i}", 25, posicao, overall))
    return clube


def _liga():
    """Três italianos (um gigante), um inglês forte e um brasileiro."""
    clubes = [
        _clube("Inter", overall=85, torcedores=5_000_000),
        _clube("Milan", overall=80, torcedores=4_000_000),
        _clube("Empoli", overall=65, torcedores=200_000),
        _clube("City", "Inglaterra", overall=86, torcedores=3_000_000),
        _clube("Bahia", "Brasil", overall=68, torcedores=2_000_000),
    ]
    return SimpleNamespace(clubes=clubes, livres=[])


def _clube_de(liga, nome):
    return next(c for c in liga.clubes if c.nome == nome)


def test_prestigio_vem_da_forca_e_da_torcida():
    liga = _liga()
    prest = vontade.prestigio(liga.clubes)
    assert prest["Inter"] > prest["Milan"] > prest["Empoli"]
    assert prest["Empoli"] == 0   # o mais fraco e com menos torcida
    assert all(0 <= p <= 100 for p in prest.values())


def test_jovem_e_cria_do_clube_onde_esta():
    liga = _liga()
    empoli = _clube_de(liga, "Empoli")
    jovem = Jogador("Garoto", vontade.IDADE_CRIA, "Atacante", 60)
    assert vontade.formador_inicial(jovem, empoli, liga.clubes) == "Empoli"


def test_formador_e_o_mesmo_em_toda_execucao():
    liga = _liga()
    inter = _clube_de(liga, "Inter")
    veterano = Jogador("Fulano de Tal", 30, "Atacante", 80)
    primeiro = vontade.formador_inicial(veterano, inter, liga.clubes)
    assert primeiro in {c.nome for c in liga.clubes}
    assert vontade.formador_inicial(veterano, inter, liga.clubes) == primeiro


def test_livre_tambem_tem_formador():
    liga = _liga()
    livre = Jogador("Sem Clube", 28, "Defesa", 70)
    assert vontade.formador_inicial(livre, None, liga.clubes) in {c.nome for c in liga.clubes}


def test_jovem_sonha_com_um_grande_do_pais_ou_do_mundo():
    liga = _liga()
    prest = vontade.prestigio(liga.clubes)
    grandes = {"Inter", "Milan", "Empoli", "City", "Bahia"}   # liga pequena: todos cabem
    for i in range(40):
        jogador = Jogador(f"Jogador {i}", 24, "Atacante", 70)
        jogador.formador = "Empoli"
        assert vontade.sonho(jogador, liga.clubes, prest) in grandes


def test_sonho_nacional_e_do_pais_onde_foi_formado():
    liga = _liga()
    prest = vontade.prestigio(liga.clubes)
    # formado na Itália: os grandes italianos aparecem entre os sonhos
    sonhos = set()
    for i in range(60):
        jogador = Jogador(f"Italiano {i}", 22, "Meio-Campo", 70)
        jogador.formador = "Empoli"
        sonhos.add(vontade.sonho(jogador, liga.clubes, prest))
    assert {"Inter", "Milan"} <= sonhos


def test_veterano_quer_encerrar_no_formador():
    liga = _liga()
    prest = vontade.prestigio(liga.clubes)
    veterano = Jogador("Velho Lobo", vontade.IDADE_APOSENTADORIA, "Defesa", 75)
    veterano.formador = "Bahia"
    assert vontade.sonho(veterano, liga.clubes, prest) == "Bahia"


def test_veterano_com_historia_escolhe_entre_formador_e_historia():
    liga = _liga()
    prest = vontade.prestigio(liga.clubes)
    escolhas = set()
    for i in range(40):
        veterano = Jogador(f"Veterano {i}", 33, "Defesa", 75)
        veterano.formador = "Bahia"
        veterano.clube_historia = "Milan"
        escolhas.add(vontade.sonho(veterano, liga.clubes, prest))
    assert escolhas == {"Bahia", "Milan"}


def test_idolo_ganha_a_historia_e_leva_ela_ao_sair():
    liga = _liga()
    milan, city = _clube_de(liga, "Milan"), _clube_de(liga, "City")
    idolo = Jogador("Ídolo", 29, "Atacante", 82, fama=80, temporadas_no_clube=5)
    milan.contratar_jogador(idolo)
    comum = milan.jogadores[0]

    vontade.marcar_historia(liga)
    assert idolo.clube_historia == "Milan"
    assert comum.clube_historia is None

    mercado.transferir(idolo, milan, city, 1_000_000)
    vontade.marcar_historia(liga)
    assert idolo.clube_historia == "Milan"   # no City ainda não fez história


def test_completar_nao_mexe_em_quem_ja_tem():
    liga = _liga()
    jogador = _clube_de(liga, "Inter").jogadores[0]
    jogador.formador, jogador.sonho = "Bahia", "Empoli"
    vontade.completar(liga)
    assert (jogador.formador, jogador.sonho) == ("Bahia", "Empoli")


def test_na_virada_o_sonho_muda_com_a_idade():
    liga = _liga()
    jogador = _clube_de(liga, "Inter").jogadores[0]
    vontade.completar(liga)
    jogador.formador = "Bahia"
    jogador.idade = vontade.IDADE_APOSENTADORIA
    vontade.virada(liga)
    assert jogador.sonho == "Bahia"


def test_seed_da_formador_e_sonho_a_todo_mundo():
    campeonato = carregar_campeonato(TODAS_AS_LIGAS)
    nomes = {c.nome for c in campeonato.clubes}
    todos = [j for c in campeonato.clubes for j in c.jogadores] + campeonato.livres
    assert all(j.formador in nomes and j.sonho in nomes for j in todos)
    # ninguém sonha com o mesmo clube que um quarto da liga
    maior = max(sum(j.sonho == n for j in todos) for n in nomes)
    assert maior < len(todos) / 4


def test_jovem_da_base_e_cria_da_casa():
    campeonato = carregar_campeonato()
    clube = campeonato.clubes[0]
    jovem = base.gerar_jovem(clube, set(), random.Random(1))
    assert jovem.formador == clube.nome


def test_snapshot_guarda_a_vontade():
    campeonato = carregar_campeonato()
    jogador = campeonato.clubes[0].jogadores[0]
    jogador.formador, jogador.clube_historia, jogador.sonho = "A", "B", "C"
    blob = snapshot_estado(campeonato)

    novo = carregar_campeonato()
    restaurar_estado(novo, blob)
    copia = next(j for c in novo.clubes for j in c.jogadores if j.nome == jogador.nome)
    assert (copia.formador, copia.clube_historia, copia.sonho) == ("A", "B", "C")


# --- interesse em vir (passo 2) ---------------------------------------------

def test_reserva_de_clube_pequeno_quer_vir_para_o_grande():
    liga = _liga()
    inter, empoli = _clube_de(liga, "Inter"), _clube_de(liga, "Empoli")
    reserva = Jogador("Reserva", 24, "Atacante", 64)   # pior que os titulares do Empoli
    empoli.contratar_jogador(reserva)
    reserva.overall = 90                               # mas seria titular na Inter
    i = vontade.interesse(reserva, inter, empoli, liga.clubes)
    assert i.nivel == vontade.QUER_VIR
    assert i.fator < 1
    assert "seria titular" in i.motivos


def test_titular_de_clube_grande_resiste_a_descer():
    liga = _liga()
    inter, empoli = _clube_de(liga, "Inter"), _clube_de(liga, "Empoli")
    craque = Jogador("Craque", 27, "Atacante", 88)
    inter.contratar_jogador(craque)
    i = vontade.interesse(craque, empoli, inter, liga.clubes)
    assert i.nivel == vontade.RESISTENTE
    assert i.fator > 1
    assert i.motivos[0] == "o clube atual tem mais prestígio"   # o motivo mais forte primeiro


def test_clube_do_sonho_pesa_e_quem_ja_esta_nele_nao_quer_sair():
    liga = _liga()
    milan, bahia = _clube_de(liga, "Milan"), _clube_de(liga, "Bahia")
    j = Jogador("Sonhador", 25, "Atacante", 80)
    bahia.contratar_jogador(j)
    j.sonho = "Milan"
    sonhando = vontade.interesse(j, milan, bahia, liga.clubes)
    j.sonho = "Bahia"
    em_casa = vontade.interesse(j, milan, bahia, liga.clubes)
    assert sonhando.pontos - em_casa.pontos == 4
    assert "é o clube do sonho" in sonhando.motivos


def test_o_fator_tem_limites():
    liga = _liga()
    inter, empoli = _clube_de(liga, "Inter"), _clube_de(liga, "Empoli")
    j = Jogador("Qualquer", 25, "Atacante", 80)
    empoli.contratar_jogador(j)
    for sonho in ("Inter", "Empoli"):
        j.sonho = sonho
        for comprador, vendedor in ((inter, empoli), (empoli, inter)):
            fator = vontade.interesse(j, comprador, vendedor, liga.clubes).fator
            assert vontade.FATOR_MIN <= fator <= vontade.FATOR_MAX


def test_idolo_nao_joga_no_rival_nem_anos_depois():
    liga = _liga()
    inter, milan, city = (_clube_de(liga, n) for n in ("Inter", "Milan", "City"))
    inter.rivais = {"Milan"}
    j = Jogador("Lenda", 33, "Atacante", 82)
    city.contratar_jogador(j)
    j.clube_historia = "Inter"   # fez história na Inter e hoje está no City
    i = vontade.interesse(j, milan, city, liga.clubes)
    assert i.nivel == vontade.NAO_VEM
    assert i.bloqueio == "Ídolo do Inter: não joga no rival"
    # para quem não é rival, tudo normal
    assert vontade.interesse(j, _clube_de(liga, "Bahia"), city, liga.clubes).bloqueio is None


def test_livre_quer_voltar_a_jogar():
    liga = _liga()
    livre = Jogador("Livre", 28, "Atacante", 70)
    i = vontade.interesse(livre, _clube_de(liga, "Bahia"), None, liga.clubes)
    assert "quer voltar a jogar" in i.motivos


# --- vontade no clube (passo 4) ---------------------------------------------

from app.domain import contrato, ofertas, papeis  # noqa: E402
from app.domain.carreira import resolver_contratos  # noqa: E402


class _Sorte(random.Random):
    """`random()` sempre devolve o mesmo valor (o resto é sorteio de verdade)."""

    def __init__(self, valor):
        super().__init__(1)
        self.valor = valor

    def random(self):
        return self.valor


def test_clube_do_sonho_faz_oferta_justa():
    liga = _liga()
    bahia, milan = _clube_de(liga, "Bahia"), _clube_de(liga, "Milan")
    sonhador = Jogador("Sonhador", 25, "Atacante", 90)   # seria titular no Milan
    bahia.contratar_jogador(sonhador)
    sonhador.sonho = "Milan"
    jogador, oferta = ofertas.do_sonho(bahia, liga.clubes, _Sorte(0.0))
    assert jogador is sonhador and oferta.clube is milan
    assert oferta.sonho and oferta.espontanea   # não estava à venda
    assert oferta.valor >= sonhador.valor_mercado() - 10_000


def test_sem_sorte_ou_sem_sonho_fora_nao_ha_oferta():
    liga = _liga()
    bahia = _clube_de(liga, "Bahia")
    j = Jogador("Caseiro", 25, "Atacante", 90)
    bahia.contratar_jogador(j)
    j.sonho = "Milan"
    assert ofertas.do_sonho(bahia, liga.clubes, _Sorte(0.99)) is None
    j.sonho = "Bahia"   # já está no clube do sonho
    assert ofertas.do_sonho(bahia, liga.clubes, _Sorte(0.0)) is None


def test_nao_vender_ao_clube_do_sonho_piora_o_humor():
    j = Jogador("Chateado", 25, "Atacante", 80)
    assert vontade.recusou_o_sonho(j) and j.humor == papeis.INCOMODADO
    assert vontade.recusou_o_sonho(j) and j.humor == papeis.QUER_SAIR
    assert j.a_venda   # quem quer sair vai para a lista
    assert not vontade.recusou_o_sonho(j)


def test_no_clube_do_sonho_ele_nao_chega_a_querer_sair():
    clube = Clube("A", "Brasil", 0)
    j = Jogador("Paciente", 20, "Atacante", 80)
    j.papel, j.jogos_disponivel, j.titularidades = papeis.TITULAR, 10, 2   # 20% < 50%
    j.sonho = "A"
    clube.jogadores = [j]
    for _ in range(3):
        papeis.checar(clube)
    assert j.humor == papeis.INCOMODADO and not j.a_venda


def test_vontade_pesa_na_renovacao():
    clube = _clube("Inter")
    j = Jogador("Renovando", 27, "Atacante", 75)
    clube.contratar_jogador(j)
    normal = contrato.salario_pedido(j, clube, "3x")

    j.humor = papeis.INCOMODADO
    assert contrato.salario_pedido(j, clube, "3x") > normal
    j.humor = papeis.CONTENTE

    j.sonho = "Inter"
    assert contrato.salario_pedido(j, clube, "3x") < normal

    j.idade, j.sonho = vontade.IDADE_APOSENTADORIA, "Bahia"
    veterano = contrato.salario_pedido(j, clube, "3x")
    j.sonho = "Inter"
    assert veterano > contrato.salario_pedido(j, clube, "3x")
    j.sonho = "Bahia"
    r = contrato.avaliar_renovacao(j, clube, 1_000, 1, "3x")
    assert "pensa em encerrar a carreira no Bahia" in r.motivo


def test_veterano_livre_volta_para_encerrar_no_formador():
    camp = carregar_campeonato()
    meu, casa = camp.clubes[0], camp.clubes[7]
    for c in camp.clubes:
        for j in c.jogadores:
            j.contrato_anos = 3
    veterano = next(j for j in meu.jogadores if j.posicao != "Goleiro")
    veterano.idade, veterano.contrato_anos = 33, 1
    veterano.formador = veterano.sonho = casa.nome
    while len(casa.jogadores) >= 25:
        casa.jogadores.pop()

    movs = resolver_contratos(camp, meu.nome)

    assert veterano in casa.jogadores
    assert veterano.contrato_anos <= contrato.duracao_max(veterano)
    detalhes = {m["detalhe"] for m in movs if m["jogador"] == veterano.nome}
    assert f"voltou para encerrar a carreira no {casa.nome}, que o formou" in detalhes
