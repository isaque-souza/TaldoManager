"""Categorias de base do técnico (v2.0, passo 4): ver a base, fazer uma
peneira (a cada 90 dias), trocar o nível, promover e dispensar jovens. As
regras ficam em `app.domain.base`.

O que anda sozinho roda dentro da transação de quem chama:
- `treinar`: a cada rodada jogada, os jovens crescem um pouco
- `semear`: a base com que um jogo novo começa (`temporada_service.iniciar`)
- `virar`: a base passa para a temporada seguinte (`carreira_service`)

Nada aqui usa o `random` do processo: a sequência das partidas não muda.
"""

import random
from datetime import date

from app.db.conexao import conectar
from app.domain import base, caixa, calendario, mercado, posicoes
from app.repositories import jovem_base_repository as jovem_repo
from app.repositories import mensagem_repository as mensagem_repo
from app.repositories import simulacao_repository as simulacao_repo
from app.services.temporada_service import TemporadaConcluida, exigir_sem_transmissao


class AcaoInvalida(ValueError):
    """Nível que não existe, sem caixa ou elenco cheio."""


# ---------------------------------------------------------------------------
# o que anda com as rodadas e a virada
# ---------------------------------------------------------------------------

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


def _hoje(sim):
    return calendario.data_atual(sim["temporada"], sim["rodada_atual"], sim["data_atual"])


def _ultima_peneira(sim):
    return date.fromisoformat(sim["ultima_peneira"]) if sim["ultima_peneira"] else None


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
    hoje = _hoje(sim)
    liberada = base.peneira_liberada_em(_ultima_peneira(sim))
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
            "bloqueio": base.motivo_peneira_bloqueada(
                _ultima_peneira(sim), hoje, len(jovens),
            ),
            "liberada_em": liberada.isoformat() if liberada else None,
            "liberada_fmt": (calendario.formatar(liberada, com_semana=False)
                             if liberada and liberada > hoje else None),
            "por_peneira": list(base.NIVEIS[alvo.nivel_base][4]),
            "intervalo_dias": base.INTERVALO_PENEIRA.days,
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


def fazer_peneira(simulacao_id):
    """O técnico faz uma peneira: chegam jovens pelo nível da base, e a
    próxima só depois de INTERVALO_PENEIRA. Devolve {novos, de_fora, base};
    None se a simulação não existe; `AcaoInvalida` se não dá agora."""
    conn = conectar()
    try:
        ctx = _carregar(conn, simulacao_id)
        if ctx is None:
            return None
        sim = ctx.sim
        exigir_sem_transmissao(sim)
        hoje = _hoje(sim)
        ocupadas = jovem_repo.contar(conn, simulacao_id)
        motivo = base.motivo_peneira_bloqueada(_ultima_peneira(sim), hoje, ocupadas)
        if motivo:
            raise AcaoInvalida(motivo)

        nivel = ctx.alvo.nivel_base
        rng = base.rng_da_peneira(sim["seed"], simulacao_id, f"{sim['temporada']}:{hoje}")
        quantos, de_fora = base.quantos_na_peneira(ocupadas, nivel, rng)
        media = sum(j.overall for j in ctx.alvo.jogadores) / len(ctx.alvo.jogadores)
        proibidos = _nomes_proibidos(conn, sim) | {
            j.nome for c in ctx.campeonato.clubes for j in c.jogadores
        } | {j.nome for j in ctx.campeonato.livres}
        jovens = [base.gerar_da_peneira(media, nivel, proibidos, rng) for _ in range(quantos)]
        with conn:
            jovem_repo.inserir(conn, simulacao_id, jovens, hoje.isoformat())
            simulacao_repo.marcar_peneira(conn, simulacao_id, hoje)
            mensagem_repo.inserir(conn, simulacao_id, ctx.rodada, [caixa.peneira(
                [(j.nome, j.idade, j.funcao, int(j.overall), j.potencial) for j in jovens],
                de_fora,
            )])
        ctx.sim = simulacao_repo.buscar(conn, simulacao_id)
        return {"novos": [j.nome for j in jovens], "de_fora": de_fora, "base": _visao(ctx)}
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
