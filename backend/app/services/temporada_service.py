"""Temporada simulada rodada a rodada.

Ao contrário de `simulacao_service`, que roda as 38 rodadas de uma vez e grava
só o resultado final, aqui a temporada nasce "em andamento": cada chamada de
`avancar` joga uma rodada, grava as partidas dela e re-grava as stats
acumuladas dos clubes/jogadores, até a 38ª rodada, quando o save vira uma
simulação concluída normal (com campeão).

O estado vivo entre rodadas (energia, corrente do RNG, ...) fica num blob JSON
em `simulacao.estado_json` — ver `app.domain.temporada`.
"""

import io
import json
import random
from contextlib import redirect_stdout
from datetime import datetime, timezone

from app.db.conexao import conectar
from app.domain import caixa, calendario, contrato, copa, disputa, emprestimo, fama, mercado, mercado_cpu, posicoes
from app.domain import vontade
from app.domain.temporada import (
    livres_para_json, restaurar_estado, snapshot_estado,
)
from app.repositories import atuacao_repository as atuacao_repo
from app.repositories import clube_repository as clube_repo
from app.repositories import jogador_repository as jogador_repo
from app.repositories import mensagem_repository as mensagem_repo
from app.repositories import negociacao_repository as negociacao_repo
from app.repositories import oferta_repository as oferta_repo
from app.repositories import lance_repository as lance_repo
from app.repositories import partida_repository as partida_repo
from app.repositories import simulacao_repository as simulacao_repo
from app.repositories import transferencia_repository as transferencia_repo
from app.services import copa_service, oferta_service, relatorio_service, simulacao_service
from scripts.data_loader import (
    LIGA_PADRAO, carregar_campeonato, carregar_campeonato_do_save,
)


class TemporadaConcluida(Exception):
    """Tentou avançar uma temporada que já terminou."""


class PartidaEmAndamento(Exception):
    """Mexer no elenco com a partida do técnico sendo transmitida (v1.2):
    a re-simulação dela depende do elenco de quando a bola rolou."""


# ---------------------------------------------------------------------------
# transmissão em curso (simulação interativa, v1.2 — ver transmissao_service)
# ---------------------------------------------------------------------------

def transmissao_ativa(sim):
    """Há uma partida do técnico sendo transmitida nesta rodada?"""
    if not sim["ao_vivo_json"]:
        return False
    return json.loads(sim["ao_vivo_json"])["rodada"] == sim["rodada_atual"]


def decisoes_ao_vivo(sim):
    """As decisões do técnico na transmissão em curso ([] se não há)."""
    if not transmissao_ativa(sim):
        return []
    return json.loads(sim["ao_vivo_json"])["decisoes"]


def exigir_sem_transmissao(sim):
    if transmissao_ativa(sim):
        raise PartidaEmAndamento(
            "A partida já começou: o elenco fica travado até o apito final"
        )


def _achar_clube(campeonato, nome):
    clube = next((c for c in campeonato.clubes if c.nome == nome), None)
    if clube is None:
        raise ValueError(f"Clube desconhecido: {nome!r}")
    return clube


def _resolver_disputas(conn, simulacao_id, rodada, campeonato):
    """Quem tinha concorrente e ficou sem contrato com o técnico (acordo
    aberto ou jogador que desistiu) assina com o concorrente (v1.9). Devolve
    (negociação, jogador, vendedor ou None, concorrente) do que deu certo;
    se o concorrente não pode mais (caixa, elenco), o acordo só cai."""
    clubes = {c.nome: c for c in campeonato.clubes}
    feitas = []
    for neg in negociacao_repo.listar_disputas_perdidas(conn, simulacao_id, rodada):
        concorrente = clubes.get(neg["concorrente"])
        if neg["clube"] is None:
            vendedor = None
            onde = campeonato.livres
        else:
            vendedor = clubes.get(neg["clube"])
            onde = vendedor.jogadores if vendedor else []
        jogador = next((j for j in onde if j.nome == neg["jogador"]), None)
        if concorrente is None or jogador is None:
            continue
        anos = min(disputa.ANOS_CONCORRENTE, contrato.duracao_max(jogador))
        termos = (anos, neg["concorrente_salario"], None)
        try:
            if vendedor is not None:
                mercado.transferir(jogador, vendedor, concorrente, neg["valor"], termos)
            else:
                mercado.contratar_livre(jogador, campeonato.livres, concorrente, termos)
        except mercado.TransferenciaInvalida:
            continue
        feitas.append((neg, jogador, vendedor, concorrente))
    return feitas


def _confronto_do_clube(rodada, nome):
    """(adversário, mando) do clube `nome` numa rodada do calendário, ou
    (None, None) se ele folga."""
    for mandante, visitante in rodada:
        if mandante.nome == nome:
            return visitante.nome, "casa"
        if visitante.nome == nome:
            return mandante.nome, "fora"
    return None, None


# ---------------------------------------------------------------------------
# iniciar
# ---------------------------------------------------------------------------

def iniciar(seed=None, clube_usuario=None, tatica="equilibrado",
            formacao=None, xi_preferido=None, ligas=LIGA_PADRAO):
    """Cria uma temporada em andamento, parada antes da rodada 1. Devolve o
    id. `ligas` (v1.6): as que rodam juntas — sem dizer, só a Taldo."""

    if not clube_usuario:
        raise ValueError("Simular rodada a rodada exige um clube dirigido")

    if seed is not None:
        random.seed(seed)
    else:
        random.seed()

    campeonato = carregar_campeonato(ligas)
    campeonato.iniciar_copa(copa.classificados_de_inicio(campeonato))
    alvo = _achar_clube(campeonato, clube_usuario)
    simulacao_service._configurar_clube(alvo, tatica, formacao, xi_preferido)

    xi_ef = list(dict.fromkeys(xi_preferido)) if xi_preferido else None
    # a meta nasce do elenco de antes da janela (como na temporada contínua)
    meta = simulacao_service.meta_inicial(campeonato, clube_usuario)
    # a janela da pré-temporada abre: a CPU negocia entre si (v1.7)
    negocios_cpu = mercado_cpu.negociar(
        campeonato.clubes, clube_usuario, mercado_cpu.semente(seed, 1, 1),
    )
    cru = simulacao_service._serializar(
        campeonato, seed, clube_usuario, tatica, formacao, xi_ef
    )

    conn = conectar()
    try:
        with conn:
            sim_id = simulacao_repo.criar(
                conn,
                seed=seed,
                campeao="",
                rodadas=len(campeonato.calendario),
                criada_em=datetime.now(timezone.utc).isoformat(),
                clube_usuario=clube_usuario,
                tatica=tatica,
                formacao=formacao,
                xi_preferido=(
                    json.dumps(xi_ef, ensure_ascii=False) if xi_ef else None
                ),
                estado="em_andamento",
                rodada_atual=1,
                estado_json=json.dumps(snapshot_estado(campeonato)),
                ligas=ligas if tuple(ligas) != LIGA_PADRAO else None,
                # o save começa no primeiro dia da pré-temporada (v2.0)
                data_atual=calendario.inicio(1).isoformat(),
                **meta,
            )
            mapa = clube_repo.inserir(conn, sim_id, cru["clubes"])
            jogador_repo.inserir(conn, sim_id, mapa, cru["jogadores"])
            if meta:
                mensagem_repo.inserir(conn, sim_id, None, [caixa.meta_da_temporada(
                    clube_usuario, meta["meta_posicao"], meta["ranking_forca"],
                )])
            mensagem_repo.inserir(conn, sim_id, None, [
                copa_service.mensagem_de_inicio(campeonato, clube_usuario),
            ])
            # a janela da pré-temporada abre: a CPU negociou e faz ofertas (v1.7)
            oferta_service.registrar_cpu(conn, sim_id, 1, negocios_cpu, mapa, alvo, None)
            oferta_service.abrir_janela(conn, sim_id, 1, campeonato, clube_usuario, None)
        return sim_id
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# preview da próxima rodada
# ---------------------------------------------------------------------------

def proxima_rodada(simulacao_id):
    """Confrontos da próxima rodada e a situação do elenco dirigido. None se a
    simulação não existe."""

    conn = conectar()
    try:
        sim = simulacao_repo.buscar(conn, simulacao_id)
        if sim is None:
            return None

        total = sim["rodadas"]
        if sim["estado"] != "em_andamento":
            return {
                "concluida": True,
                "rodada": None,
                "total_rodadas": total,
                "clube_usuario": sim["clube_usuario"],
                "adversario": None,
                "mando": None,
                "tatica": sim["tatica"],
                "formacao": sim["formacao"],
                "xi_preferido": None,
                "formacoes": [],
                "confrontos": [],
                "elenco": [],
                "transmissao_ativa": False,
            }

        estado_rng = random.getstate()
        try:
            campeonato = carregar_campeonato_do_save(sim)
            restaurar_estado(campeonato, json.loads(sim["estado_json"]))
        finally:
            random.setstate(estado_rng)

        r = campeonato.rodada
        rodada = campeonato.calendario[r - 1]
        alvo = _achar_clube(campeonato, sim["clube_usuario"])
        adversario, mando = _confronto_do_clube(rodada, alvo.nome)

        return {
            "concluida": False,
            "rodada": r,
            "total_rodadas": total,
            "clube_usuario": alvo.nome,
            "adversario": adversario,
            "mando": mando,
            "tatica": alvo.tatica,
            "formacao": alvo.formacao,
            "xi_preferido": sorted(j.nome for j in alvo.xi_preferido) or None,
            "formacoes": list(alvo.FORMACOES),
            # a partida já começou (v1.2): a tela retoma a transmissão
            "transmissao_ativa": transmissao_ativa(sim),
            # o time como o motor vai escalar (editor no campo, v1.2)
            "escalacao": _escalacao(alvo),
            "confrontos": [
                {"mandante": m.nome, "visitante": v.nome, "liga": m.liga}
                for m, v in rodada
            ],
            "elenco": [
                {
                    "nome": j.nome,
                    "posicao": j.posicao,
                    "funcao": j.funcao,
                    "secundarias": list(j.secundarias),
                    "atributos": j.atributos,
                    "overall": j.overall,
                    "energia": j.energia,
                    "condicao": j.condicao,
                    "suspenso": j.suspenso,
                    "jogos_suspensao": j.jogos_suspensao,
                    "amarelos_ciclo": j.amarelos_ciclo,
                    "lesionado": j.lesionado,
                    "rodadas_lesao": j.rodadas_lesao,
                }
                for j in alvo.jogadores
            ],
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# pré-jogo (v1.1): as duas escalações como vão entrar em campo
# ---------------------------------------------------------------------------

# overall a partir do qual o jogador ganha a estrela de craque no pré-jogo
CRAQUE = 88

_LINHA = {"Goleiro": 0, "Defesa": 1, "Meio-Campo": 2, "Atacante": 3}


def _jogador_pre_jogo(j, linha=None):
    dados = {
        "nome": j.nome,
        "numero": j.numero,
        "posicao": j.posicao,
        "funcao": j.funcao,
        "secundarias": list(j.secundarias),
        "overall_por_posicao": j.overall_por_posicao(),
        "atributos": j.atributos,
        "overall": j.overall,
        "energia": round(j.energia),
        "condicao": j.condicao,
        "pendurado": j.amarelos_ciclo == 4,
        "craque": j.overall >= CRAQUE,
    }
    if linha is not None:
        dados["linha"] = linha
        dados["vaga"] = j.vaga
        dados["overall_vaga"] = j.overall_em_campo()
    return dados


def _no_desenho(dados, clube, j):
    """Onde o titular fica no campo: x (largura), y (profundidade) e o
    rótulo da vaga (LE, VOL, PD...), pelo desenho da formação."""
    _, x, y, rotulo = posicoes.desenho(clube.formacao)[j.slot]
    return {**dados, "slot": j.slot, "x": x, "y": y, "rotulo": rotulo}


def _escalacao(clube):
    """XI e banco exatamente como o motor escala no apito
    (Clube.escalar_time é determinístico). Cada titular vem com a vaga
    (v1.3), o overall nela e a `linha` do campo: 0 goleiro, 1 defesa,
    2 meio, 3 ataque — um improvisado fica na linha da vaga, não na dele."""
    clube.escalar_time()
    return {
        "clube": clube.nome,
        "formacao": clube.formacao,
        "tatica": clube.tatica,
        "titulares": [
            _no_desenho(_jogador_pre_jogo(j, _LINHA[posicoes.SETOR[j.vaga]]), clube, j)
            for j in clube.titulares
        ],
        "banco": [_jogador_pre_jogo(j) for j in clube.reservas],
    }


def pre_jogo(simulacao_id):
    """As duas escalações da partida do técnico na próxima rodada, com a
    decisão salva (tática, formação, XI). Só leitura: nada é gravado e o
    gerador aleatório volta ao estado de antes. None se a simulação não
    existe; `TemporadaConcluida` se já terminou; `adversario` None na folga."""

    conn = conectar()
    try:
        sim = simulacao_repo.buscar(conn, simulacao_id)
    finally:
        conn.close()
    if sim is None:
        return None
    if sim["estado"] != "em_andamento":
        raise TemporadaConcluida("Esta temporada já foi concluída")

    estado_rng = random.getstate()
    try:
        campeonato = carregar_campeonato_do_save(sim)
        restaurar_estado(campeonato, json.loads(sim["estado_json"]))
    finally:
        random.setstate(estado_rng)

    r = campeonato.rodada
    alvo = _achar_clube(campeonato, sim["clube_usuario"])
    adversario, mando = _confronto_do_clube(campeonato.calendario[r - 1], alvo.nome)

    base = {
        "rodada": r,
        "total_rodadas": len(campeonato.calendario),
        "clube_usuario": alvo.nome,
        "adversario": adversario,
        "mando": mando,
    }
    if adversario is None:
        return {**base, "mandante": None, "visitante": None}

    rival = _achar_clube(campeonato, adversario)
    mandante, visitante = (alvo, rival) if mando == "casa" else (rival, alvo)
    return {**base, "mandante": _escalacao(mandante), "visitante": _escalacao(visitante)}


# ---------------------------------------------------------------------------
# avançar uma rodada
# ---------------------------------------------------------------------------

def avancar(simulacao_id, tatica=None, formacao=None, xi_preferido=None,
            posicionamento=None):
    """Joga a próxima rodada. Devolve `{rodada_jogada, concluida, ...visão}`.
    None se a simulação não existe; `TemporadaConcluida` se já terminou."""

    conn = conectar()
    try:
        sim = simulacao_repo.buscar(conn, simulacao_id)
        if sim is None:
            return None
        if sim["estado"] != "em_andamento":
            raise TemporadaConcluida(
                "Esta temporada já foi concluída"
            )

        seed = sim["seed"]
        clube_usuario = sim["clube_usuario"]

        # partida transmitida (v1.2): a escalação é a do apito inicial (já
        # gravada) e as mudanças do técnico durante o jogo entram aqui
        ao_vivo = transmissao_ativa(sim)
        decisoes = decisoes_ao_vivo(sim)
        if ao_vivo:
            tatica = formacao = xi_preferido = posicionamento = None

        campeonato = carregar_campeonato_do_save(sim)
        restaurar_estado(campeonato, json.loads(sim["estado_json"]))

        alvo = _achar_clube(campeonato, clube_usuario)
        nova_tatica = tatica or alvo.tatica
        nova_formacao = formacao or alvo.formacao
        # xi None = mantém o salvo; [] = todos no automático
        simulacao_service._configurar_clube(
            alvo, nova_tatica, nova_formacao, xi_preferido, posicionamento
        )
        if xi_preferido is not None:
            xi_ef = list(dict.fromkeys(xi_preferido)) or None
        else:
            xi_ef = sorted(j.nome for j in alvo.xi_preferido) or None

        rodada_jogada = campeonato.rodada
        # para a caixa de entrada: o elenco antes da rodada (v1.3)
        antes = caixa.foto_do_elenco(alvo)
        idolos_antes = {j.nome for j in fama.idolos(alvo)}
        capacidade_antes = alvo.capacidade
        adversario, _ = _confronto_do_clube(
            campeonato.calendario[rodada_jogada - 1], alvo.nome
        )
        with redirect_stdout(io.StringIO()):
            campeonato.jogar_rodada(clube_usuario, decisoes)
        mensagens = caixa.depois_da_rodada(antes, caixa.foto_do_elenco(alvo), adversario)
        # empréstimos (v1.7): quem voltou ao clube de origem e, faltando
        # poucas rodadas, o aviso da opção de compra
        mensagens.append(caixa.emprestimos_encerrados([
            (j.nome, cedente.nome) for j, tomador, cedente in campeonato.devolvidos
            if tomador is alvo
        ]))
        de_volta = [(j.nome, tomador.nome) for j, tomador, cedente in campeonato.devolvidos
                    if cedente is alvo]
        mensagens.append(caixa.emprestados_de_volta(de_volta))
        for j in alvo.jogadores:
            e = j.emprestimo
            if e and e["opcao"] and e["volta"] - campeonato.rodada == emprestimo.AVISO_OPCAO:
                mensagens.append(caixa.emprestimo_acabando(j, emprestimo.AVISO_OPCAO))
        mensagens.append(
            copa_service.mensagem_da_rodada(campeonato, rodada_jogada, clube_usuario)
        )
        if alvo.capacidade > capacidade_antes:
            mensagens.append(caixa.obra_concluida(
                alvo.capacidade - capacidade_antes, alvo.capacidade,
            ))

        novas = [
            p for p in campeonato.partidas_jogadas
            if p["rodada"] == rodada_jogada
        ]

        # disputas que o técnico não fechou a tempo (v1.9): o jogador assina
        # com o concorrente, como os negócios da CPU, depois da rodada
        perdidas = _resolver_disputas(conn, simulacao_id, rodada_jogada, campeonato)
        # ignorar a oferta do clube do sonho também chateia (v1.9): antes de
        # gravar o elenco, com o humor novo
        for r in oferta_repo.listar_do_sonho_abertas(conn, simulacao_id, rodada_jogada):
            jogador = next((j for j in alvo.jogadores if j.nome == r["jogador"]), None)
            if jogador is not None:
                vontade.recusou_o_sonho(jogador)
                mensagens.append(caixa.sonho_recusado(jogador, r["clube"]))

        # a janela do meio da temporada abre: a CPU negocia entre si (v1.7)
        negocios_cpu = []
        if (campeonato.rodada <= len(campeonato.calendario)
                and mercado.janela_aberta(campeonato.rodada)):
            negocios_cpu = mercado_cpu.negociar(
                campeonato.clubes, clube_usuario,
                mercado_cpu.semente(seed, sim["temporada"], campeonato.rodada),
            )

        cru = simulacao_service._serializar(
            campeonato, seed, clube_usuario,
            nova_tatica, nova_formacao, xi_ef,
        )

        concluida = campeonato.rodada > len(campeonato.calendario)
        if concluida:
            # a tabela da liga do técnico (v1.6)
            tabela = campeonato.classificacao(
                simulacao_service.liga_do_tecnico(campeonato, clube_usuario)
            )
            mensagens.append(caixa.fim_de_temporada(
                next(i for i, c in enumerate(tabela, start=1) if c.nome == clube_usuario),
                sim["meta_posicao"], tabela[0].nome, clube_usuario,
            ))
            mensagens.append(caixa.balanco_da_torcida(
                alvo.torcedores_inicial, alvo.torcedores,
            ))
            mensagens.append(caixa.novos_idolos(
                [j.nome for j in fama.idolos(alvo) if j.nome not in idolos_antes],
                clube_usuario,
            ))
        xi_json = (
            json.dumps(xi_ef, ensure_ascii=False) if xi_ef else None
        )

        # a rodada seguinte começa no plano de jogo padrão (v1.2): o que o
        # técnico mexeu antes deste jogo valeu só para ele. Nada aqui sorteia.
        if not concluida:
            from app.services import plano_service   # aqui: evita import circular
            aplicado = plano_service.aplicar_padrao(conn, simulacao_id, alvo)
            if aplicado:
                nova_tatica, nova_formacao, xi_padrao = aplicado
                xi_json = (
                    json.dumps(xi_padrao, ensure_ascii=False) if xi_padrao else None
                )

        with conn:
            # jogar a rodada leva o calendário ao dia do jogo (v2.0)
            dia_do_jogo = calendario.data_da_rodada(sim["temporada"], rodada_jogada)
            simulacao_repo.definir_data(conn, simulacao_id, dia_do_jogo)
            # relatórios do olheiro prontos até o dia do jogo (v2.0)
            relatorio_service.entregar(conn, simulacao_id, dia_do_jogo, rodada_jogada)
            mapa = clube_repo.atualizar(conn, simulacao_id, cru["clubes"])
            mapa_jog = jogador_repo.atualizar(
                conn, simulacao_id, mapa, cru["jogadores"]
            )
            # quem voltou de empréstimo no fim da rodada jogou por quem o
            # tinha emprestado (v1.7): os lances dele são de lá
            for j, tomador, cedente in campeonato.devolvidos:
                mapa_jog[(tomador.nome, j.nome)] = mapa_jog[(cedente.nome, j.nome)]
            # e quem a CPU vendeu depois da rodada jogou por quem vendeu
            for n in negocios_cpu:
                chave = (n.comprador.nome, n.jogador.nome)
                mapa_jog[(n.vendedor.nome, n.jogador.nome)] = mapa_jog[chave]
            for neg, jogador, vendedor, concorrente in perdidas:
                jogador_id = mapa_jog[(concorrente.nome, jogador.nome)]
                if vendedor is not None:
                    mapa_jog[(vendedor.nome, jogador.nome)] = jogador_id
                negociacao_repo.marcar_perdida(conn, neg["id"])
                transferencia_repo.inserir(
                    conn, simulacao_id, rodada_jogada, jogador_id,
                    mapa[vendedor.nome] if vendedor else None, mapa[concorrente.nome],
                    neg["valor"], tipo="transferencia" if vendedor else "livre",
                )
            mensagens.append(caixa.disputas_perdidas(
                [(j.nome, c.nome) for _, j, _, c in perdidas]
            ))
            partida_ids = partida_repo.inserir(conn, simulacao_id, mapa, novas)
            lance_repo.inserir(conn, partida_ids, mapa, mapa_jog, novas)
            atuacao_repo.inserir(conn, partida_ids, mapa, mapa_jog, novas)
            # acordos com clubes sem contrato acertado caem com a rodada (v1.7)
            expiradas = negociacao_repo.expirar_abertas(conn, simulacao_id, rodada_jogada)
            mensagens.append(caixa.acordos_expirados([n["jogador"] for n in expiradas]))
            # e as ofertas da CPU que o técnico não respondeu (v1.7)
            oferta_repo.expirar_abertas(conn, simulacao_id, rodada_jogada)
            mensagem_repo.inserir(conn, simulacao_id, rodada_jogada, mensagens)
            # a janela do meio da temporada abre: a CPU faz ofertas (v1.7)
            if not concluida and mercado.janela_aberta(campeonato.rodada):
                oferta_service.registrar_cpu(
                    conn, simulacao_id, campeonato.rodada, negocios_cpu, mapa, alvo,
                    rodada_jogada,
                )
                oferta_service.abrir_janela(
                    conn, simulacao_id, campeonato.rodada, campeonato,
                    clube_usuario, rodada_jogada,
                )
            if ao_vivo:
                simulacao_repo.definir_ao_vivo(conn, simulacao_id, None)

            if concluida:
                simulacao_repo.atualizar_estado(
                    conn, simulacao_id,
                    estado="concluida",
                    rodada_atual=None,
                    estado_json=None,
                    campeao=tabela[0].nome,
                    tatica=nova_tatica,
                    formacao=nova_formacao,
                    xi_preferido=xi_json,
                )
                # o snapshot some; os livres ficam para a próxima temporada
                simulacao_repo.definir_livres(conn, simulacao_id, json.dumps(
                    livres_para_json(campeonato), ensure_ascii=False,
                ))
                # a copa também (v1.6)
                if cru["copa"]:
                    simulacao_repo.definir_copa(conn, simulacao_id, json.dumps(
                        cru["copa"], ensure_ascii=False,
                    ))
            else:
                simulacao_repo.atualizar_estado(
                    conn, simulacao_id,
                    estado="em_andamento",
                    rodada_atual=campeonato.rodada,
                    estado_json=json.dumps(snapshot_estado(campeonato)),
                    campeao="",
                    tatica=nova_tatica,
                    formacao=nova_formacao,
                    xi_preferido=xi_json,
                )

        visao = simulacao_service._montar_visao(
            simulacao_service._cru_do_banco(conn, simulacao_id)
        )
        liga_de = {c.nome: c.liga for c in campeonato.clubes}
        return {
            "rodada_jogada": rodada_jogada,
            "concluida": concluida,
            "resultados": [
                {
                    "partida_id": pid,
                    "mandante": p["mandante"],
                    "visitante": p["visitante"],
                    "gols_mandante": p["gols_mandante"],
                    "gols_visitante": p["gols_visitante"],
                    "liga": liga_de[p["mandante"]],
                }
                for pid, p in zip(partida_ids, novas)
            ],
            "copa": copa_service.jogos_da_rodada(
                campeonato.copa and campeonato.copa.para_dict(), rodada_jogada, liga_de,
            ),
            **visao,
        }
    finally:
        conn.close()
