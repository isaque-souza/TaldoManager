"""As copas (v1.6; v2.6, várias): a visão para a tela. As regras ficam em
`app.domain.copa`; aqui é só ler o estado delas (no snapshot, durante a
temporada; em `simulacao.copa_json`, depois) e contar onde o clube do
técnico está. Nada é restaurado nem regravado.

O estado é o dict de `Copas.para_dict` (o de antes da v2.6, com uma copa
só, passa por `copa.normalizar`). Uma fase é chamada pela chave
"copa:fase".
"""

import json

from app.db.conexao import conectar
from app.domain import caixa, copa, divisoes, financas
from app.repositories import clube_repository as clube_repo
from app.repositories import simulacao_repository as simulacao_repo


def estado_da_copa(sim):
    """O dict das copas ({"copas": [...]}) de uma simulação, ou None."""
    dados = None
    if sim["estado_json"]:
        dados = json.loads(sim["estado_json"]).get("copa")
    elif sim["copa_json"]:
        dados = json.loads(sim["copa_json"])
    return copa.normalizar(dados)


def fase_do_jogo(dados, chave):
    """{"fase", "nome", "copa", "fase_nome"} do jogo do técnico numa copa
    (`FaseDoJogo` da API)."""
    copa_id, fase = copa.dividir(chave)
    c = copa.copa_de(dados, copa_id)
    return {
        "fase": copa.chave(copa_id, fase),
        "nome": copa.nome_da_chave(dados, chave),
        "copa": c["nome"] if c else copa.NOME_CONTINENTAL,
        "fase_nome": copa.nome_da_fase(fase),
    }


def ver(simulacao_id):
    """{"copa": a visão da primeira copa (a continental, se tem), "copas":
    todas} — vazias quando o save não tem copa; None se a simulação não
    existe."""
    conn = conectar()
    try:
        sim = simulacao_repo.buscar(conn, simulacao_id)
        if sim is None:
            return None
        dados = estado_da_copa(sim)
        if not dados:
            return {"copa": None, "copas": []}
        liga = {
            r["nome"]: r["liga"]
            for r in clube_repo.listar_por_simulacao(conn, simulacao_id)
        }
        visoes = [
            visao(c, sim["clube_usuario"], liga, economia_do(sim))
            for c in _do_tecnico_primeiro(dados["copas"], sim["clube_usuario"])
        ]
        return {"copa": visoes[0] if visoes else None, "copas": visoes}
    finally:
        conn.close()


def _do_tecnico_primeiro(copas, clube):
    """As copas do técnico primeiro (a continental antes da nacional), depois
    as outras, na ordem."""
    return sorted(copas, key=lambda c: not _classificado(c, clube))


def economia_do(sim):
    """A versão das regras de dinheiro do save (v2.5)."""
    return financas.economia_do_save(sim)


def visao(c, clube_usuario, liga_de, economia=2):
    """Uma copa como a tela mostra: as fases (as que ainda não têm confronto
    vêm com `jogos` vazio), o campeão, a próxima data e a situação do clube
    do técnico. `c`: uma copa do dict (`copa.normalizar`)."""
    fases = []
    valores = copa.premios_da_copa(economia, c)
    for fase in c["ordem"]:
        jogos = [_jogo(j, liga_de) for j in c["fases"].get(fase, [])]
        fases.append({
            "fase": fase,
            "nome": copa.nome_da_fase(fase),
            "depois_da_rodada": c["datas"][fase],
            "premio": valores[fase],
            "jogos": jogos,
            "jogada": bool(jogos) and all(j["vencedor"] for j in jogos),
        })
    proxima = next((f for f in fases if not f["jogada"]), None)
    final = c["fases"].get("final")
    return {
        "id": c["id"],
        "nome": c["nome"],
        "tipo": c["tipo"],
        "fases": fases,
        "campeao": final[0]["vencedor"] if final and final[0]["vencedor"] else None,
        "proxima": (
            {"fase": proxima["fase"], "nome": proxima["nome"],
             "depois_da_rodada": proxima["depois_da_rodada"]}
            if proxima else None
        ),
        "seu_clube": situacao(c, clube_usuario),
    }


def _jogo(j, liga_de):
    return {
        **j,
        "liga_mandante": liga_de.get(j["mandante"]),
        "liga_visitante": liga_de.get(j["visitante"]),
    }


def _classificado(c, clube):
    return any(clube in nomes for nomes in c["classificados"].values())


def situacao(c, clube):
    """Onde o clube do técnico está numa copa (`c`, do dict): `fora` (não se
    classificou), `vivo` (com o próximo jogo), `eliminado` (e em que fase)
    ou `campeao`."""
    c = copa._normalizar_copa(c)
    if not _classificado(c, clube):
        return {"estado": "fora", "fase": None, "jogo": None}

    for fase in c["ordem"]:
        jogo = next(
            (j for j in c["fases"].get(fase, [])
             if clube in (j["mandante"], j["visitante"])),
            None,
        )
        if jogo is None:
            # a fase ainda não foi montada: ele passou da anterior
            return {"estado": "vivo", "fase": fase, "jogo": None}
        if jogo["vencedor"] is None:
            return {"estado": "vivo", "fase": fase, "jogo": _do_ponto_de_vista(jogo, clube)}
        if jogo["vencedor"] != clube:
            return {"estado": "eliminado", "fase": fase, "jogo": _do_ponto_de_vista(jogo, clube)}
    return {"estado": "campeao", "fase": "final", "jogo": None}


def _do_ponto_de_vista(jogo, clube):
    em_casa = jogo["mandante"] == clube
    return {
        "adversario": jogo["visitante"] if em_casa else jogo["mandante"],
        "mando": "casa" if em_casa else "fora",
    }


def jogos_da_rodada(dados, rodada, liga_de, clube=None):
    """A fase jogada depois desta rodada da liga (para o resultado da
    rodada): {fase (a chave), nome, jogos} ou None. Com as nacionais no
    mesmo dia, a da copa do `clube`."""
    chave = copa.chave_da_rodada(dados, rodada, clube)
    if chave is None:
        return None
    jogos = copa.jogos_da_chave(dados, chave)
    if not jogos:
        return None
    return {
        "fase": chave,
        "nome": copa.nome_da_chave(dados, chave),
        "jogos": [_jogo(j, liga_de) for j in jogos],
    }


# --- caixa de entrada --------------------------------------------------------

def mensagens_de_inicio(campeonato, clube):
    """As mensagens do começo da temporada: em que copas entramos. A
    continental conta também quando ficamos fora (se a liga é uma Série A);
    a nacional, só a do país do técnico. [] se o save não tem copa."""
    if campeonato.copa is None:
        return []
    liga = next((c.liga for c in campeonato.clubes if c.nome == clube), None)
    mensagens = []
    for c in campeonato.copa:
        dados = c.para_dict()
        sit = situacao(dados, clube)
        if sit["estado"] == "fora":
            nossa = (c.tipo == copa.CONTINENTAL and divisoes.eh_primeira(liga)) or (
                c.tipo == "nacional" and divisoes.pais(liga) == c.id)
            if not nossa:
                continue
        rodada = c.datas[sit["fase"] or c.ordem[0]]
        mensagens.append(caixa.copa_classificacao(
            sit, rodada, sum(copa.premios_da_copa(campeonato.economia, c).values()),
            c.nome, c.tipo,
        ))
    return mensagens


def mensagem_da_rodada(campeonato, rodada, clube):
    """Depois de uma rodada com copa: o resultado do jogo do técnico nela.
    None se não teve copa ou ele não jogou."""
    if campeonato.copa is None:
        return None
    chave = campeonato.copa.fase_da_rodada(rodada, clube)
    if chave is None:
        return None
    copa_id, fase = copa.dividir(chave)
    c = campeonato.copa.copa(copa_id)
    dados = c.para_dict()
    jogo = next(
        (j for j in c.fases.get(fase) or []
         if clube in (j["mandante"], j["visitante"])),
        None,
    )
    if jogo is None or jogo["vencedor"] is None:
        return None
    proxima = None
    sit = situacao(dados, clube)
    if sit["estado"] == "vivo" and sit["jogo"]:
        proxima = (sit["fase"], c.datas[sit["fase"]],
                   sit["jogo"]["adversario"], sit["jogo"]["mando"])
    return caixa.copa_resultado(
        fase, jogo, clube, copa.premios_da_copa(campeonato.economia, c)[fase], proxima, c.nome,
    )
