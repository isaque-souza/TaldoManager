"""Olheiros da base (v2.0, passo 5): mandar um olheiro para uma região,
receber os relatórios mensais e trazer os indicados para a base. As regras
ficam em `app.domain.olheiro_base`.

O que anda com o calendário roda dentro da transação de quem chama
(`calendario_service` e `temporada_service`, como os relatórios de
contratação):
- `entregar`: os relatórios que ficaram prontos até o dia
- `proximo_relatorio`: o dia do próximo, para o "Continuar" parar nele
- `virar`: missões e indicados seguem para a temporada nova

Nada aqui usa o `random` do processo: a sequência das partidas não muda.
"""

from datetime import date, timedelta
from types import SimpleNamespace

from app.db.conexao import conectar
from app.domain import base, caixa, calendario, olheiro, olheiro_base, posicoes
from app.repositories import clube_repository as clube_repo
from app.repositories import jogador_repository as jogador_repo
from app.repositories import jovem_base_repository as jovem_repo
from app.repositories import mensagem_repository as mensagem_repo
from app.repositories import olheiro_base_repository as repo
from app.repositories import simulacao_repository as simulacao_repo


# ---------------------------------------------------------------------------
# o que anda com o calendário
# ---------------------------------------------------------------------------

def _clube_e_media(conn, sim):
    """A linha do clube do técnico e a média de overall do elenco dele."""
    clube = next(c for c in clube_repo.listar_por_simulacao(conn, sim["id"])
                 if c["nome"] == sim["clube_usuario"])
    overalls = [j["overall"] for j in jogador_repo.listar_por_simulacao(
        conn, sim["id"], com_livres=False) if j["clube"] == sim["clube_usuario"]]
    return clube, sum(overalls) / len(overalls)


def entregar(conn, simulacao_id, dia, rodada):
    """Gera os relatórios das missões com data até `dia` (date) e manda as
    mensagens. Os indicados com o prazo vencido somem antes. Devolve as
    regiões dos relatórios entregues."""
    repo.expirar_indicados(conn, simulacao_id, dia.isoformat())
    missao = repo.vencidas(conn, simulacao_id, dia.isoformat())
    if missao is None:
        return []

    from app.services.base_service import _nomes_proibidos   # evita ciclo
    sim = simulacao_repo.buscar(conn, simulacao_id)
    clube, media = _clube_e_media(conn, sim)
    proibidos = _nomes_proibidos(conn, sim) | repo.nomes_indicados(conn, simulacao_id)
    entregues = []
    while missao is not None:
        regiao = olheiro_base.REGIOES[missao["regiao"]]
        no_dia = date.fromisoformat(missao["proximo_relatorio"])
        mes = missao["relatorios_feitos"] + 1
        rng = base.rng_da_peneira(sim["seed"], simulacao_id, f"olheiro{missao['id']}:{mes}")
        jovens = olheiro_base.gerar_relatorio(
            missao["regiao"], media, clube["nivel_base"], proibidos, rng,
        )
        repo.inserir_indicados(
            conn, simulacao_id, missao["regiao"], jovens, no_dia.isoformat(),
            (no_dia + olheiro_base.VALIDADE_INDICADO).isoformat(),
        )
        if mes >= missao["meses"]:
            repo.encerrar_missao(conn, missao["id"])
        else:
            proximo = no_dia + timedelta(days=olheiro_base.DIAS_POR_RELATORIO)
            repo.avancar_missao(conn, missao["id"], proximo.isoformat())
        mensagem_repo.inserir(conn, simulacao_id, rodada, [caixa.relatorio_olheiro_base(
            regiao["de"], [(j.nome, j.idade, j.funcao, j.pais) for j in jovens],
            mes, missao["meses"],
        )])
        entregues.append(regiao["nome"])
        missao = repo.vencidas(conn, simulacao_id, dia.isoformat())
    return entregues


def proximo_relatorio(conn, simulacao_id):
    """O dia (date) do próximo relatório de um olheiro da base, ou None."""
    dia = repo.proximo_relatorio(conn, simulacao_id)
    return date.fromisoformat(dia) if dia else None


def virar(conn, de, para, temporada):
    """Leva missões e indicados para a temporada `temporada` (a nova). As
    férias entre o último dia da antiga e a pré-temporada não contam: as
    datas andam junto."""
    fim = calendario.data_atual(de["temporada"], de["rodadas"], de["data_atual"])
    dias = max(0, (calendario.inicio(temporada) - fim).days)
    repo.mover(conn, de["id"], para, dias)


# ---------------------------------------------------------------------------
# a tela (dentro da Base)
# ---------------------------------------------------------------------------

def visao(conn, sim, alvo, hoje, ocupadas):
    """Os olheiros da base: regiões, missões em andamento e indicados."""
    missoes = repo.listar_missoes(conn, sim["id"])
    em_missao = [m["regiao"] for m in missoes]
    regioes = []
    for r in olheiro_base.resumo_regioes():
        bloqueios = {
            meses: olheiro_base.motivo_envio_bloqueado(
                r["id"], meses, em_missao, alvo.nivel_base, alvo.dinheiro,
            )
            for meses in olheiro_base.DURACOES
        }
        regioes.append({
            **r,
            "duracoes": [
                {"meses": m, "custo": olheiro_base.custo(r["id"], m), "bloqueio": b}
                for m, b in bloqueios.items()
            ],
        })
    indicados = []
    for j, linha in repo.listar_indicados(conn, sim["id"]):
        est = olheiro.estimativa(
            SimpleNamespace(nome=j.nome, idade=j.idade, overall=int(j.overall),
                            potencial=j.potencial),
            alvo.nivel_olheiro,
        )
        expira = date.fromisoformat(linha["expira_em"])
        indicados.append({
            "id": j.id,
            "nome": j.nome,
            "idade": j.idade,
            "funcao": j.funcao,
            "posicao": posicoes.SETOR[j.funcao],
            "overall": int(j.overall),
            **est,
            "pais": j.pais,
            "regiao": olheiro_base.REGIOES[linha["regiao"]]["nome"],
            "expira_em": expira.isoformat(),
            "dias_restantes": max(0, (expira - hoje).days),
        })
    return {
        "limite": olheiro_base.limite(alvo.nivel_base),
        "regioes": regioes,
        "missoes": [
            {
                "id": m["id"],
                "regiao": olheiro_base.REGIOES[m["regiao"]]["nome"],
                "meses": m["meses"],
                "relatorios_feitos": m["relatorios_feitos"],
                "proximo_relatorio": m["proximo_relatorio"],
                "proximo_fmt": calendario.formatar(
                    date.fromisoformat(m["proximo_relatorio"]), com_semana=False,
                ),
                "dias_ate_o_relatorio": max(
                    0, (date.fromisoformat(m["proximo_relatorio"]) - hoje).days,
                ),
            }
            for m in missoes
        ],
        "indicados": indicados,
        "bloqueio_trazer": (f"A base está cheia ({base.VAGAS} jovens)"
                            if ocupadas >= base.VAGAS else None),
    }


def enviar(simulacao_id, regiao, meses):
    """Manda um olheiro para a `regiao` por `meses`, pagando a missão
    inteira na hora. Devolve a visão da base; None se a simulação não existe."""
    from app.services.base_service import AcaoInvalida, _carregar, _hoje, _visao
    from app.services.temporada_service import exigir_sem_transmissao

    try:
        olheiro_base.validar(regiao, meses)
    except olheiro_base.MissaoInvalida as e:
        raise AcaoInvalida(str(e)) from e

    conn = conectar()
    try:
        ctx = _carregar(conn, simulacao_id)
        if ctx is None:
            return None
        exigir_sem_transmissao(ctx.sim)
        em_missao = [m["regiao"] for m in repo.listar_missoes(conn, simulacao_id)]
        motivo = olheiro_base.motivo_envio_bloqueado(
            regiao, meses, em_missao, ctx.alvo.nivel_base, ctx.alvo.dinheiro,
        )
        if motivo:
            raise AcaoInvalida(motivo)
        custo = olheiro_base.custo(regiao, meses)
        hoje = _hoje(ctx.sim)
        ctx.alvo.lancar("despesa_base", custo)
        with conn:
            ctx.gravar()
            repo.inserir_missao(
                conn, simulacao_id, regiao, meses, hoje.isoformat(),
                olheiro_base.primeiro_relatorio(hoje).isoformat(), custo,
            )
        return _visao(ctx)
    finally:
        conn.close()


def trazer(simulacao_id, indicado_id):
    """Traz o indicado para a base (precisa de vaga). Devolve {jovem, base};
    None se a simulação ou o indicado (deste save) não existem."""
    from app.services.base_service import AcaoInvalida, _carregar, _hoje, _visao
    from app.services.temporada_service import exigir_sem_transmissao

    conn = conectar()
    try:
        ctx = _carregar(conn, simulacao_id)
        if ctx is None:
            return None
        exigir_sem_transmissao(ctx.sim)
        jovem = repo.buscar_indicado(conn, simulacao_id, indicado_id)
        if jovem is None:
            return None
        if jovem_repo.contar(conn, simulacao_id) >= base.VAGAS:
            raise AcaoInvalida(
                f"A base está cheia ({base.VAGAS} jovens): promova ou dispense alguém"
            )
        with conn:
            jovem_repo.inserir(conn, simulacao_id, [jovem], _hoje(ctx.sim).isoformat())
            repo.apagar_indicado(conn, indicado_id)
        return {"jovem": jovem.nome, "base": _visao(ctx)}
    finally:
        conn.close()


def descartar(simulacao_id, indicado_id):
    """Tira o indicado da lista. Devolve a visão da base; None se não existe."""
    from app.services.base_service import ver
    from app.services.temporada_service import TemporadaConcluida, exigir_sem_transmissao

    conn = conectar()
    try:
        sim = simulacao_repo.buscar(conn, simulacao_id)
        if sim is None:
            return None
        if sim["estado"] != "em_andamento":
            raise TemporadaConcluida("A temporada já foi concluída")
        exigir_sem_transmissao(sim)
        if repo.buscar_indicado(conn, simulacao_id, indicado_id) is None:
            return None
        with conn:
            repo.apagar_indicado(conn, indicado_id)
    finally:
        conn.close()
    return ver(simulacao_id)
