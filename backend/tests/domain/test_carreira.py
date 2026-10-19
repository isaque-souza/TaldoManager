import pytest

from app.domain.carreira import preparar_nova_temporada, seed_da_temporada
from scripts.data_loader import carregar_campeonato


def test_seed_da_temporada_soma_o_numero_da_temporada():
    assert seed_da_temporada(10, 1) == 10
    assert seed_da_temporada(10, 2) == 11
    assert seed_da_temporada(10, 5) == 14


def test_seed_da_temporada_aleatoria_continua_aleatoria():
    assert seed_da_temporada(None, 3) is None


def _finais(campeonato):
    """O "estado final" no formato das tabelas, sem mudança nenhuma."""
    clubes = [{"nome": c.nome, "dinheiro": c.dinheiro} for c in campeonato.clubes]
    jogadores = [
        {
            "nome": j.nome,
            "clube": c.nome,
            "idade": j.idade,
            "overall": j.overall,
            "potencial": j.potencial,
            "partidas": 0,
            "salario": j.salario,
            "contrato_anos": j.contrato_anos,
            "multa_rescisoria": j.multa_rescisoria,
        }
        for c in campeonato.clubes for j in c.jogadores
    ]
    return clubes, jogadores


def test_jogador_transferido_comeca_no_clube_novo():
    base = carregar_campeonato()
    clubes, jogadores = _finais(base)
    a, b = base.clubes[0].nome, base.clubes[1].nome
    vendido = next(j for j in jogadores if j["clube"] == a)
    vendido["clube"] = b

    novo = preparar_nova_temporada(carregar_campeonato(), clubes, jogadores)
    elencos = {c.nome: {j.nome for j in c.jogadores} for c in novo.clubes}

    assert vendido["nome"] not in elencos[a]
    assert vendido["nome"] in elencos[b]
    # ninguém some nem duplica
    total = sum(len(e) for e in elencos.values())
    assert total == len(jogadores)


def test_contrato_e_caixa_sao_herdados():
    base = carregar_campeonato()
    clubes, jogadores = _finais(base)
    clubes[0]["dinheiro"] = -1_234_000      # terminou endividado
    jogadores[0].update(salario=9_999_000, contrato_anos=5,
                        multa_rescisoria=77_000_000)

    novo = preparar_nova_temporada(carregar_campeonato(), clubes, jogadores)
    clube = next(c for c in novo.clubes if c.nome == clubes[0]["nome"])
    jogador = next(j for c in novo.clubes for j in c.jogadores
                   if j.nome == jogadores[0]["nome"])

    assert clube.dinheiro == clube.dinheiro_inicial == -1_234_000
    assert (jogador.salario, jogador.contrato_anos,
            jogador.multa_rescisoria) == (9_999_000, 5, 77_000_000)


def test_jogador_fora_da_seed_e_criado():
    base = carregar_campeonato()
    clubes, jogadores = _finais(base)
    jovem = {**jogadores[0], "nome": "Jovem da Base", "posicao": "Goleiro",
             "idade": 17, "overall": 60, "potencial": 80,
             "salario": 50_000, "contrato_anos": 3, "multa_rescisoria": None}
    jogadores.append(jovem)

    novo = preparar_nova_temporada(carregar_campeonato(), clubes, jogadores)
    j = next(j for c in novo.clubes for j in c.jogadores if j.nome == "Jovem da Base")

    assert (j.posicao, j.idade, j.overall, j.potencial) == ("Goleiro", 17, 60, 80)
    assert (j.salario, j.contrato_anos) == (50_000, 3)


def test_envelhecer_aplica_a_evolucao_em_todos():
    import random

    from app.domain.carreira import envelhecer

    base = carregar_campeonato()
    clubes, jogadores = _finais(base)
    novo = preparar_nova_temporada(carregar_campeonato(), clubes, jogadores)
    envelhecer(novo, jogadores, random.Random(1))

    antes = {j["nome"]: j for j in jogadores}
    for c in novo.clubes:
        for j in c.jogadores:
            a = antes[j.nome]
            assert j.idade == a["idade"] + 1
            assert j.potencial >= j.overall
            if a["idade"] >= 30:
                assert j.overall <= a["overall"]
            else:
                assert j.overall >= a["overall"]


# --- aposentadoria e contratos (passo 3) ---

from app.domain import mercado  # noqa: E402
from app.domain.carreira import (  # noqa: E402
    aposentar,
    chance_aposentadoria,
    resolver_contratos,
)


class Sorte:
    """rng de teste: `random()` sempre devolve o mesmo valor."""

    def __init__(self, valor):
        self.valor = valor

    def random(self):
        return self.valor


SEMPRE = Sorte(0.0)     # toda chance acontece
NUNCA = Sorte(0.999)    # nenhuma chance acontece


def test_chance_de_aposentadoria_por_idade():
    assert chance_aposentadoria(33, False) == 0.0
    assert chance_aposentadoria(34, False) == 0.15
    assert chance_aposentadoria(37, False) == 0.60
    assert chance_aposentadoria(40, False) == 0.85
    # sem contrato, pendura as chuteiras mais fácil
    assert chance_aposentadoria(35, True) == pytest.approx(0.45)
    assert chance_aposentadoria(40, True) == 1.0
    assert chance_aposentadoria(20, True) == 0.0


def _clube_com_veterano(campeonato, idade=36):
    clube = campeonato.clubes[0]
    veterano = next(j for j in clube.jogadores if j.posicao != "Goleiro")
    veterano.idade = idade
    for j in clube.jogadores:
        if j is not veterano:
            j.idade = 25
    return clube, veterano


def test_veterano_se_aposenta_e_sai_do_elenco():
    camp = carregar_campeonato()
    for c in camp.clubes[1:]:
        for j in c.jogadores:
            j.idade = 25
    clube, veterano = _clube_com_veterano(camp)

    movs = aposentar(camp, SEMPRE)

    assert veterano not in clube.jogadores
    assert [(m["tipo"], m["jogador"]) for m in movs] == [("aposentou", veterano.nome)]
    assert movs[0]["idade"] == 36 and movs[0]["overall"] == veterano.overall


def test_sem_sorte_ninguem_se_aposenta():
    camp = carregar_campeonato()
    _clube_com_veterano(camp)
    aposentar(camp, NUNCA)
    assert all(len(c.jogadores) == 23 for c in camp.clubes)


def test_elenco_minimo_faz_o_veterano_adiar():
    camp = carregar_campeonato()
    clube, veterano = _clube_com_veterano(camp)
    while len(clube.jogadores) > mercado.ELENCO_MIN:
        clube.jogadores.remove(next(j for j in clube.jogadores
                                    if j is not veterano and j.posicao != "Goleiro"))

    movs = [m for m in aposentar(camp, SEMPRE) if m["clube"] == clube.nome]

    assert veterano in clube.jogadores
    assert [m["tipo"] for m in movs] == ["adiou"]


def _todos(camp, anos):
    for c in camp.clubes:
        for j in c.jogadores:
            j.contrato_anos = anos


def test_contratos_descontam_uma_temporada():
    camp = carregar_campeonato()
    _todos(camp, 3)
    assert resolver_contratos(camp, camp.clubes[0].nome) == []
    assert all(j.contrato_anos == 2 for c in camp.clubes for j in c.jogadores)


def test_cpu_renova_sozinha():
    camp = carregar_campeonato()
    _todos(camp, 3)
    cpu = camp.clubes[1]
    jovem, veterano = cpu.jogadores[0], cpu.jogadores[1]
    jovem.idade, veterano.idade = 22, 33
    jovem.contrato_anos = veterano.contrato_anos = 1
    jovem.salario = 1_000

    movs = resolver_contratos(camp, camp.clubes[0].nome)

    assert {m["jogador"]: m["tipo"] for m in movs} == {
        jovem.nome: "renovou", veterano.nome: "renovou",
    }
    assert jovem in cpu.jogadores and veterano in cpu.jogadores
    assert (jovem.contrato_anos, veterano.contrato_anos) == (3, 2)
    assert jovem.salario == jovem.salario_referencia()


def test_jogador_do_tecnico_nao_renovado_sai_de_graca():
    camp = carregar_campeonato()
    _todos(camp, 3)
    meu = camp.clubes[0]
    craque = max(meu.jogadores, key=lambda j: j.overall)
    craque.contrato_anos = 1

    movs = resolver_contratos(camp, meu.nome)

    assert craque not in meu.jogadores
    destino = next(c for c in camp.clubes if craque in c.jogadores)
    assert destino is not meu
    assert [m["tipo"] for m in movs] == ["saiu_livre", "chegou_livre"]
    assert movs[0]["detalhe"] == f"assinou com {destino.nome}"
    # contrato novo no destino, sem ser descontado de novo
    assert (craque.contrato_anos, craque.multa_rescisoria) == (3, None)


def test_destino_e_o_clube_mais_rico_onde_seria_titular():
    camp = carregar_campeonato()
    _todos(camp, 3)
    meu = camp.clubes[0]
    craque = max(meu.jogadores, key=lambda j: j.overall)
    craque.contrato_anos = 1
    rico = camp.clubes[5]
    rico.dinheiro = 10**12

    resolver_contratos(camp, meu.nome)
    assert craque in rico.jogadores


def test_sem_destino_o_jogador_deixa_a_liga():
    camp = carregar_campeonato()
    _todos(camp, 3)
    meu = camp.clubes[0]
    # de linha: um goleiro cairia na trava dos 2 goleiros (emergência)
    fraco = min((j for j in meu.jogadores if j.posicao != "Goleiro"),
                key=lambda j: j.overall)
    fraco.overall = 1      # não seria titular em lugar nenhum
    fraco.contrato_anos = 1

    movs = resolver_contratos(camp, meu.nome)

    assert all(fraco not in c.jogadores for c in camp.clubes)
    assert [(m["tipo"], m["detalhe"]) for m in movs] == [("saiu_livre", "deixou a liga")]


def test_elenco_minimo_gera_contrato_de_emergencia():
    camp = carregar_campeonato()
    _todos(camp, 3)
    meu = camp.clubes[0]
    while len(meu.jogadores) > mercado.ELENCO_MIN:
        meu.jogadores.pop()
    saindo = next(j for j in meu.jogadores if j.posicao != "Goleiro")
    saindo.contrato_anos = 1

    movs = resolver_contratos(camp, meu.nome)

    assert saindo in meu.jogadores
    assert saindo.contrato_anos == 1
    assert movs[0]["tipo"] == "renovou" and "emergência" in movs[0]["detalhe"]


def test_cpu_dispensa_veterano_reserva_com_elenco_cheio():
    camp = carregar_campeonato()
    _todos(camp, 3)
    cpu = camp.clubes[1]
    reserva = min((j for j in cpu.jogadores if j.posicao == "Atacante"),
                  key=lambda j: j.overall)
    reserva.idade, reserva.contrato_anos = 31, 1
    cpu.jogadores.append(camp.clubes[2].jogadores.pop())   # 19 > 18

    movs = resolver_contratos(camp, camp.clubes[0].nome)

    assert reserva not in cpu.jogadores
    assert movs[0]["tipo"] == "saiu_livre" and movs[0]["clube"] == cpu.nome


def test_cpu_renova_veterano_reserva_se_o_elenco_nao_esta_cheio():
    camp = carregar_campeonato()
    _todos(camp, 3)
    cpu = camp.clubes[1]
    reserva = min((j for j in cpu.jogadores if j.posicao == "Atacante"),
                  key=lambda j: j.overall)
    reserva.idade, reserva.contrato_anos = 31, 1      # elenco = 18

    movs = resolver_contratos(camp, camp.clubes[0].nome)
    assert reserva in cpu.jogadores and movs[0]["tipo"] == "renovou"
