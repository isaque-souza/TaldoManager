"""Roda uma temporada e transforma o resultado em dados (dict/JSON).

Três caminhos:
- `simular_temporada`  -> roda e devolve a visão, sem tocar no banco (modo rápido)
- `salvar_temporada`   -> roda e persiste; devolve o id da simulação
- `carregar_temporada` -> lê do banco e devolve a mesma visão

A visão (classificação, rankings, recordes, ...) é sempre montada por
`_montar_visao`, então os três caminhos produzem o mesmo formato.
"""

import io
import json
import random
from contextlib import redirect_stdout
from datetime import datetime, timezone

from app.db.conexao import conectar
from app.domain import atributos, copa, diretoria, fama, posicoes
from app.domain import historico as historico_carreira
from app.domain.clube import Clube
from app.domain.jogador import Jogador
from app.repositories import atuacao_repository as atuacao_repo
from app.repositories import carreira_repository as carreira_repo
from app.repositories import clube_repository as clube_repo
from app.repositories import jogador_repository as jogador_repo
from app.repositories import lance_repository as lance_repo
from app.repositories import movimento_repository as movimento_repo
from app.repositories import partida_repository as partida_repo
from app.repositories import simulacao_repository as simulacao_repo
from scripts.data_loader import (
    LIGA_PADRAO, LIGAS, TODAS_AS_LIGAS, carregar_campeonato,
)

NOME_CAMPEONATO = "Taldo"


# ---------------------------------------------------------------------------
# rodar a simulação
# ---------------------------------------------------------------------------

def _configurar_clube(clube, tatica, formacao, xi_preferido, posicionamento=None):
    """Aplica as escolhas do técnico no clube. Levanta ValueError se algo
    não bate com o elenco / opções válidas. `posicionamento` (v1.3):
    {"formacao", "nomes"} com quem joga em cada vaga do desenho; None não
    mexe, {} limpa."""

    if tatica not in Clube.TATICAS:
        raise ValueError(f"Tática inválida: {tatica!r}")
    clube.tatica = tatica

    if formacao is not None:
        if formacao not in Clube.FORMACOES:
            raise ValueError(f"Formação inválida: {formacao!r}")
        clube.formacao = formacao

    # None = não mexe; [] = todos no automático (limpa a preferência)
    if xi_preferido is not None:
        nomes = list(dict.fromkeys(xi_preferido))   # sem duplicatas, na ordem
        if len(nomes) > 11:
            raise ValueError("O XI titular tem no máximo 11 jogadores")
        do_elenco = {j.nome: j for j in clube.jogadores}
        fora = [n for n in nomes if n not in do_elenco]
        if fora:
            raise ValueError(
                f"Não são do elenco de {clube.nome}: {fora}"
            )
        clube.xi_preferido = {do_elenco[n] for n in nomes}

    if posicionamento is not None:
        clube.posicionamento = validar_posicionamento(clube, posicionamento)


def validar_posicionamento(clube, posicionamento):
    """O posicionamento limpo (ou None, se vazio). ValueError se a formação
    não existe, se o tamanho não bate com as vagas, se alguém não é do
    elenco ou se um goleiro está na linha (ou alguém de linha no gol)."""
    if not posicionamento:
        return None
    formacao = posicionamento.get("formacao")
    if formacao not in Clube.FORMACOES:
        raise ValueError(f"Formação inválida no posicionamento: {formacao!r}")
    nomes = list(posicionamento.get("nomes") or [])
    vagas = posicoes.vagas(formacao)
    if len(nomes) != len(vagas):
        raise ValueError(f"O posicionamento do {formacao} tem {len(vagas)} vagas")
    do_elenco = {j.nome: j for j in clube.jogadores}
    for vaga, nome in zip(vagas, nomes):
        if nome is None:
            continue
        if nome not in do_elenco:
            raise ValueError(f"Não é do elenco de {clube.nome}: {nome}")
        if (do_elenco[nome].posicao == "Goleiro") != (vaga == "Goleiro"):
            raise ValueError("Goleiro só joga no gol, e só goleiro joga no gol")
    if len({n for n in nomes if n}) != len([n for n in nomes if n]):
        raise ValueError("Cada jogador ocupa uma vaga só")
    return {"formacao": formacao, "nomes": nomes}


def liga_do_tecnico(campeonato, clube_usuario):
    """A liga do clube dirigido (v1.6) — a do "campeão" do save. Sem clube,
    a primeira."""
    return next(
        (c.liga for c in campeonato.clubes if c.nome == clube_usuario),
        campeonato.ligas[0],
    )


def meta_inicial(campeonato, clube_usuario):
    """Meta da diretoria fixada no início da temporada, a partir do ranking
    de força dos elencos de agora: {meta_posicao, ranking_forca}, ou {} sem
    clube dirigido. Gravada no save — vender craques depois não baixa a meta.
    """
    if not clube_usuario:
        return {}
    # a força é comparada com a da própria liga (v1.6)
    liga = liga_do_tecnico(campeonato, clube_usuario)
    ranking = diretoria.ranking_de_forca(campeonato.clubes_da_liga(liga))[clube_usuario]
    return {
        "meta_posicao": diretoria.meta_da_temporada(ranking),
        "ranking_forca": ranking,
    }


def _rodar(seed, clube_usuario=None, tatica="equilibrado",
           formacao=None, xi_preferido=None, ligas=LIGA_PADRAO):
    if seed is not None:
        random.seed(seed)
    else:
        random.seed()

    campeonato = carregar_campeonato(ligas)
    campeonato.iniciar_copa(copa.classificados_de_inicio(campeonato))

    if clube_usuario is not None:
        alvo = next(
            (c for c in campeonato.clubes if c.nome == clube_usuario), None
        )
        if alvo is None:
            raise ValueError(f"Clube desconhecido: {clube_usuario!r}")
        _configurar_clube(alvo, tatica, formacao, xi_preferido)

    with redirect_stdout(io.StringIO()):
        while campeonato.rodada <= len(campeonato.calendario):
            campeonato.jogar_rodada(clube_usuario)

    return campeonato


# ---------------------------------------------------------------------------
# dados crus (o que vai pro banco)
# ---------------------------------------------------------------------------

def _serializar_jogador(jogador, clube_nome):
    return {
        "id": None,          # preenchido só quando vem do banco
        "nome": jogador.nome,
        "clube": clube_nome,
        "posicao": jogador.posicao,
        "funcao": jogador.funcao,
        "secundarias": json.dumps(list(jogador.secundarias), ensure_ascii=False),
        "overall": jogador.overall,
        "idade": jogador.idade,
        "partidas": jogador.partidas,
        "gols": jogador.gols,
        "assistencias": jogador.assistencias,
        "nota_media": jogador.nota_media(),
        "melhor_nota": round(jogador.melhor_nota, 2),
        "pior_nota": round(jogador.pior_nota, 2),
        "melhor_em_campo": jogador.melhor_em_campo,
        "hat_tricks": jogador.hat_tricks,
        "clean_sheets": jogador.clean_sheets,
        "amarelos": jogador.amarelos,
        "vermelhos": jogador.vermelhos,
        "penaltis": jogador.penaltis,
        "penaltis_perdidos": jogador.penaltis_perdidos,
        "faltas": jogador.faltas,
        "potencial": jogador.potencial,
        "contrato_anos": jogador.contrato_anos,
        "valor_mercado": jogador.valor_mercado(),
        "salario": jogador.salario,
        "multa_rescisoria": jogador.multa_rescisoria,
        "numero": jogador.numero,
        "fama": jogador.fama,
        "temporadas_no_clube": jogador.temporadas_no_clube,
        "a_venda": jogador.a_venda,
    }


def _serializar(campeonato, seed, clube_usuario=None, tatica=None,
                formacao=None, xi_preferido=None):
    # posição na tabela da própria liga (v1.6)
    posicao = {
        c.nome: i
        for liga in campeonato.ligas
        for i, c in enumerate(campeonato.classificacao(liga), start=1)
    }

    clubes = []
    jogadores = []

    for clube in campeonato.clubes:
        jogos = clube.vitorias + clube.empates + clube.derrotas
        clubes.append({
            "nome": clube.nome,
            "pais": clube.pais,
            "posicao_final": posicao[clube.nome],
            "liga": clube.liga,
            "pontos": clube.pontos,
            "jogos": jogos,
            "vitorias": clube.vitorias,
            "empates": clube.empates,
            "derrotas": clube.derrotas,
            "gols_marcados": clube.gols_marcados,
            "gols_sofridos": clube.gols_sofridos,
            "dinheiro_inicial": clube.dinheiro_inicial,
            "dinheiro": clube.dinheiro,
            "receita_tv": clube.receita_tv,
            "receita_bilheteria": clube.receita_bilheteria,
            "receita_premiacao": clube.receita_premiacao,
            "despesa_salarios": clube.despesa_salarios,
            "receita_vendas": clube.receita_vendas,
            "despesa_compras": clube.despesa_compras,
            "historico_caixa": json.dumps(clube.historico_caixa),
            "torcedores": clube.torcedores,
            "torcedores_inicial": clube.torcedores_inicial,
            "despesa_marketing": clube.despesa_marketing,
            "torcedores_base": clube.torcedores_base,
            "capacidade": clube.capacidade,
            "ingresso": clube.ingresso,
            "obra_lugares": clube.obra_lugares,
            "obra_rodadas": clube.obra_rodadas,
            "lugares_ampliados": clube.lugares_ampliados,
            "despesa_estadio": clube.despesa_estadio,
        })

        for jogador in clube.jogadores:
            jogadores.append(_serializar_jogador(jogador, clube.nome))

    return {
        "seed": seed,
        "campeao": campeonato.classificacao(liga_do_tecnico(campeonato, clube_usuario))[0].nome,
        "rodadas": len(campeonato.calendario),
        "clube_usuario": clube_usuario,
        "tatica": tatica,
        "formacao": formacao,
        "xi_preferido": xi_preferido,
        "clubes": clubes,
        "jogadores": jogadores,
        "partidas": list(campeonato.partidas_jogadas),
        # a copa entre as ligas (v1.6); None = sem copa
        "copa": campeonato.copa.para_dict() if campeonato.copa else None,
    }


# ---------------------------------------------------------------------------
# montar a visão a partir dos dados crus
# ---------------------------------------------------------------------------

def _forma_por_clube(partidas):
    """Últimos 5 resultados de cada clube (V/E/D), em ordem cronológica."""
    forma = {}
    for p in sorted(partidas, key=lambda x: x["rodada"]):
        for clube, pro, contra in (
            (p["mandante"], p["gols_mandante"], p["gols_visitante"]),
            (p["visitante"], p["gols_visitante"], p["gols_mandante"]),
        ):
            r = "V" if pro > contra else "D" if pro < contra else "E"
            forma.setdefault(clube, []).append(r)
    return {clube: r[-5:] for clube, r in forma.items()}


def _recordes(partidas):
    maior_goleada = {"valor": 0, "partida": ""}
    mais_gols = {"valor": 0, "partida": ""}

    for p in partidas:
        desc = (
            f"{p['mandante']} {p['gols_mandante']} x "
            f"{p['gols_visitante']} {p['visitante']}"
        )
        dif = abs(p["gols_mandante"] - p["gols_visitante"])
        total = p["gols_mandante"] + p["gols_visitante"]

        if dif > maior_goleada["valor"]:
            maior_goleada = {"valor": dif, "partida": desc}
        if total > mais_gols["valor"]:
            mais_gols = {"valor": total, "partida": desc}

    return {"maior_goleada": maior_goleada, "mais_gols_jogo": mais_gols}


def _evolucao_pontos(partidas, clubes_ordenados):
    """Pontos acumulados de cada clube ao fim de cada rodada (para o gráfico
    da corrida pelo título). `clubes_ordenados` já vem na ordem da tabela."""

    rodadas = sorted({p["rodada"] for p in partidas})

    ganho = {c["nome"]: dict.fromkeys(rodadas, 0) for c in clubes_ordenados}

    for p in partidas:
        gm, gv = p["gols_mandante"], p["gols_visitante"]
        if gm > gv:
            ganho[p["mandante"]][p["rodada"]] += 3
        elif gv > gm:
            ganho[p["visitante"]][p["rodada"]] += 3
        else:
            ganho[p["mandante"]][p["rodada"]] += 1
            ganho[p["visitante"]][p["rodada"]] += 1

    series = []
    for c in clubes_ordenados:
        acumulado = 0
        pontos = []
        for r in rodadas:
            acumulado += ganho[c["nome"]][r]
            pontos.append(acumulado)
        series.append({"clube": c["nome"], "id": c.get("id"), "pontos": pontos})

    return {"rodadas": rodadas, "series": series}


def _historico_caixa(clube):
    """A coluna guarda JSON; saves antigos vêm com '[]'."""
    return json.loads(clube.get("historico_caixa") or "[]")


def _financas_da_liga(clubes, jogadores):
    """Caixa, folha e saldo de cada clube, na ordem da classificação."""
    folha = {}
    for j in jogadores:
        folha[j["clube"]] = folha.get(j["clube"], 0) + (j.get("salario") or 0)

    linhas = []
    for c in clubes:
        receitas = (c.get("receita_tv", 0) + c.get("receita_bilheteria", 0)
                    + c.get("receita_premiacao", 0) + c.get("receita_vendas", 0))
        despesas = (c.get("despesa_salarios", 0) + c.get("despesa_compras", 0)
                    + c.get("despesa_marketing", 0) + c.get("despesa_estadio", 0))
        linhas.append({
            "id": c.get("id"),
            "posicao": c["posicao_final"],
            "clube": c["nome"],
            "caixa_inicial": c.get("dinheiro_inicial", 0),
            "caixa": c.get("dinheiro", 0),
            "saldo": c.get("dinheiro", 0) - c.get("dinheiro_inicial", 0),
            "receitas": receitas,
            "despesas": despesas,
            "folha": folha.get(c["nome"], 0),
            "torcedores": c.get("torcedores", 0),
            "torcedores_inicial": c.get("torcedores_inicial", 0),
        })
    return linhas


def _meta_da_visao(cru, clubes_ordenados):
    """Meta da diretoria com a situação na tabela de agora (ou a final).
    None quando o save não tem meta (sem clube dirigido ou anterior à v1.0)."""
    meta = cru.get("meta_posicao")
    if meta is None:
        return None
    posicao = next(
        c["posicao_final"] for c in clubes_ordenados
        if c["nome"] == cru["clube_usuario"]
    )
    return {
        "posicao": meta,
        "descricao": diretoria.descricao_meta(meta),
        "ranking_forca": cru["ranking_forca"],
        "posicao_atual": posicao,
        "situacao": diretoria.situacao(posicao, meta, len(clubes_ordenados)),
    }


def _ligas_da_visao(cru, liga):
    """(ligas do save, liga do técnico, liga mostrada). Saves antigos não
    trazem `liga` nos clubes: são da Taldo."""
    ligas = list(dict.fromkeys(c.get("liga", "taldo") for c in cru["clubes"]))
    do_tecnico = next(
        (c.get("liga", "taldo") for c in cru["clubes"]
         if c["nome"] == cru.get("clube_usuario")),
        ligas[0],
    )
    if liga not in ligas:
        liga = do_tecnico
    return ligas, do_tecnico, liga


def _montar_visao(cru, liga=None):
    """A visão de uma liga do save (v1.6): tabela, rankings, finanças e
    gráficos só com os clubes dela. Sem `liga` (ou uma que o save não tem),
    a do técnico."""
    ligas, do_tecnico, liga = _ligas_da_visao(cru, liga)
    da_liga = {c["nome"] for c in cru["clubes"] if c.get("liga", "taldo") == liga}
    partidas = [p for p in cru["partidas"] if p["mandante"] in da_liga]
    forma = _forma_por_clube(partidas)

    clubes_ordenados = sorted(
        (c for c in cru["clubes"] if c["nome"] in da_liga),
        key=lambda c: c["posicao_final"],
    )
    # a meta é sempre na liga do técnico, qualquer que seja a mostrada
    clubes_do_tecnico = [
        c for c in cru["clubes"] if c.get("liga", "taldo") == do_tecnico
    ]

    classificacao = [
        {
            "id": c.get("id"),
            "posicao": c["posicao_final"],
            "clube": c["nome"],
            "pais": c["pais"],
            "pontos": c["pontos"],
            "jogos": c["jogos"],
            "vitorias": c["vitorias"],
            "empates": c["empates"],
            "derrotas": c["derrotas"],
            "gols_marcados": c["gols_marcados"],
            "gols_sofridos": c["gols_sofridos"],
            "saldo_gols": c["gols_marcados"] - c["gols_sofridos"],
            "forma": forma.get(c["nome"], []),
        }
        for c in clubes_ordenados
    ]

    jogadores = [j for j in cru["jogadores"] if j["clube"] in da_liga]

    def ranking(chave, filtro=None, limite=None):
        itens = sorted(jogadores, key=chave, reverse=True)
        if filtro is not None:
            itens = [j for j in itens if filtro(j)]
        if limite is not None:
            itens = itens[:limite]
        return itens

    mvp_lista = ranking(historico_carreira.chave_mvp)

    historico = [
        f"Rodada {p['rodada']}: {p['mandante']} "
        f"{p['gols_mandante']} x {p['gols_visitante']} {p['visitante']}"
        for p in sorted(partidas, key=lambda x: x["rodada"])
    ]

    return {
        "campeonato": NOME_CAMPEONATO if liga == "taldo" else LIGAS[liga][0],
        # ligas do save (v1.6): a mostrada e as que dá para escolher
        "liga": liga,
        "ligas": [{"id": l, "nome": LIGAS[l][0]} for l in ligas],
        "seed": cru["seed"],
        "rodadas": cru["rodadas"],
        # o campeão do save é o da liga do técnico; o da outra, o 1º dela
        "campeao": (
            (cru["campeao"] if liga == do_tecnico else clubes_ordenados[0]["nome"])
            if cru["campeao"] else None
        ),
        "estado": cru.get("estado", "concluida"),
        "rodada_atual": cru.get("rodada_atual"),
        "carreira_id": cru.get("carreira_id"),
        "temporada": cru.get("temporada", 1),
        "proxima_temporada_id": cru.get("proxima_temporada_id"),
        "movimentos_virada": cru.get("movimentos_virada", []),
        "evolucao_virada": cru.get("evolucao_virada", []),
        "clube_usuario": cru.get("clube_usuario"),
        "meta": _meta_da_visao(cru, clubes_do_tecnico),
        "cargo": cru.get("cargo"),
        "fim_de_carreira": cru.get("fim_de_carreira"),
        "tatica": cru.get("tatica"),
        "formacao": cru.get("formacao"),
        "xi_preferido": cru.get("xi_preferido"),
        "classificacao": classificacao,
        "financas": _financas_da_liga(clubes_ordenados, jogadores),
        "artilharia": ranking(
            lambda j: (j["gols"], j["assistencias"]),
            filtro=lambda j: j["gols"] > 0,
            limite=20,
        ),
        "assistencias": ranking(
            lambda j: (j["assistencias"], j["gols"]),
            filtro=lambda j: j["assistencias"] > 0,
            limite=20,
        ),
        "melhores_notas": ranking(
            lambda j: (j["nota_media"], j["melhor_nota"], j["melhor_em_campo"]),
            filtro=lambda j: j["partidas"] > 0,
            limite=20,
        ),
        "clean_sheets": ranking(
            lambda j: (j["clean_sheets"], j["nota_media"]),
            filtro=lambda j: j["posicao"] == "Goleiro" and j["clean_sheets"] > 0,
            limite=20,
        ),
        "hat_tricks": ranking(
            lambda j: j["hat_tricks"],
            filtro=lambda j: j["hat_tricks"] > 0,
            limite=20,
        ),
        "disciplina": ranking(
            lambda j: (
                j.get("vermelhos", 0),
                j.get("amarelos", 0),
                j.get("faltas", 0),
            ),
            filtro=lambda j: j.get("vermelhos", 0) or j.get("amarelos", 0),
            limite=20,
        ),
        "penaltis": ranking(
            lambda j: (
                j.get("penaltis", 0) + j.get("penaltis_perdidos", 0),
                j.get("penaltis", 0),
            ),
            filtro=lambda j: j.get("penaltis", 0) or j.get("penaltis_perdidos", 0),
            limite=20,
        ),
        "mvp": mvp_lista[0] if mvp_lista else None,
        "historico": historico,
        "recordes": _recordes(partidas),
        "evolucao": _evolucao_pontos(partidas, clubes_ordenados),
    }


# ---------------------------------------------------------------------------
# API pública do serviço
# ---------------------------------------------------------------------------

def _visao_crua(seed, clube_usuario, tatica, formacao, xi_preferido,
                ligas=LIGA_PADRAO):
    """Roda e serializa. As escolhas do técnico (tática/formação/XI) só
    valem quando há um `clube_usuario`."""
    if clube_usuario:
        tatica_ef, formacao_ef = tatica, formacao
        xi_ef = list(xi_preferido) if xi_preferido else None
    else:
        tatica_ef = formacao_ef = xi_ef = None

    campeonato = _rodar(seed, clube_usuario, tatica, formacao, xi_preferido, ligas)
    return _serializar(
        campeonato, seed, clube_usuario, tatica_ef, formacao_ef, xi_ef
    )


def simular_temporada(seed=None, clube_usuario=None, tatica="equilibrado",
                      formacao=None, xi_preferido=None):
    """Roda a temporada e devolve a visão. Não persiste nada."""
    return _montar_visao(
        _visao_crua(seed, clube_usuario, tatica, formacao, xi_preferido)
    )


def salvar_temporada(seed=None, clube_usuario=None, tatica="equilibrado",
                     formacao=None, xi_preferido=None, ligas=LIGA_PADRAO):
    """Roda a temporada, grava no banco e devolve o id da simulação.
    `ligas` (v1.6): as que rodam juntas — sem dizer, só a Taldo."""
    cru = _visao_crua(seed, clube_usuario, tatica, formacao, xi_preferido, ligas)
    # a seed não muda: o campeonato recém-carregado é o do início (e o
    # clube já foi validado por _visao_crua)
    meta = meta_inicial(carregar_campeonato(ligas), clube_usuario)

    conn = conectar()
    try:
        with conn:
            sim_id = simulacao_repo.criar(
                conn,
                seed=seed,
                campeao=cru["campeao"],
                rodadas=cru["rodadas"],
                criada_em=datetime.now(timezone.utc).isoformat(),
                clube_usuario=cru["clube_usuario"],
                tatica=cru["tatica"],
                formacao=cru["formacao"],
                xi_preferido=(
                    json.dumps(cru["xi_preferido"], ensure_ascii=False)
                    if cru["xi_preferido"]
                    else None
                ),
                ligas=ligas if tuple(ligas) != LIGA_PADRAO else None,
                **meta,
            )
            mapa = clube_repo.inserir(conn, sim_id, cru["clubes"])
            mapa_jog = jogador_repo.inserir(conn, sim_id, mapa, cru["jogadores"])
            partida_ids = partida_repo.inserir(conn, sim_id, mapa, cru["partidas"])
            lance_repo.inserir(
                conn, partida_ids, mapa, mapa_jog, cru["partidas"]
            )
            atuacao_repo.inserir(
                conn, partida_ids, mapa, mapa_jog, cru["partidas"]
            )
            if cru["copa"]:
                simulacao_repo.definir_copa(
                    conn, sim_id, json.dumps(cru["copa"], ensure_ascii=False)
                )
        return sim_id
    finally:
        conn.close()


def listar_simulacoes():
    conn = conectar()
    try:
        sims = []
        for r in simulacao_repo.listar(conn):
            cargo = cargo_da_temporada(conn, r)
            sims.append({
                **dict(r),
                "fim_de_carreira": bool(cargo) and cargo["estado"] == "demitido",
            })
        return sims
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# diretoria: cargo do técnico (v1.0) — calculado, nada guardado
# ---------------------------------------------------------------------------

def _posicao_do_tecnico(conn, sim):
    return next(
        c["posicao_final"]
        for c in clube_repo.listar_por_simulacao(conn, sim["id"])
        if c["nome"] == sim["clube_usuario"]
    )


def _resultado(conn, sim):
    """(posição final do técnico, meta) de uma temporada concluída com
    meta; None se não existe, está em andamento ou é anterior à v1.0."""
    if sim is None or sim["estado"] != "concluida" or sim["meta_posicao"] is None:
        return None
    return _posicao_do_tecnico(conn, sim), sim["meta_posicao"]


def cargo_da_temporada(conn, sim):
    """{estado, motivo} do técnico nesta temporada (olhando também a
    anterior da carreira), ou None se ela não tem meta."""
    if sim["meta_posicao"] is None:
        return None
    anterior = _resultado(conn, simulacao_repo.antecessora(conn, sim["id"]))
    return diretoria.avaliar_cargo(_resultado(conn, sim), anterior)


def _fim_de_carreira(conn, sim, cargo):
    """O balanço do técnico demitido: as temporadas concluídas da carreira
    até esta (ou só esta, se ainda não virou carreira)."""
    if sim["carreira_id"] is None:
        ids = [sim["id"]]
    else:
        ids = [
            t["id"]
            for t in carreira_repo.listar_temporadas(conn, sim["carreira_id"])
            if t["temporada"] <= sim["temporada"] and t["estado"] == "concluida"
        ]
    temporadas = []
    for sid in ids:
        t = simulacao_repo.buscar(conn, sid)
        temporadas.append({
            "posicao": _posicao_do_tecnico(conn, t),
            "meta": t["meta_posicao"],
            "campeao": t["campeao"] == t["clube_usuario"],
        })
    return {
        "clube": sim["clube_usuario"],
        "motivo": cargo["motivo"],
        **diretoria.resumo_carreira(temporadas),
    }


def listar_clubes(ligas=LIGA_PADRAO):
    """Os clubes do seed (para o usuário escolher qual dirigir), com a
    força do elenco, a posição no ranking de força da liga dele (v1.6) e a
    meta que a diretoria daria."""
    campeonato = carregar_campeonato(ligas)
    ranking = {}
    for liga in campeonato.ligas:
        ranking.update(diretoria.ranking_de_forca(campeonato.clubes_da_liga(liga)))
    clubes = []
    for c in campeonato.clubes:
        meta = diretoria.meta_da_temporada(ranking[c.nome])
        clubes.append({
            "nome": c.nome,
            "liga": c.liga,
            "pais": c.pais,
            "forca": diretoria.forca_do_elenco(c),
            "ranking_forca": ranking[c.nome],
            "meta_posicao": meta,
            "meta": diretoria.descricao_meta(meta),
            "dinheiro": c.dinheiro,
            "torcedores": c.torcedores,
            "identidade": c.identidade,
        })
    return clubes


def elenco_do_clube(nome):
    """Clube do seed + elenco (para montar a escalação), de qualquer liga.
    None se não existir."""
    campeonato = carregar_campeonato(TODAS_AS_LIGAS)
    clube = next((c for c in campeonato.clubes if c.nome == nome), None)
    if clube is None:
        return None
    return {
        "nome": clube.nome,
        "pais": clube.pais,
        "formacoes": list(clube.FORMACOES),
        "elenco": [
            {"nome": j.nome, "posicao": j.posicao, "overall": j.overall}
            for j in clube.jogadores
        ],
    }


def apagar_simulacao(simulacao_id):
    conn = conectar()
    try:
        with conn:
            return simulacao_repo.deletar(conn, simulacao_id)
    finally:
        conn.close()


def _evolucao_virada(conn, sim, jogadores):
    """Carreira (v0.8): o elenco do técnico com overall/potencial antes
    (fim da temporada anterior) e agora (depois da virada). Quem não jogou a
    anterior (jovem da base) vem com `overall_antes` None. Ordenado pela
    variação, quem mais subiu primeiro; os novos no fim."""

    if not sim["clube_usuario"] or sim["carreira_id"] is None:
        return []
    anterior = simulacao_repo.antecessora(conn, sim["id"])
    if anterior is None:
        return []
    antes = {
        r["nome"]: r for r in jogador_repo.listar_por_simulacao(conn, anterior["id"])
    }
    linhas = []
    for j in jogadores:
        if j["clube"] != sim["clube_usuario"]:
            continue
        a = antes.get(j["nome"])
        linhas.append({
            "nome": j["nome"],
            "posicao": j["posicao"],
            "idade": j["idade"],
            "overall_antes": a["overall"] if a else None,
            "overall": j["overall"],
            "potencial_antes": a["potencial"] if a else None,
            "potencial": j["potencial"],
            "clube_antes": a["clube"] if a else None,
        })
    return sorted(
        linhas,
        key=lambda l: (l["overall_antes"] is None,
                       -(l["overall"] - (l["overall_antes"] or 0))),
    )


def _idolo(r):
    """O jogador (linha do banco) é ídolo do clube? Saves de antes da v1.4
    não guardam a fama (NULL): ninguém é."""
    return fama.eh_idolo(r["fama"] or 0, r["temporadas_no_clube"] or 0)


def _cru_do_banco(conn, simulacao_id):
    sim = simulacao_repo.buscar(conn, simulacao_id)
    if sim is None:
        return None

    # mantém `id` (o frontend usa para montar os links), descarta as FKs
    clubes = [
        {k: r[k] for k in r.keys() if k != "simulacao_id"}
        for r in clube_repo.listar_por_simulacao(conn, simulacao_id)
    ]

    jogadores = [
        {
            **{k: r[k] for k in r.keys() if k not in ("simulacao_id", "clube_id")},
            "idolo": _idolo(r),
        }
        for r in jogador_repo.listar_por_simulacao(conn, simulacao_id)
    ]

    partidas = [
        {
            "id": r["id"],
            "rodada": r["rodada"],
            "mandante": r["mandante_nome"],
            "visitante": r["visitante_nome"],
            "gols_mandante": r["gols_mandante"],
            "gols_visitante": r["gols_visitante"],
            "posse_mandante": r["posse_mandante"],
            "finalizacoes_mandante": r["finalizacoes_mandante"],
            "finalizacoes_visitante": r["finalizacoes_visitante"],
        }
        for r in partida_repo.listar_por_simulacao(conn, simulacao_id)
    ]

    xi = sim["xi_preferido"]
    sucessora = simulacao_repo.sucessora(conn, simulacao_id)
    movimentos = [
        dict(r) for r in movimento_repo.listar_por_simulacao(conn, simulacao_id)
    ]

    cargo = cargo_da_temporada(conn, sim)
    demitido = cargo is not None and cargo["estado"] == "demitido"

    return {
        "seed": sim["seed"],
        "cargo": cargo,
        "fim_de_carreira": _fim_de_carreira(conn, sim, cargo) if demitido else None,
        "carreira_id": sim["carreira_id"],
        "temporada": sim["temporada"],
        "proxima_temporada_id": sucessora["id"] if sucessora else None,
        "movimentos_virada": movimentos,
        "evolucao_virada": _evolucao_virada(conn, sim, jogadores),
        "campeao": sim["campeao"],
        "rodadas": sim["rodadas"],
        "estado": sim["estado"],
        "rodada_atual": sim["rodada_atual"],
        "clube_usuario": sim["clube_usuario"],
        "meta_posicao": sim["meta_posicao"],
        "ranking_forca": sim["ranking_forca"],
        "tatica": sim["tatica"],
        "formacao": sim["formacao"],
        "xi_preferido": json.loads(xi) if xi else None,
        "clubes": clubes,
        "jogadores": jogadores,
        "partidas": partidas,
    }


def carregar_temporada(simulacao_id, liga=None):
    """Lê a simulação do banco e devolve a visão. None se não existir."""
    conn = conectar()
    try:
        cru = _cru_do_banco(conn, simulacao_id)
        return _montar_visao(cru, liga) if cru is not None else None
    finally:
        conn.close()


def detalhe_clube(simulacao_id, clube_id):
    """Clube + elenco + tabela de jogos. None se o clube não for da simulação."""
    conn = conectar()
    try:
        clube = clube_repo.buscar(conn, clube_id)
        if clube is None or clube["simulacao_id"] != simulacao_id:
            return None

        elenco = [
            {
                **{k: r[k] for k in r.keys() if k not in ("simulacao_id", "clube_id")},
                "salario_referencia": Jogador.salario_de_mercado(r["overall"]),
                "idolo": _idolo(r),
            }
            for r in jogador_repo.listar_por_clube(conn, clube_id)
        ]

        jogos = []
        for p in partida_repo.listar_por_clube(conn, clube_id):
            em_casa = p["mandante_id"] == clube_id
            pro = p["gols_mandante"] if em_casa else p["gols_visitante"]
            contra = p["gols_visitante"] if em_casa else p["gols_mandante"]
            jogos.append({
                "partida_id": p["id"],
                "rodada": p["rodada"],
                "adversario": p["visitante_nome"] if em_casa else p["mandante_nome"],
                "mando": "casa" if em_casa else "fora",
                "gols_pro": pro,
                "gols_contra": contra,
                "resultado": "V" if pro > contra else "D" if pro < contra else "E",
            })

        c = dict(clube)
        c["saldo_gols"] = c["gols_marcados"] - c["gols_sofridos"]
        c["historico_caixa"] = _historico_caixa(c)

        return {"clube": c, "elenco": elenco, "jogos": jogos}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# navegação por partida / jogador (fase 2b)
# ---------------------------------------------------------------------------

def _atuacao_visao(r):
    return {
        "jogador_id": r["jogador_id"],
        "jogador": r["jogador_nome"],
        "posicao": r["jogador_posicao"],
        "titular": bool(r["titular"]),
        "entrou_min": r["entrou_min"],
        "saiu_min": r["saiu_min"],
        "gols": r["gols"],
        "assistencias": r["assistencias"],
        "nota": r["nota"],
    }


# lances que mudam o placar (o pênalti convertido é um tipo à parte)
TIPOS_GOL = ("gol", "penalti")


def ao_vivo(simulacao_id, rodada):
    """Os jogos de uma rodada com os gols minuto a minuto, para o placar dos
    outros jogos na transmissão ao vivo (v1.1). None se a simulação não
    existe; lista vazia se a rodada não foi jogada."""

    conn = conectar()
    try:
        sim = simulacao_repo.buscar(conn, simulacao_id)
        if sim is None:
            return None
        # só a liga do técnico (v1.6): é a tabela que mexe com ele
        liga = {c["nome"]: c["liga"] for c in clube_repo.listar_por_simulacao(conn, simulacao_id)}
        minha = liga.get(sim["clube_usuario"], "taldo")
        partidas = []
        for p in partida_repo.listar_por_simulacao(conn, simulacao_id):
            if p["rodada"] != rodada or liga.get(p["mandante_nome"]) != minha:
                continue
            gols = [
                {"minuto": r["minuto"], "clube": r["clube_nome"]}
                for r in lance_repo.listar_por_partida(conn, p["id"])
                if r["tipo"] in TIPOS_GOL
            ]
            partidas.append({
                "partida_id": p["id"],
                "mandante": p["mandante_nome"],
                "visitante": p["visitante_nome"],
                "gols_mandante": p["gols_mandante"],
                "gols_visitante": p["gols_visitante"],
                "acrescimos": p["acrescimos"],
                "gols": sorted(gols, key=lambda g: g["minuto"]),
            })
        return {"rodada": rodada, "partidas": partidas}
    finally:
        conn.close()


def detalhe_partida(simulacao_id, partida_id):
    """Placar, estatísticas, timeline e as duas escalações (com nota) de uma
    partida. None se a partida não for da simulação."""

    conn = conectar()
    try:
        p = partida_repo.buscar(conn, partida_id)
        if p is None or p["simulacao_id"] != simulacao_id:
            return None

        eventos = [
            {
                "minuto": r["minuto"],
                "tipo": r["tipo"],
                "jogador": r["jogador_nome"],
                "jogador_id": r["jogador_id"],
                "clube": r["clube_nome"],
                "detalhe": r["detalhe"],
            }
            for r in lance_repo.listar_por_partida(conn, partida_id)
        ]

        atuacoes = atuacao_repo.listar_por_partida(conn, partida_id)
        mandante = [
            _atuacao_visao(r) for r in atuacoes if r["clube_id"] == p["mandante_id"]
        ]
        visitante = [
            _atuacao_visao(r) for r in atuacoes if r["clube_id"] == p["visitante_id"]
        ]

        partida = {
            "id": p["id"],
            "rodada": p["rodada"],
            "mandante": {"id": p["mandante_id"], "nome": p["mandante_nome"]},
            "visitante": {"id": p["visitante_id"], "nome": p["visitante_nome"]},
            "gols_mandante": p["gols_mandante"],
            "gols_visitante": p["gols_visitante"],
            "posse_mandante": p["posse_mandante"],
            "posse_visitante": 100 - p["posse_mandante"],
            "finalizacoes_mandante": p["finalizacoes_mandante"],
            "finalizacoes_visitante": p["finalizacoes_visitante"],
            "finalizacoes_gol_mandante": p["finalizacoes_gol_mandante"],
            "finalizacoes_gol_visitante": p["finalizacoes_gol_visitante"],
            "escanteios_mandante": p["escanteios_mandante"],
            "escanteios_visitante": p["escanteios_visitante"],
            "acrescimos": p["acrescimos"],
            "publico": p["publico"],
        }

        return {
            "partida": partida,
            "eventos": eventos,
            "escalacao_mandante": mandante,
            "escalacao_visitante": visitante,
        }
    finally:
        conn.close()


def game_log_jogador(simulacao_id, jogador_id):
    """Ficha do jogador + uma linha por partida disputada (nota, contribuição,
    contexto). None se o jogador não for da simulação."""

    conn = conectar()
    try:
        j = jogador_repo.buscar(conn, jogador_id)
        if j is None or j["simulacao_id"] != simulacao_id:
            return None

        jogos = []
        for r in atuacao_repo.listar_por_jogador(conn, jogador_id):
            em_casa = r["mandante_id"] == j["clube_id"]
            pro = r["gols_mandante"] if em_casa else r["gols_visitante"]
            contra = r["gols_visitante"] if em_casa else r["gols_mandante"]
            jogos.append({
                "partida_id": r["partida_id"],
                "rodada": r["rodada"],
                "adversario": r["visitante_nome"] if em_casa else r["mandante_nome"],
                "mando": "casa" if em_casa else "fora",
                "gols_pro": pro,
                "gols_contra": contra,
                "resultado": "V" if pro > contra else "D" if pro < contra else "E",
                "titular": bool(r["titular"]),
                "entrou_min": r["entrou_min"],
                "saiu_min": r["saiu_min"],
                "gols": r["gols"],
                "assistencias": r["assistencias"],
                "nota": r["nota"],
            })

        jogador = {
            "id": j["id"],
            "nome": j["nome"],
            "clube": j["clube"],
            "clube_id": j["clube_id"],
            "posicao": j["posicao"],
            "funcao": j["funcao"],
            "atributos": atributos.calcular(
                j["nome"], j["posicao"], j["funcao"], j["overall"]
            ),
            "overall": j["overall"],
            "idade": j["idade"],
            "partidas": j["partidas"],
            "gols": j["gols"],
            "assistencias": j["assistencias"],
            "nota_media": j["nota_media"],
            "melhor_nota": j["melhor_nota"],
            "pior_nota": j["pior_nota"],
            "melhor_em_campo": j["melhor_em_campo"],
            "fama": j["fama"],
            "temporadas_no_clube": j["temporadas_no_clube"],
            "idolo": _idolo(j),
            "amarelos": j["amarelos"],
            "vermelhos": j["vermelhos"],
            "penaltis": j["penaltis"],
            "penaltis_perdidos": j["penaltis_perdidos"],
            "faltas": j["faltas"],
            "potencial": j["potencial"],
            "contrato_anos": j["contrato_anos"],
            "valor_mercado": j["valor_mercado"],
            "salario": j["salario"],
            "multa_rescisoria": j["multa_rescisoria"],
        }

        return {"jogador": jogador, "jogos": jogos}
    finally:
        conn.close()
