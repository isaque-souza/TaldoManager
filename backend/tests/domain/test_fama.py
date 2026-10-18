"""Fama dos jogadores e ídolos (v1.4)."""

import io
import random
from contextlib import redirect_stdout

import pytest

from app.domain import caixa, fama, mercado, torcida
from app.domain.clube import Clube
from app.domain.jogador import Jogador
from app.domain.temporada import restaurar_estado, snapshot_estado
from scripts.data_loader import carregar_campeonato


def _clube(nome="Teste FC", torcedores=1_000_000):
    return Clube(nome, "Brasil", 10_000_000, torcedores)


def _idolo(nome="Ídolo", overall=85):
    return Jogador(nome, 29, "Atacante", overall, fama=80, temporadas_no_clube=5)


def test_fama_inicial_vem_do_overall_e_da_idade():
    craque, _ = fama.inicial("Fulano", 30, 92)
    jovem, temporadas = fama.inicial("Fulano", 19, 72)
    assert craque > jovem
    assert 0 <= jovem <= craque <= fama.FAMA_MAX
    assert temporadas == 0   # aos 19 ainda não deu tempo de fazer história


def test_fama_inicial_e_a_mesma_em_toda_execucao():
    assert fama.inicial("Bruno Rodriguez", 29, 94) == fama.inicial("Bruno Rodriguez", 29, 94)


def test_idolo_precisa_de_fama_e_de_tempo_de_casa():
    assert fama.eh_idolo(fama.LIMIAR_IDOLO, fama.TEMPORADAS_IDOLO)
    assert not fama.eh_idolo(fama.LIMIAR_IDOLO - 1, 10)
    assert not fama.eh_idolo(100, fama.TEMPORADAS_IDOLO - 1)


def test_temporada_boa_da_fama_e_quem_some_e_esquecido():
    artilheiro = Jogador("Artilheiro", 26, "Atacante", 85, fama=40)
    sumido = Jogador("Sumido", 26, "Atacante", 85, fama=40)
    artilheiro.gols, artilheiro.partidas, artilheiro.melhor_em_campo = 25, 38, 8
    clube = _clube()
    for j in (artilheiro, sumido):
        clube.contratar_jogador(j)

    fama.fim_de_temporada([_clube("Campeão"), clube])

    assert artilheiro.fama > 40 > sumido.fama
    assert sumido.fama == round(40 * fama.RETENCAO)
    assert artilheiro.temporadas_no_clube == sumido.temporadas_no_clube == 1


def test_titulo_da_fama_a_quem_jogou():
    titular = Jogador("Titular", 26, "Defesa", 80)
    reserva = Jogador("Reserva", 26, "Defesa", 70)
    titular.partidas, reserva.partidas = 30, 3
    assert fama.pontos_da_temporada(titular, campeao=True) == pytest.approx(
        fama.pontos_da_temporada(titular) + fama.CAMPEAO
    )
    assert fama.pontos_da_temporada(reserva, campeao=True) == fama.pontos_da_temporada(reserva)


def test_clean_sheet_so_conta_para_goleiro():
    goleiro = Jogador("Goleiro", 26, "Goleiro", 80)
    zagueiro = Jogador("Zagueiro", 26, "Defesa", 80)
    goleiro.clean_sheets = zagueiro.clean_sheets = 10
    assert fama.pontos_da_temporada(goleiro) == pytest.approx(10 * fama.POR_CLEAN_SHEET)
    assert fama.pontos_da_temporada(zagueiro) == 0


def test_fama_nunca_passa_de_100():
    j = Jogador("Lenda", 26, "Atacante", 95, fama=99)
    j.gols, j.partidas, j.melhor_em_campo = 40, 38, 20
    clube = _clube()
    clube.contratar_jogador(j)
    fama.fim_de_temporada([clube])
    assert j.fama == fama.FAMA_MAX


def test_famoso_vale_mais():
    anonimo = Jogador("Anônimo", 26, "Atacante", 85)
    famoso = Jogador("Famoso", 26, "Atacante", 85, fama=100)
    assert famoso.valor_mercado() == pytest.approx(
        anonimo.valor_mercado() * fama.fator_valor(100), rel=0.01
    )


def test_idolo_custa_mais_para_sair():
    vendedor, comprador = _clube("Casa"), _clube("Fora")
    idolo = _idolo()
    comum = Jogador("Comum", 29, "Atacante", 85, fama=80)
    for j in (idolo, comum):
        vendedor.contratar_jogador(j)
    assert mercado.preco_pedido(idolo, vendedor, comprador) > mercado.preco_pedido(
        comum, vendedor, comprador
    )


def test_transferencia_leva_a_fama_mas_zera_o_tempo_de_casa():
    vendedor, comprador = _clube("Casa"), _clube("Fora")
    for i in range(mercado.ELENCO_MIN):
        vendedor.contratar_jogador(Jogador(f"J{i}", 25, "Defesa", 70))
    idolo = _idolo()
    vendedor.contratar_jogador(idolo)

    mercado.transferir(idolo, vendedor, comprador, 1_000_000)

    assert idolo.fama == 80
    assert idolo.temporadas_no_clube == 0
    assert not fama.idolo(idolo)


def test_vender_idolo_revolta_a_torcida_e_soma_com_a_do_rival():
    casa, rival, neutro = _clube("Casa"), _clube("Rival"), _clube("Neutro")
    casa.rivais = {"Rival"}
    idolo = _idolo(overall=90)
    casa.contratar_jogador(idolo)
    casa.contratar_jogador(Jogador("Comum", 25, "Atacante", 70))

    assert torcida.revolta_da_venda(casa, neutro, idolo) == torcida.VENDA_IDOLO
    assert torcida.revolta_da_venda(casa, rival, idolo) == pytest.approx(
        torcida.VENDA_IDOLO + torcida.VENDA_RIVAL_CRAQUE
    )

    antes, depois = torcida.reagir_a_venda(casa, neutro, idolo)
    assert depois == round(antes * (1 + torcida.VENDA_IDOLO))
    assert neutro.torcedores == 1_000_000   # só o rival comemora


def test_idolos_atraem_torcida_no_fim_da_temporada():
    sem, com = _clube("Sem"), _clube("Com")
    for i in range(fama.MAX_IDOLOS_TORCIDA + 2):   # o bônus tem teto
        com.contratar_jogador(_idolo(f"Ídolo {i}"))
    assert fama.bonus_torcida(com) == pytest.approx(
        fama.TORCIDA_POR_IDOLO * fama.MAX_IDOLOS_TORCIDA
    )
    # 5º e 6º: a mesma faixa da tabela, só os ídolos fazem a diferença
    torcida.fim_de_temporada([_clube(f"G{i}") for i in range(4)] + [sem, com])
    assert com.torcedores > sem.torcedores


def test_mensagens_de_idolo():
    novo = caixa.novos_idolos(["Fulano"], "Casa")
    assert novo["setor"] == "Marketing" and "Fulano virou ídolo" in novo["corpo"]
    assert "Fulano e Beltrano viraram ídolos" in caixa.novos_idolos(
        ["Fulano", "Beltrano"], "Casa"
    )["corpo"]
    assert caixa.novos_idolos([], "Casa") is None

    luto = caixa.revolta_da_torcida(
        _idolo("Fulano"), _clube("Fora"), 1_000_000, 970_000, rival=False, idolo=True,
    )
    assert "ídolo da casa" in luto["corpo"] and "em festa" not in luto["corpo"]


def test_virada_homenageia_o_idolo_que_se_aposenta():
    movimentos = [
        {"tipo": "aposentou", "jogador": "Velho Ídolo", "clube": "Casa",
         "posicao": "Atacante", "idade": 37, "overall": 80, "detalhe": ""},
        {"tipo": "aposentou", "jogador": "Velho Comum", "clube": "Casa",
         "posicao": "Defesa", "idade": 37, "overall": 75, "detalhe": ""},
    ]
    msgs = caixa.virada("Casa", movimentos, [], idolos={"Velho Ídolo"})
    adeus = [m for m in msgs if m["assunto"].startswith("Adeus")]
    assert [m["assunto"] for m in adeus] == ["Adeus, Velho Ídolo"]


def test_seed_tem_idolos_nos_clubes_grandes():
    camp = carregar_campeonato()
    assert any(fama.idolos(c) for c in camp.clubes)


def test_fama_vai_no_snapshot():
    camp = carregar_campeonato()
    j = camp.clubes[0].jogadores[0]
    j.fama, j.temporadas_no_clube = 77, 6
    blob = snapshot_estado(camp)

    estado = random.getstate()
    try:
        outro = carregar_campeonato()
        restaurar_estado(outro, blob)
    finally:
        random.setstate(estado)
    mesmo = next(x for x in outro.clubes[0].jogadores if x.nome == j.nome)
    assert (mesmo.fama, mesmo.temporadas_no_clube) == (77, 6)


def test_fama_nao_consome_rng():
    """Fama e ídolos são determinísticos: a temporada inteira com a fama
    ligada e com ela "desligada" tem os mesmos placares."""

    def placares(desligar):
        random.seed(5)
        camp = carregar_campeonato()
        if desligar:
            for c in camp.clubes:
                for j in c.jogadores:
                    j.fama = j.temporadas_no_clube = 0
        with redirect_stdout(io.StringIO()):
            while camp.rodada <= len(camp.calendario):
                camp.jogar_rodada()
        return camp.historico

    assert placares(False) == placares(True)
