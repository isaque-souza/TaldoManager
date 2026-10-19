import random

from app.domain.temporada import restaurar_estado, snapshot_estado
from scripts.data_loader import carregar_campeonato


def _campeonato_apos(n_rodadas, seed=7):
    random.seed(seed)
    camp = carregar_campeonato()
    for _ in range(n_rodadas):
        camp.jogar_rodada()
    return camp


def test_snapshot_e_json_serializavel():
    import json

    camp = _campeonato_apos(3)
    blob = snapshot_estado(camp)
    # não levanta
    json.dumps(blob)
    assert blob["rodada"] == 4
    assert len(blob["clubes"]) == 20


def test_restaurar_reconstroi_stats_de_clube_e_jogador():
    camp = _campeonato_apos(5)
    blob = snapshot_estado(camp)

    alvo = camp.clubes[0]
    pontos, gp, energia = (
        alvo.pontos,
        alvo.gols_marcados,
        camp.clubes[0].jogadores[0].energia,
    )

    novo = carregar_campeonato()
    restaurar_estado(novo, blob)

    igual = next(c for c in novo.clubes if c.nome == alvo.nome)
    assert igual.pontos == pontos
    assert igual.gols_marcados == gp
    assert igual.forma == alvo.forma
    assert novo.rodada == 6
    assert igual.jogadores[0].energia == energia


def test_ciclo_snapshot_restaura_continua_a_corrente_do_rng():
    # rodar 10 rodadas direto
    referencia = _campeonato_apos(10, seed=123)
    tabela_ref = [
        (c.nome, c.pontos, c.gols_marcados) for c in referencia.classificacao()
    ]

    # rodar 4, snapshot, restaurar num campeonato novo, rodar +6
    random.seed(123)
    parcial = carregar_campeonato()
    for _ in range(4):
        parcial.jogar_rodada()
    blob = snapshot_estado(parcial)

    retomado = carregar_campeonato()
    restaurar_estado(retomado, blob)
    for _ in range(6):
        retomado.jogar_rodada()

    tabela_ret = [
        (c.nome, c.pontos, c.gols_marcados) for c in retomado.classificacao()
    ]
    assert tabela_ret == tabela_ref


def test_snapshot_recria_jogador_fora_da_seed():
    from app.domain.jogador import Jogador
    from app.domain.temporada import restaurar_estado, snapshot_estado
    from scripts.data_loader import carregar_campeonato

    camp = carregar_campeonato()
    jovem = Jogador("Jovem da Base", 17, "Goleiro", 61, potencial=83)
    jovem.gols = 2
    camp.clubes[3].jogadores.append(jovem)
    blob = snapshot_estado(camp)

    novo = carregar_campeonato()
    restaurar_estado(novo, blob)

    j = next(j for j in novo.clubes[3].jogadores if j.nome == "Jovem da Base")
    assert (j.posicao, j.idade, j.overall, j.potencial, j.gols) == (
        "Goleiro", 17, 61, 83, 2
    )


def test_snapshot_guarda_os_livres():
    camp = carregar_campeonato()
    contratado = camp.livres.pop(0)
    camp.clubes[0].jogadores.append(contratado)
    camp.livres[0].overall = 99
    blob = snapshot_estado(camp)

    novo = carregar_campeonato()
    restaurar_estado(novo, blob)

    nomes = [j.nome for j in novo.livres]
    assert contratado.nome not in nomes and len(nomes) == 49
    assert novo.livres[0].overall == 99
    assert contratado.nome in {j.nome for j in novo.clubes[0].jogadores}


def test_snapshot_antigo_sem_livres_fica_com_os_da_seed():
    camp = carregar_campeonato()
    blob = snapshot_estado(camp)
    del blob["livres"]
    # um jovem da base com o nome de um livre: não pode estar nos dois
    blob["clubes"][camp.clubes[0].nome]["elenco"].append(camp.livres[0].nome)
    blob["clubes"][camp.clubes[0].nome]["jogadores"][camp.livres[0].nome] = (
        blob["clubes"][camp.clubes[0].nome]["jogadores"][camp.clubes[0].jogadores[0].nome]
    )

    novo = carregar_campeonato()
    restaurar_estado(novo, blob)

    assert len(novo.livres) == 49
    assert camp.livres[0].nome not in {j.nome for j in novo.livres}
