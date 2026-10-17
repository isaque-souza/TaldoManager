"""Estado vivo de uma temporada, para simular rodada a rodada.

Um `Campeonato` depois de N rodadas fica totalmente descrito por:

- o número da próxima rodada;
- as stats acumuladas de cada clube (pontos, gols, V/E/D, forma) e as
  escolhas do técnico (tática, formação, XI preferido);
- as stats acumuladas de cada jogador, incluindo energia/condição;
- o estado do gerador de números aleatórios, para a corrente continuar
  de onde parou.

Recordes, histórico e a lista de partidas NÃO entram no snapshot: o serviço
os recalcula a partir das tabelas `partida`/`lance`/`atuacao`. O calendário
é regenerado de forma determinística por `carregar_campeonato()` e casado
por nome de clube.
"""

import random

from app.domain import numeros
from app.domain.jogador import Jogador

# campos acumulados de Jogador (os *_partida são zerados a cada jogo)
_JOGADOR_CAMPOS = (
    "gols", "assistencias", "partidas", "soma_nota", "melhor_nota",
    "pior_nota", "melhor_em_campo", "clean_sheets", "hat_tricks",
    "penaltis", "penaltis_perdidos", "faltas", "amarelos", "vermelhos",
    "energia", "condicao",
    "jogos_suspensao", "amarelos_ciclo", "rodadas_lesao",
    # contrato (v0.7): muda com renovações e transferências
    "salario", "contrato_anos", "multa_rescisoria",
    # carreira (v0.8): mudam na virada de temporada (envelhecimento e
    # evolução); sem eles, cada rodada voltaria aos valores da seed
    "idade", "overall", "potencial",
    # camisa (v1.1): vai com o jogador quando ele muda de clube
    "numero",
)

# campos acumulados de Clube (penalidade_expulsao é zerada a cada jogo)
_CLUBE_CAMPOS = (
    "pontos", "gols_marcados", "gols_sofridos",
    "vitorias", "empates", "derrotas",
    "dinheiro", "dinheiro_inicial", "receita_tv", "receita_bilheteria",
    "receita_premiacao", "despesa_salarios",
    "receita_vendas", "despesa_compras", "historico_caixa",
)


def snapshot_estado(campeonato):
    """Serializa o estado vivo do campeonato para um dict JSON-serializável."""

    rng = random.getstate()   # (versao, tupla de 625 ints, gauss_next)

    clubes = {}
    for clube in campeonato.clubes:
        dados = {c: getattr(clube, c) for c in _CLUBE_CAMPOS}
        dados["historico_caixa"] = list(clube.historico_caixa)
        dados["forma"] = list(clube.forma)
        dados["tatica"] = clube.tatica
        dados["formacao"] = clube.formacao
        dados["xi_preferido"] = sorted(j.nome for j in clube.xi_preferido)
        # o elenco entra no snapshot porque transferências mudam quem joga
        # onde; sem isso, cada jogador voltaria para o clube da seed
        dados["elenco"] = [j.nome for j in clube.jogadores]
        # `posicao` vai junto para recriar quem não está na seed (base, v0.8)
        dados["jogadores"] = {
            j.nome: {
                **{c: getattr(j, c) for c in _JOGADOR_CAMPOS},
                "posicao": j.posicao,
            }
            for j in clube.jogadores
        }
        clubes[clube.nome] = dados

    return {
        "rodada": campeonato.rodada,
        "rng": [rng[0], list(rng[1]), rng[2]],
        "clubes": clubes,
    }


def restaurar_estado(campeonato, blob):
    """Aplica um snapshot num campeonato recém-carregado do seed."""

    campeonato.rodada = blob["rodada"]

    versao, estado, gauss_next = blob["rng"]
    random.setstate((versao, tuple(estado), gauss_next))

    # todos os jogadores da liga, por nome (os nomes são únicos na seed)
    por_nome = {j.nome: j for c in campeonato.clubes for j in c.jogadores}

    # quem não está na seed (jovens da base, v0.8) é recriado do snapshot
    for dados in blob["clubes"].values():
        for nome, campos in dados["jogadores"].items():
            if nome not in por_nome:
                por_nome[nome] = criar_jogador(nome, campos)

    for clube in campeonato.clubes:
        dados = blob["clubes"][clube.nome]
        for c in _CLUBE_CAMPOS:
            # .get: snapshots antigos não têm os campos mais novos
            setattr(clube, c, dados.get(c, getattr(clube, c)))
        clube.forma = list(dados["forma"])
        clube.tatica = dados["tatica"]
        clube.formacao = dados["formacao"]

        # remonta o elenco a partir do snapshot (snapshots antigos, sem
        # "elenco", ficam com o elenco da seed)
        if "elenco" in dados:
            clube.jogadores = [por_nome[n] for n in dados["elenco"]]
            clube.titulares = []
            clube.reservas = []

        clube.xi_preferido = {
            por_nome[n] for n in dados["xi_preferido"] if n in por_nome
        }
        for nome, campos in dados["jogadores"].items():
            jogador = por_nome[nome]
            for c in _JOGADOR_CAMPOS:
                # .get: snapshots antigos não têm os campos mais novos
                setattr(jogador, c, campos.get(c, getattr(jogador, c)))

    # snapshots antigos não têm número: quem foi transferido traz o da seed
    # do clube antigo e pode repetir o de alguém
    for clube in campeonato.clubes:
        numeros.revisar(clube)


def criar_jogador(nome, campos):
    """Jogador que não existe na seed, a partir de um dict com `posicao`,
    `idade`, `overall` e `potencial` (do snapshot ou da tabela `jogador`).
    O resto (contrato, stats) é aplicado depois por quem chamou."""
    return Jogador(
        nome, campos["idade"], campos["posicao"], campos["overall"],
        potencial=campos["potencial"],
    )
