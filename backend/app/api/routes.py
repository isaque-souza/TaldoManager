"""Rotas HTTP da API do Taldo Manager."""

from fastapi import APIRouter, HTTPException, Query, Response

from app.api.schemas import (
    ClubeComElenco,
    ClubeDetalhe,
    ClubeSeed,
    HealthResponse,
    JogadorDetalhe,
    Mercado,
    NovaSimulacao,
    PartidaDetalhe,
    PedidoTransferencia,
    ProximaRodada,
    RodadaDecisao,
    RodadaJogada,
    SimulacaoCriada,
    SimulacaoResponse,
    SimulacaoResumo,
    Tatica,
    TransferenciaResultado,
)
from app.domain.mercado import TransferenciaInvalida
from app.services import mercado_service, simulacao_service, temporada_service
from app.services.temporada_service import TemporadaConcluida

router = APIRouter()

_SEED_DESC = (
    "Semente aleatoria. Com o mesmo seed a simulacao e reproduzivel; "
    "sem seed cada chamada roda uma temporada nova."
)
_CLUBE_DESC = (
    "Nome do clube que o usuario 'dirige'. So esse clube usa a tatica "
    "escolhida; os outros seguem neutros. Omitir = temporada neutra."
)
_TATICA_DESC = "Postura do clube dirigido (ignorada sem 'clube')."


def _erro_de_valor(e):
    return HTTPException(status_code=400, detail=str(e))


@router.get("/health", response_model=HealthResponse, tags=["infra"])
def health():
    return {"status": "ok"}


@router.get("/clubes", response_model=list[ClubeSeed], tags=["infra"])
def listar_clubes():
    """Os clubes do seed — para o usuário escolher qual dirigir."""
    return simulacao_service.listar_clubes()


@router.get("/clubes/{nome}", response_model=ClubeComElenco, tags=["infra"])
def obter_clube_do_seed(nome: str):
    """Elenco e formações disponíveis — para montar a escalação."""
    clube = simulacao_service.elenco_do_clube(nome)
    if clube is None:
        raise HTTPException(status_code=404, detail="Clube não encontrado")
    return clube


@router.get("/simulacao", response_model=SimulacaoResponse, tags=["simulacao"])
def simulacao_rapida(
    seed: int | None = Query(default=None, description=_SEED_DESC),
    clube: str | None = Query(default=None, description=_CLUBE_DESC),
    tatica: Tatica = Query(default="equilibrado", description=_TATICA_DESC),
    formacao: str | None = Query(default=None),
):
    """Roda uma temporada e devolve o resultado sem salvar (modo rápido)."""
    try:
        return simulacao_service.simular_temporada(
            seed=seed, clube_usuario=clube, tatica=tatica, formacao=formacao
        )
    except ValueError as e:
        raise _erro_de_valor(e) from e


@router.get("/simulacoes", response_model=list[SimulacaoResumo], tags=["simulacoes"])
def listar_simulacoes():
    """Lista as simulações salvas, da mais recente para a mais antiga."""
    return simulacao_service.listar_simulacoes()


@router.post(
    "/simulacoes",
    response_model=SimulacaoCriada,
    status_code=201,
    tags=["simulacoes"],
)
def criar_simulacao(cfg: NovaSimulacao | None = None):
    """Roda uma temporada, salva no banco e devolve o id.

    Corpo JSON opcional: `seed`, `clube`, `tatica`, `formacao`, `xi`
    (nomes do XI titular preferido). Sem corpo, roda uma temporada neutra.

    `modo="rodada_a_rodada"` cria um save em andamento (parado antes da
    rodada 1, exige `clube`) — avance com `POST /simulacoes/{id}/rodadas`.
    """
    cfg = cfg or NovaSimulacao()
    try:
        if cfg.modo == "rodada_a_rodada":
            sim_id = temporada_service.iniciar(
                seed=cfg.seed,
                clube_usuario=cfg.clube,
                tatica=cfg.tatica,
                formacao=cfg.formacao,
                xi_preferido=cfg.xi,
            )
        else:
            sim_id = simulacao_service.salvar_temporada(
                seed=cfg.seed,
                clube_usuario=cfg.clube,
                tatica=cfg.tatica,
                formacao=cfg.formacao,
                xi_preferido=cfg.xi,
            )
    except ValueError as e:
        raise _erro_de_valor(e) from e
    return {"id": sim_id}


@router.get(
    "/simulacoes/{simulacao_id}/rodadas/proxima",
    response_model=ProximaRodada,
    tags=["simulacoes"],
)
def obter_proxima_rodada(simulacao_id: int):
    """Confrontos da próxima rodada e a situação do elenco dirigido."""
    dados = temporada_service.proxima_rodada(simulacao_id)
    if dados is None:
        raise HTTPException(status_code=404, detail="Simulação não encontrada")
    return dados


@router.post(
    "/simulacoes/{simulacao_id}/rodadas",
    response_model=RodadaJogada,
    tags=["simulacoes"],
)
def jogar_proxima_rodada(
    simulacao_id: int, decisao: RodadaDecisao | None = None
):
    """Joga a próxima rodada de uma temporada em andamento.

    Corpo JSON opcional (`tatica`, `formacao`, `xi`): o que o técnico muda
    antes da rodada; o que não vier fica como está.
    """
    decisao = decisao or RodadaDecisao()
    try:
        resultado = temporada_service.avancar(
            simulacao_id,
            tatica=decisao.tatica,
            formacao=decisao.formacao,
            xi_preferido=decisao.xi,
        )
    except TemporadaConcluida as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ValueError as e:
        raise _erro_de_valor(e) from e
    if resultado is None:
        raise HTTPException(status_code=404, detail="Simulação não encontrada")
    return resultado


@router.get(
    "/simulacoes/{simulacao_id}/mercado",
    response_model=Mercado,
    tags=["mercado"],
)
def obter_mercado(
    simulacao_id: int,
    posicao: str | None = Query(None, description="Goleiro, Defesa, Meio-Campo ou Atacante"),
    valor_max: int | None = Query(None, ge=0, description="Só jogadores até este valor"),
):
    """Janela, caixa, o elenco dirigido e os jogadores dos outros clubes."""
    try:
        dados = mercado_service.ver_mercado(simulacao_id, posicao, valor_max)
    except TemporadaConcluida as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    if dados is None:
        raise HTTPException(status_code=404, detail="Simulação não encontrada")
    return dados


@router.post(
    "/simulacoes/{simulacao_id}/transferencias",
    response_model=TransferenciaResultado,
    tags=["mercado"],
)
def fazer_transferencia(simulacao_id: int, pedido: PedidoTransferencia):
    """Compra ou vende um jogador pelo valor de mercado (janela aberta)."""
    try:
        feita = mercado_service.transferir(
            simulacao_id, pedido.jogador_id, pedido.tipo
        )
    except TemporadaConcluida as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except TransferenciaInvalida as e:
        raise _erro_de_valor(e) from e
    if feita is None:
        raise HTTPException(status_code=404, detail="Simulação ou jogador não encontrado")
    return feita


@router.get(
    "/simulacoes/{simulacao_id}",
    response_model=SimulacaoResponse,
    tags=["simulacoes"],
)
def obter_simulacao(simulacao_id: int):
    """Classificação, rankings e recordes de uma simulação salva."""
    visao = simulacao_service.carregar_temporada(simulacao_id)
    if visao is None:
        raise HTTPException(status_code=404, detail="Simulação não encontrada")
    return visao


@router.delete("/simulacoes/{simulacao_id}", status_code=204, tags=["simulacoes"])
def apagar_simulacao(simulacao_id: int):
    if not simulacao_service.apagar_simulacao(simulacao_id):
        raise HTTPException(status_code=404, detail="Simulação não encontrada")
    return Response(status_code=204)


@router.get(
    "/simulacoes/{simulacao_id}/clubes/{clube_id}",
    response_model=ClubeDetalhe,
    tags=["simulacoes"],
)
def obter_clube(simulacao_id: int, clube_id: int):
    """Elenco e tabela de jogos de um clube dentro de uma simulação."""
    detalhe = simulacao_service.detalhe_clube(simulacao_id, clube_id)
    if detalhe is None:
        raise HTTPException(status_code=404, detail="Clube não encontrado")
    return detalhe


@router.get(
    "/simulacoes/{simulacao_id}/partidas/{partida_id}",
    response_model=PartidaDetalhe,
    tags=["simulacoes"],
)
def obter_partida(simulacao_id: int, partida_id: int):
    """Placar, estatísticas, timeline e escalações de uma partida."""
    detalhe = simulacao_service.detalhe_partida(simulacao_id, partida_id)
    if detalhe is None:
        raise HTTPException(status_code=404, detail="Partida não encontrada")
    return detalhe


@router.get(
    "/simulacoes/{simulacao_id}/jogadores/{jogador_id}",
    response_model=JogadorDetalhe,
    tags=["simulacoes"],
)
def obter_jogador(simulacao_id: int, jogador_id: int):
    """Ficha do jogador e o game log (nota partida a partida)."""
    detalhe = simulacao_service.game_log_jogador(simulacao_id, jogador_id)
    if detalhe is None:
        raise HTTPException(status_code=404, detail="Jogador não encontrado")
    return detalhe
