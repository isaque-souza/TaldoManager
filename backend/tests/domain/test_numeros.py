from app.domain import mercado, numeros
from app.domain.clube import Clube
from app.domain.jogador import Jogador
from app.domain.temporada import restaurar_estado, snapshot_estado
from scripts.data_loader import carregar_campeonato


def _clube(nome="A", dinheiro=500_000_000):
    return Clube(nome, "Brasil", dinheiro, 1_000_000)


def _jogador(nome, posicao, overall=75):
    return Jogador(nome, 25, posicao, overall)


def test_quem_chega_primeiro_pega_o_numero_classico_da_posicao():
    clube = _clube()
    for nome, pos in [("G", "Goleiro"), ("Z", "Defesa"), ("M", "Meio-Campo"), ("C", "Atacante")]:
        clube.contratar_jogador(_jogador(nome, pos))
    assert {j.nome: j.numero for j in clube.jogadores} == {"G": 1, "Z": 2, "M": 8, "C": 9}


def test_segundo_da_posicao_pega_o_proximo_da_lista():
    clube = _clube()
    clube.contratar_jogador(_jogador("G1", "Goleiro"))
    clube.contratar_jogador(_jogador("G2", "Goleiro"))
    assert [j.numero for j in clube.jogadores] == [1, 12]


def test_numeros_da_seed_sao_unicos_em_cada_clube():
    for clube in carregar_campeonato().clubes:
        nums = [j.numero for j in clube.jogadores]
        assert None not in nums
        assert len(set(nums)) == len(nums), clube.nome


def test_goleiro_titular_da_seed_e_o_1():
    for clube in carregar_campeonato().clubes:
        goleiros = [j for j in clube.jogadores if j.posicao == "Goleiro"]
        assert 1 in {j.numero for j in goleiros}, clube.nome


def test_transferido_mantem_o_numero_se_estiver_livre():
    vendedor, comprador = _clube("V"), _clube("C")
    for i in range(18):
        vendedor.contratar_jogador(_jogador(f"v{i}", "Defesa"))
    comprador.contratar_jogador(_jogador("g", "Goleiro"))
    craque = vendedor.jogadores[5]
    numero = craque.numero

    mercado.transferir(craque, vendedor, comprador, 1_000_000)
    assert craque.numero == numero


def test_transferido_troca_de_numero_se_o_dele_estiver_ocupado():
    vendedor, comprador = _clube("V"), _clube("C")
    for i in range(18):
        vendedor.contratar_jogador(_jogador(f"v{i}", "Atacante"))
    comprador.contratar_jogador(_jogador("dono-do-9", "Atacante"))   # pega o 9
    nove = next(j for j in vendedor.jogadores if j.numero == 9)

    mercado.transferir(nove, vendedor, comprador, 1_000_000)
    assert nove.numero == 11   # o 9 tem dono; o próximo atacante livre
    assert comprador.jogadores[0].numero == 9


def test_revisar_corrige_numero_repetido_mantendo_quem_veio_antes():
    clube = _clube()
    a, b = _jogador("a", "Atacante"), _jogador("b", "Atacante")
    a.numero = b.numero = 9
    clube.jogadores = [a, b]

    numeros.revisar(clube)
    assert (a.numero, b.numero) == (9, 11)


def test_numero_sobrevive_ao_snapshot():
    camp = carregar_campeonato()
    jogador = camp.clubes[0].jogadores[0]
    jogador.numero = 77
    blob = snapshot_estado(camp)

    novo = carregar_campeonato()
    restaurar_estado(novo, blob)
    assert novo.clubes[0].jogadores[0].numero == 77


def test_snapshot_antigo_sem_numero_nao_deixa_repetido():
    camp = carregar_campeonato()
    blob = snapshot_estado(camp)
    origem, destino = blob["clubes"][camp.clubes[0].nome], blob["clubes"][camp.clubes[1].nome]
    # um transferido num save de antes da v1.1: muda de elenco sem número
    nome = origem["elenco"].pop()
    destino["elenco"].append(nome)
    destino["jogadores"][nome] = origem["jogadores"].pop(nome)
    for dados in blob["clubes"].values():
        for campos in dados["jogadores"].values():
            campos.pop("numero")

    novo = carregar_campeonato()
    restaurar_estado(novo, blob)
    for clube in novo.clubes:
        nums = [j.numero for j in clube.jogadores]
        assert len(set(nums)) == len(nums), clube.nome
