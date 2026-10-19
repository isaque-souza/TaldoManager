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

import json
import random

from app.domain import numeros
from app.domain.copa import Copa
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
    # fama (v1.4): muda no fim da temporada e o tempo de casa nas
    # transferências
    "fama", "temporadas_no_clube",
    # lista de transferências (v1.7)
    "a_venda",
)

# campos acumulados de Clube (penalidade_expulsao é zerada a cada jogo)
_CLUBE_CAMPOS = (
    "pontos", "gols_marcados", "gols_sofridos",
    "vitorias", "empates", "derrotas",
    "dinheiro", "dinheiro_inicial", "receita_tv", "receita_bilheteria",
    "receita_premiacao", "despesa_salarios",
    "receita_vendas", "despesa_compras", "historico_caixa",
    "despesa_marketing",
    # torcida (v1.4): cresce e encolhe com a campanha
    "torcedores", "torcedores_inicial", "torcedores_base",
    # estádio (v1.5)
    "capacidade", "ingresso",
    "obra_lugares", "obra_rodadas", "lugares_ampliados", "despesa_estadio",
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
        dados["posicionamento"] = clube.posicionamento
        # o elenco entra no snapshot porque transferências mudam quem joga
        # onde; sem isso, cada jogador voltaria para o clube da seed
        dados["elenco"] = [j.nome for j in clube.jogadores]
        dados["jogadores"] = {j.nome: campos_jogador(j) for j in clube.jogadores}
        clubes[clube.nome] = dados

    return {
        "rodada": campeonato.rodada,
        "rng": [rng[0], list(rng[1]), rng[2]],
        "clubes": clubes,
        # quem está sem clube (v1.6): também muda (contratações)
        "livres": livres_para_json(campeonato),
        # a copa entre as ligas (v1.6); None = sem copa
        "copa": campeonato.copa.para_dict() if campeonato.copa else None,
    }


def campos_jogador(jogador):
    """O que o snapshot guarda de um jogador. `posicao` (e a específica,
    v1.3) vai junto para recriar quem não está na seed (base, v0.8)."""
    return {
        **{c: getattr(jogador, c) for c in _JOGADOR_CAMPOS},
        "posicao": jogador.posicao,
        "funcao": jogador.funcao,
        "secundarias": list(jogador.secundarias),
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
        clube.posicionamento = dados.get("posicionamento")
        for nome, campos in dados["jogadores"].items():
            jogador = por_nome[nome]
            for c in _JOGADOR_CAMPOS:
                # .get: snapshots antigos não têm os campos mais novos
                setattr(jogador, c, campos.get(c, getattr(jogador, c)))

    # snapshots antigos não têm número: quem foi transferido traz o da seed
    # do clube antigo e pode repetir o de alguém
    for clube in campeonato.clubes:
        numeros.revisar(clube)

    # livres (v1.6). Snapshots de antes deles ficam com os da seed, menos
    # quem tiver o nome de alguém da liga (um jovem da base, na carreira)
    # a copa (v1.6): snapshots sem ela (antigos, ou de uma liga só) ficam sem
    campeonato.copa = Copa.de_dict(blob["copa"]) if blob.get("copa") else None

    if "livres" in blob:
        campeonato.livres = restaurar_livres(blob["livres"])
    else:
        na_liga = {j.nome for c in campeonato.clubes for j in c.jogadores}
        campeonato.livres = [
            j for j in campeonato.livres if j.nome not in na_liga
        ]


def livres_para_json(campeonato):
    """Os livres como no snapshot: {nome: campos}. Também é o que fica
    guardado quando a temporada termina (`simulacao.livres_json`)."""
    return {j.nome: campos_jogador(j) for j in campeonato.livres}


def restaurar_livres(dados):
    """O inverso de `livres_para_json`: a lista de `Jogador`."""
    livres = []
    for nome, campos in dados.items():
        jogador = criar_jogador(nome, campos)
        for c in _JOGADOR_CAMPOS:
            setattr(jogador, c, campos.get(c, getattr(jogador, c)))
        livres.append(jogador)
    return livres


def criar_jogador(nome, campos):
    """Jogador que não existe na seed, a partir de um dict com `posicao`,
    `idade`, `overall` e `potencial` (do snapshot ou da tabela `jogador`).
    O resto (contrato, stats) é aplicado depois por quem chamou. Snapshots
    de antes da v1.3 não têm `funcao`: o Jogador cai na padrão do setor."""
    secundarias = campos.get("secundarias")
    if isinstance(secundarias, str):   # na tabela `jogador`, é JSON
        secundarias = json.loads(secundarias)
    return Jogador(
        nome, campos["idade"], campos["posicao"], campos["overall"],
        potencial=campos["potencial"],
        funcao=campos.get("funcao"),
        secundarias=secundarias,
    )
