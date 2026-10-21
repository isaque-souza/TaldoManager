"""Categorias de base do técnico (v2.0, passo 4): ver a base, trocar o
nível, promover e dispensar jovens. As regras ficam em `app.domain.base`.

Os acontecimentos da base andam com o calendário e com as rodadas, dentro
da transação de quem os chama:
- `peneira`: no dia da peneira, chegam os jovens do ano (`calendario_service`
  e `temporada_service.avancar`, como os relatórios do olheiro)
- `treinar`: a cada rodada jogada, os jovens crescem um pouco
- `semear`: a base com que um jogo novo começa (`temporada_service.iniciar`)
- `virar`: a base passa para a temporada seguinte (`carreira_service`)

Nada aqui usa o `random` do processo: a sequência das partidas não muda.
"""

import random

from app.db.conexao import conectar
from app.domain import base, caixa, calendario, mercado, posicoes
from app.repositories import clube_repository as clube_repo
from app.repositories import jovem_base_repository as jovem_repo
from app.repositories import mensagem_repository as mensagem_repo
from app.repositories import simulacao_repository as simulacao_repo
from app.services.temporada_service import TemporadaConcluida, exigir_sem_transmissao


class AcaoInvalida(ValueError):
    """Nível que não existe, sem caixa ou elenco cheio."""


# ---------------------------------------------------------------------------
# o que anda com o calendário e as rodadas
# ---------------------------------------------------------------------------

def _clube_do_tecnico(conn, sim):
    return next(
        c for c in clube_repo.listar_por_simulacao(conn, sim["id"])
        if c["nome"] == sim["clube_usuario"]
    )


def _media_do_elenco(conn, clube_id):
    r = conn.execute(
        "SELECT AVG(overall) FROM jogador WHERE clube_id = ? AND livre = 0",
        (clube_id,),
    ).fetchone()
    return r[0] or base.OVERALL_MIN


def _nomes_proibidos(conn, sim):
    """Quem já existe no save (elencos, dispensados e a base) e, numa
    carreira, quem já passou por ela."""
    nomes = {r[0] for r in conn.execute(
        "SELECT nome FROM jogador WHERE simulacao_id = ?", (sim["id"],)
    )}
    nomes |= jovem_repo.nomes(conn, sim["id"])
    if sim["carreira_id"] is not None:
        from app.services.carreira_service import _nomes_usados   # evita ciclo
        nomes |= _nomes_usados(conn, sim["carreira_id"])
    return nomes


def proxima_peneira(sim):
    """O dia (date) da peneira desta temporada, ou None se já foi."""
    if sim["peneira_feita"] or not sim["clube_usuario"]:
        return None
    return base.data_da_peneira(sim["temporada"])


def peneira(conn, sim, dia, rodada):
    """Se `dia` chegou ao da peneira, os jovens do ano entram na base e
    chega a mensagem. Devolve os jovens novos."""
    data = proxima_peneira(sim)
    if data is None or dia < data:
        return []
    clube = _clube_do_tecnico(conn, sim)
    rng = base.rng_da_peneira(sim["seed"], sim["id"], sim["temporada"])
    proibidos = _nomes_proibidos(conn, sim)
    quantos, de_fora = base.quantos_na_peneira(jovem_repo.contar(conn, sim["id"]), rng)
    media = _media_do_elenco(conn, clube["id"])
    jovens = [base.gerar_da_peneira(media, clube["nivel_base"], proibidos, rng)
              for _ in range(quantos)]
    jovem_repo.inserir(conn, sim["id"], jovens, data.isoformat())
    simulacao_repo.marcar_peneira(conn, sim["id"])
    mensagem_repo.inserir(conn, sim["id"], rodada, [caixa.peneira(
        [(j.nome, j.idade, j.funcao, int(j.overall), j.potencial) for j in jovens],
        de_fora,
    )])
    return jovens


def treinar(conn, simulacao_id, nivel, total_rodadas):
    """Uma rodada de treino para todos os jovens da base."""
    jovens = [j for j, _ in jovem_repo.listar(conn, simulacao_id)]
    for j in jovens:
        base.crescer(j, nivel, total_rodadas)
    jovem_repo.atualizar(conn, jovens)


def semear(conn, simulacao_id, seed, clube, proibidos, dia):
    """A base de um jogo novo: alguns jovens de 15 a 18 anos, do nível
    inicial. `proibidos`: os nomes do campeonato (atualizado)."""
    rng = base.rng_da_peneira(seed, simulacao_id, "inicio")
    media = sum(j.overall for j in clube.jogadores) / len(clube.jogadores)
    jovens = [
        base.gerar_da_peneira(media, clube.nivel_base, proibidos, rng, base.IDADE_INICIAL)
        for _ in range(base.JOVENS_INICIAIS)
    ]
    jovem_repo.inserir(conn, simulacao_id, jovens, dia.isoformat())


def virar(conn, de_id, para_id, seed, temporada):
    """Leva a base para a temporada nova: um ano a mais e o potencial
    revisto; quem chega a IDADE_LIMITE vai embora. Devolve a mensagem."""
    rng = base.rng_da_peneira(seed, para_id, f"virada{temporada}")
    sairam, ficam = [], []
    for jovem, chegou_em in jovem_repo.listar(conn, de_id):
        base.envelhecer(jovem, rng)
        if jovem.idade >= base.IDADE_LIMITE:
            sairam.append(jovem.nome)
        else:
            jovem_repo.inserir(conn, para_id, [jovem], chegou_em)
            ficam.append(jovem)
    return caixa.base_na_virada(sairam, [j.nome for j in ficam if base.ultimo_ano(j)])


# ---------------------------------------------------------------------------
# a tela da base
# ---------------------------------------------------------------------------

def _visao(ctx):
    conn, sim, alvo = ctx.conn, ctx.sim, ctx.alvo
    peneira_em = base.data_da_peneira(sim["temporada"])
    bloqueio = base.motivo_promocao_bloqueada(alvo)
    jovens = []
    for j, chegou_em in jovem_repo.listar(conn, sim["id"]):
        jovens.append({
            "id": j.id,
            "nome": j.nome,
            "idade": j.idade,
            "funcao": j.funcao,
            "posicao": posicoes.SETOR[j.funcao],
            "overall": int(j.overall),
            # quanto falta para o próximo ponto (a barrinha da tela)
            "progresso": round(j.overall - int(j.overall), 2),
            "potencial": j.potencial,
            "chegou_em": chegou_em,
            "ultimo_ano": base.ultimo_ano(j),
        })
    total = len(ctx.campeonato.calendario)
    return {
        "nivel": alvo.nivel_base,
        "caixa": alvo.dinheiro,
        "gasto_temporada": alvo.despesa_base,
        "niveis": base.resumo_niveis(alvo, ctx.rodada - 1, total),
        "vagas": base.VAGAS,
        "idade_limite": base.IDADE_LIMITE,
        "peneira": {
            "data": peneira_em.isoformat(),
            "data_fmt": calendario.formatar(peneira_em, com_semana=False),
            "feita": bool(sim["peneira_feita"]),
        },
        "elenco": {"jogadores": len(alvo.jogadores), "maximo": mercado.ELENCO_MAX},
        "bloqueio_promocao": bloqueio,
        "jovens": jovens,
    }


def _carregar(conn, simulacao_id):
    from app.services.mercado_service import _carregar   # evita ciclo
    return _carregar(conn, simulacao_id)


def ver(simulacao_id):
    """A base do clube dirigido. None se a simulação não existe."""
    conn = conectar()
    try:
        ctx = _carregar(conn, simulacao_id)
        return None if ctx is None else _visao(ctx)
    finally:
        conn.close()


def trocar_nivel(simulacao_id, nivel):
    """Troca o nível da base, pagando a diferença até o fim da temporada
    (descer é de graça). None se a simulação não existe."""
    try:
        base.validar(nivel)
    except base.NivelInvalido as e:
        raise AcaoInvalida(str(e)) from e

    conn = conectar()
    try:
        ctx = _carregar(conn, simulacao_id)
        if ctx is None:
            return None
        clube = ctx.alvo
        custo = base.custo_da_troca(
            clube.nivel_base, nivel, ctx.rodada - 1, len(ctx.campeonato.calendario),
        )
        motivo = base.motivo_troca_bloqueada(clube, nivel, custo)
        if motivo:
            raise AcaoInvalida(motivo)
        if custo:
            clube.lancar("despesa_base", custo)
        clube.nivel_base = nivel
        with conn:
            ctx.gravar()
        return _visao(ctx)
    finally:
        conn.close()


def promover(simulacao_id, jovem_id):
    """Sobe o jovem ao elenco (contrato padrão de 3 temporadas). Devolve
    {jogador, base}; None se a simulação ou o jovem (deste save) não existem."""
    conn = conectar()
    try:
        ctx = _carregar(conn, simulacao_id)
        if ctx is None:
            return None
        jovem = jovem_repo.buscar(conn, simulacao_id, jovem_id)
        if jovem is None:
            return None
        motivo = base.motivo_promocao_bloqueada(ctx.alvo)
        if motivo:
            raise AcaoInvalida(motivo)
        proibidos = (
            {j.nome for c in ctx.campeonato.clubes for j in c.jogadores}
            | {j.nome for j in ctx.campeonato.livres}
            | (jovem_repo.nomes(conn, simulacao_id) - {jovem.nome})
        )
        rng = random.Random(f"promover:{simulacao_id}:{jovem_id}")
        jogador = base.promover(jovem, ctx.alvo, proibidos, rng)
        with conn:
            ctx.gravar()
            jovem_repo.apagar(conn, jovem_id)
        return {"jogador": jogador.nome, "base": _visao(ctx)}
    finally:
        conn.close()


def dispensar(simulacao_id, jovem_id):
    """Tira o jovem da base. Devolve a visão; None se não existe."""
    conn = conectar()
    try:
        sim = simulacao_repo.buscar(conn, simulacao_id)
        if sim is None:
            return None
        if sim["estado"] != "em_andamento":
            raise TemporadaConcluida("A temporada já foi concluída")
        exigir_sem_transmissao(sim)
        if jovem_repo.buscar(conn, simulacao_id, jovem_id) is None:
            return None
        with conn:
            jovem_repo.apagar(conn, jovem_id)
    finally:
        conn.close()
    return ver(simulacao_id)
