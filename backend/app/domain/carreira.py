"""Modo carreira (v0.8): a virada de uma temporada para a próxima.

Uma carreira é uma sequência de simulações (uma por temporada). A temporada
nova nasce de um campeonato recém-carregado da seed, sobre o qual se aplica
o que a anterior deixou: quem joga onde (transferências), os contratos e o
caixa. Todo o resto (pontos, estatísticas, cartões, lesões, energia) começa
do zero, porque o `Campeonato` carregado já vem zerado.

O estado final vem das tabelas `clube`/`jogador` da temporada concluída, e
não do `estado_json` (que é apagado quando a temporada termina): o banco é a
fonte da verdade.
"""

from app.domain.evolucao import evoluir


def seed_da_temporada(seed_carreira, temporada):
    """Temporada N usa `seed + (N − 1)`: reproduzível, mas cada temporada
    tem jogos diferentes. Carreira aleatória (None) segue aleatória."""
    if seed_carreira is None:
        return None
    return seed_carreira + temporada - 1


def preparar_nova_temporada(campeonato, clubes_finais, jogadores_finais):
    """Aplica num campeonato recém-carregado o estado final da temporada
    anterior.

    `clubes_finais`: dicts com `nome` e `dinheiro` (caixa final).
    `jogadores_finais`: dicts com `nome`, `clube`, `idade`, `overall`,
    `potencial`, `salario`, `contrato_anos` e `multa_rescisoria`, na ordem
    do elenco.
    """

    # todos os jogadores da liga, por nome (os nomes são únicos na seed)
    por_nome = {j.nome: j for c in campeonato.clubes for j in c.jogadores}
    por_clube = {c.nome: c for c in campeonato.clubes}

    desconhecidos = [j["nome"] for j in jogadores_finais
                     if j["nome"] not in por_nome]
    if desconhecidos:
        # só acontece quando existirem jogadores fora da seed (base,
        # aposentadoria — passos 3 e 4); aí o snapshot vai precisar
        # carregar o jogador inteiro
        raise ValueError(f"Jogadores fora da seed: {desconhecidos}")

    # elencos: começa vazio e cada jogador vai para o clube onde terminou
    for clube in campeonato.clubes:
        clube.jogadores = []
        clube.titulares = []
        clube.reservas = []
        clube.xi_preferido = set()

    for final in jogadores_finais:
        jogador = por_nome[final["nome"]]
        jogador.idade = final["idade"]
        jogador.overall = final["overall"]
        jogador.potencial = final["potencial"]
        jogador.salario = final["salario"]
        jogador.contrato_anos = final["contrato_anos"]
        jogador.multa_rescisoria = final["multa_rescisoria"]
        por_clube[final["clube"]].jogadores.append(jogador)

    # caixa: o final da temporada anterior é o inicial desta
    for final in clubes_finais:
        clube = por_clube[final["nome"]]
        clube.dinheiro = final["dinheiro"]
        clube.dinheiro_inicial = final["dinheiro"]

    return campeonato


def envelhecer(campeonato, jogadores_finais, rng):
    """Todo mundo fica 1 ano mais velho e evolui (ou cai) conforme a idade e
    as partidas jogadas na temporada que acabou (ver `app.domain.evolucao`).
    Chamar depois de `preparar_nova_temporada`."""

    partidas = {j["nome"]: j["partidas"] for j in jogadores_finais}

    for clube in campeonato.clubes:
        for jogador in clube.jogadores:
            jogador.idade, jogador.overall, jogador.potencial = evoluir(
                jogador.idade, jogador.overall, jogador.potencial,
                partidas.get(jogador.nome, 0), rng,
            )

    return campeonato
