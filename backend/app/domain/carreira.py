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

from app.domain import contrato, livres, mercado, numeros
from app.domain.base import TAMANHO_ALVO
from app.domain.evolucao import evoluir
from app.domain.temporada import criar_jogador


def seed_da_temporada(seed_carreira, temporada):
    """Temporada N usa `seed + (N − 1)`: reproduzível, mas cada temporada
    tem jogos diferentes. Carreira aleatória (None) segue aleatória."""
    if seed_carreira is None:
        return None
    return seed_carreira + temporada - 1


def preparar_nova_temporada(campeonato, clubes_finais, jogadores_finais,
                            livres_finais=None):
    """Aplica num campeonato recém-carregado o estado final da temporada
    anterior.

    `clubes_finais`: dicts com `nome`, `dinheiro` (caixa final),
    `torcedores` (torcida final), `torcedores_base` (tamanho natural),
    `capacidade`, `ingresso`, `obra_lugares`, `obra_rodadas` e
    `lugares_ampliados` (estádio).
    `jogadores_finais`: dicts com `nome`, `clube`, `idade`, `overall`,
    `potencial`, `salario`, `contrato_anos`, `multa_rescisoria`, `fama` e
    `temporadas_no_clube`, na ordem do elenco.
    `livres_finais`: os livres no fim dela (`temporada.restaurar_livres`);
    None (temporada de antes da v1.6) fica com os da seed.
    """

    # todos os jogadores da liga, por nome (os nomes são únicos na seed)
    por_nome = {j.nome: j for c in campeonato.clubes for j in c.jogadores}
    por_clube = {c.nome: c for c in campeonato.clubes}

    # quem não está na seed (jovens da base) é recriado a partir da tabela
    for final in jogadores_finais:
        if final["nome"] not in por_nome:
            por_nome[final["nome"]] = criar_jogador(final["nome"], final)

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
        jogador.numero = final.get("numero")
        jogador.a_venda = bool(final.get("a_venda"))   # v1.7
        # fama (v1.4); temporadas anteriores não guardam (None) e ficam com
        # a da seed
        if final.get("fama") is not None:
            jogador.fama = final["fama"]
            jogador.temporadas_no_clube = final["temporadas_no_clube"]
        por_clube[final["clube"]].jogadores.append(jogador)

    # temporadas de antes da v1.1 não guardam número
    for clube in campeonato.clubes:
        numeros.revisar(clube)

    # caixa: o final da temporada anterior é o inicial desta
    for final in clubes_finais:
        clube = por_clube[final["nome"]]
        clube.dinheiro = final["dinheiro"]
        clube.dinheiro_inicial = final["dinheiro"]
        # a torcida também (v1.4); temporadas anteriores não guardam (0) e
        # ficam com a da seed
        if final.get("torcedores"):
            clube.torcedores = final["torcedores"]
        clube.torcedores_inicial = clube.torcedores
        # o tamanho natural também (temporadas anteriores: 0, fica o da seed)
        if final.get("torcedores_base"):
            clube.torcedores_base = final["torcedores_base"]
        # o estádio também (v1.5); antes dele (0), fica o da seed
        if final.get("capacidade"):
            clube.capacidade = final["capacidade"]
            clube.ingresso = final.get("ingresso") or "normal"
            # a obra em andamento segue de onde parou
            clube.obra_lugares = final.get("obra_lugares") or 0
            clube.obra_rodadas = final.get("obra_rodadas") or 0
            clube.lugares_ampliados = final.get("lugares_ampliados") or 0

    # livres (v1.6): os do fim da temporada anterior; sem registro, os da
    # seed — nos dois casos, menos quem já está num clube
    if livres_finais is not None:
        campeonato.livres = list(livres_finais)
    na_liga = {j.nome for c in campeonato.clubes for j in c.jogadores}
    campeonato.livres = [j for j in campeonato.livres if j.nome not in na_liga]

    return campeonato


def envelhecer(campeonato, jogadores_finais, rng):
    """Todo mundo fica 1 ano mais velho e evolui (ou cai) conforme a idade e
    as partidas jogadas na temporada que acabou (ver `app.domain.evolucao`).
    Chamar depois de `preparar_nova_temporada`."""

    partidas = {j["nome"]: j["partidas"] for j in jogadores_finais}

    # os livres também (v1.6): sem jogar, quem não é jovem cai
    todos = [j for c in campeonato.clubes for j in c.jogadores] + campeonato.livres
    for jogador in todos:
        jogador.idade, jogador.overall, jogador.potencial = evoluir(
            jogador.idade, jogador.overall, jogador.potencial,
            partidas.get(jogador.nome, 0), rng,
        )

    return campeonato


# ---------------------------------------------------------------------------
# aposentadoria e contratos vencidos (passo 3)
# ---------------------------------------------------------------------------

# chance de se aposentar pela idade NOVA (depois de envelhecer)
CHANCE_APOSENTADORIA = {34: 0.15, 35: 0.25, 36: 0.40, 37: 0.60}
CHANCE_APOSENTADORIA_MAX = 0.85          # 38+
BONUS_CONTRATO_VENCENDO = 0.20           # sem contrato, pendura as chuteiras
ANOS_RENOVACAO_CPU = 3
ANOS_RENOVACAO_CPU_VETERANO = 2          # 32+ (como na renovação do técnico)
ANOS_EMERGENCIA = 1
IDADE_DISPENSA_CPU = 30                  # veterano reserva com elenco cheio


def chance_aposentadoria(idade, contrato_vencendo):
    if idade < min(CHANCE_APOSENTADORIA):
        return 0.0
    chance = CHANCE_APOSENTADORIA.get(idade, CHANCE_APOSENTADORIA_MAX)
    if contrato_vencendo:
        chance += BONUS_CONTRATO_VENCENDO
    return min(1.0, chance)


def _movimento(tipo, jogador, clube, detalhe=""):
    return {
        "tipo": tipo,
        "jogador": jogador.nome,
        "clube": clube.nome,
        "posicao": jogador.posicao,
        "idade": jogador.idade,
        "overall": jogador.overall,
        "detalhe": detalhe,
    }


def _remover(clube, jogador):
    clube.jogadores.remove(jogador)
    for lista in (clube.titulares, clube.reservas):
        if jogador in lista:
            lista.remove(jogador)
    clube.xi_preferido.discard(jogador)


def aposentar(campeonato, rng):
    """Veteranos se aposentam por sorte (ver `chance_aposentadoria`). Quem
    deixaria o clube abaixo do elenco mínimo adia por um ano. Chamar depois
    de `envelhecer` e ANTES de `resolver_contratos` (o contrato ainda não foi
    descontado). Devolve a lista de movimentos."""

    movimentos = []
    for clube in campeonato.clubes:
        for jogador in list(clube.jogadores):
            chance = chance_aposentadoria(jogador.idade, jogador.contrato_anos <= 1)
            if not chance or rng.random() >= chance:
                continue
            if mercado.motivo_saida_bloqueada(clube, jogador):
                movimentos.append(_movimento(
                    "adiou", jogador, clube,
                    "adiou a aposentadoria: o elenco ficaria curto",
                ))
                continue
            _remover(clube, jogador)
            movimentos.append(_movimento("aposentou", jogador, clube))

    # livres (v1.6) também param — sem contrato, como quem não renovou. Sem
    # clube, não entram nos movimentos (a tela da virada é por clube)
    campeonato.livres = [
        j for j in campeonato.livres
        if rng.random() >= chance_aposentadoria(j.idade, True)
    ]
    return movimentos


def _renovar(jogador, anos):
    """Contrato novo pelo salário de mercado; quem tinha multa ganha uma
    nova (3× o valor atual), quem não tinha continua sem."""
    multa = (
        contrato.valor_multa(jogador, "3x")
        if jogador.multa_rescisoria is not None else None
    )
    jogador.assinar_contrato(anos, jogador.salario_referencia(), multa)


def _destino_livre(campeonato, jogador, origem, clube_usuario):
    """Clube da CPU com vaga onde o jogador seria titular — o mais rico, que
    pode pagar melhor. None se nenhum serve (ele deixa a liga)."""
    candidatos = [
        c for c in campeonato.clubes
        if c is not origem
        and c.nome != clube_usuario
        and len(c.jogadores) < mercado.ELENCO_MAX
        and mercado.seria_titular(c, jogador)
    ]
    return max(candidatos, key=lambda c: c.dinheiro, default=None)


def _cpu_dispensa(clube, jogador):
    """A CPU deixa ir o veterano reserva quando o elenco está acima do
    tamanho-alvo — senão, com a base subindo todo ano, os elencos só
    cresceriam."""
    return (
        len(clube.jogadores) > TAMANHO_ALVO
        and jogador.idade >= IDADE_DISPENSA_CPU
        and not mercado.seria_titular(clube, jogador)
    )


def _sair_livre(campeonato, clube, jogador, clube_usuario):
    """Tira o jogador do clube e o leva, de graça, para o clube da CPU com
    vaga onde seria titular (ou para a lista de livres, v1.6). Devolve os
    movimentos."""
    _remover(clube, jogador)
    destino = _destino_livre(campeonato, jogador, clube, clube_usuario)
    if destino is None:
        livres.ficar_livre(jogador)
        campeonato.livres.append(jogador)
        return [_movimento("saiu_livre", jogador, clube, "ficou sem clube")]

    destino.contratar_jogador(jogador)
    jogador.temporadas_no_clube = 0
    jogador.assinar_contrato(
        mercado.CONTRATO_PADRAO_ANOS, jogador.salario_referencia(), None
    )
    return [
        _movimento("saiu_livre", jogador, clube, f"assinou com {destino.nome}"),
        _movimento("chegou_livre", jogador, destino,
                   f"veio de graça do {clube.nome}"),
    ]


def resolver_contratos(campeonato, clube_usuario):
    """Desconta uma temporada de cada contrato. Quem chega a 0:

    - clube da CPU: renova sozinho (salário de mercado, 3 temporadas ou 2
      para veteranos) — menos o veterano reserva com o elenco acima de 18,
      que é dispensado;
    - clube do técnico: sai de graça (não foi renovado).

    Quem sai vai para o clube da CPU com vaga onde seria titular, ou fica
    livre (v1.6). Se a saída deixaria o elenco abaixo do mínimo, o jogador assina 1
    temporada de emergência. Devolve a lista de movimentos."""

    movimentos = []
    vencidos = []
    for clube in campeonato.clubes:
        for jogador in clube.jogadores:
            jogador.contrato_anos -= 1
            if jogador.contrato_anos <= 0:
                vencidos.append((clube, jogador))

    # as saídas vêm depois de descontar todo mundo: quem chega de graça
    # assina contrato novo e não pode ser descontado de novo
    for clube, jogador in vencidos:
        do_tecnico = clube.nome == clube_usuario

        if not do_tecnico and not _cpu_dispensa(clube, jogador):
            anos = (ANOS_RENOVACAO_CPU_VETERANO
                    if jogador.idade >= contrato.IDADE_VETERANO
                    else ANOS_RENOVACAO_CPU)
            _renovar(jogador, anos)
            movimentos.append(_movimento(
                "renovou", jogador, clube, f"{anos} temporadas"
            ))
            continue

        if mercado.motivo_saida_bloqueada(clube, jogador):
            _renovar(jogador, ANOS_EMERGENCIA)
            movimentos.append(_movimento(
                "renovou", jogador, clube,
                "contrato de emergência (1 temporada): o elenco ficaria curto",
            ))
            continue

        movimentos += _sair_livre(campeonato, clube, jogador, clube_usuario)

    return movimentos
