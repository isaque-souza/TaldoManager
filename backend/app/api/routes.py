"""Rotas HTTP da API do Taldo Manager."""

from fastapi import APIRouter, HTTPException, Query, Response

from app.api.schemas import (
    CaixaDeEntrada,
    CarreiraDetalhe,
    ClubeComElenco,
    ContratoJogador,
    DecisaoNova,
    DecisaoSalva,
    ClubeDetalhe,
    ClubeSeed,
    HealthResponse,
    JogadorDetalhe,
    ContratacaoLivre,
    Mercado,
    NovaSimulacao,
    PartidaDetalhe,
    NovaContratacaoLivre,
    NovaProposta,
    NovaRenovacao,
    NovaVenda,
    NovoPlano,
    PlanoEdicao,
    Planos,
    OfertasJogador,
    RespostaProposta,
    RespostaRenovacao,
    PreJogo,
    RodadaAoVivo,
    ProximaRodada,
    RodadaDecisao,
    RodadaJogada,
    SimulacaoCriada,
    SimulacaoResponse,
    SimulacaoResumo,
    Tatica,
    TemporadaCriada,
    TransferenciaResultado,
    MomentoPartida,
    Marketing,
    Copa,
    Estadio,
    NovaObra,
    NovoIngresso,
    NovaCampanha,
    Transmissao,
    NovaListaTransferencia,
    ListaTransferencia,
    Dispensa,
    NovoPapel,
    PapelDefinido,
)
from app.domain.contrato import ContratoInvalido
from app.domain.mercado import TransferenciaInvalida
from app.services import (
    carreira_service,
    contrato_service,
    copa_service,
    escalacao_service,
    estadio_service,
    marketing_service,
    mensagem_service,
    mercado_service,
    plano_service,
    simulacao_service,
    temporada_service,
    transmissao_service,
)
from app.services.carreira_service import CarreiraInvalida
from app.services.estadio_service import IngressoInvalido, ObraInvalida
from app.services.marketing_service import CampanhaInvalida
from app.services.plano_service import PlanoInvalido
from app.services.temporada_service import PartidaEmAndamento, TemporadaConcluida
from app.services.transmissao_service import TransmissaoInvalida
from scripts.data_loader import TODAS_AS_LIGAS

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
    """Os clubes do seed, de todas as ligas (v1.6) — para o usuário escolher
    qual dirigir."""
    return simulacao_service.listar_clubes(TODAS_AS_LIGAS)


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
    """Lista as simulações salvas, da jogada por último para a mais antiga."""
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
    # todo jogo novo tem todas as ligas (v1.6), na ordem de LIGAS
    ligas = tuple(l for l in TODAS_AS_LIGAS if l in (cfg.ligas or TODAS_AS_LIGAS))
    try:
        if cfg.modo == "rodada_a_rodada":
            sim_id = temporada_service.iniciar(
                seed=cfg.seed,
                clube_usuario=cfg.clube,
                tatica=cfg.tatica,
                formacao=cfg.formacao,
                xi_preferido=cfg.xi,
                ligas=ligas,
            )
        else:
            sim_id = simulacao_service.salvar_temporada(
                seed=cfg.seed,
                clube_usuario=cfg.clube,
                tatica=cfg.tatica,
                formacao=cfg.formacao,
                xi_preferido=cfg.xi,
                ligas=ligas,
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


@router.get(
    "/simulacoes/{simulacao_id}/pre-jogo",
    response_model=PreJogo,
    tags=["simulacoes"],
)
def obter_pre_jogo(simulacao_id: int):
    """As duas escalações da partida do técnico na próxima rodada, como o
    motor vai escalar no apito (com a decisão salva). Não grava nada."""
    try:
        dados = temporada_service.pre_jogo(simulacao_id)
    except TemporadaConcluida as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    if dados is None:
        raise HTTPException(status_code=404, detail="Simulação não encontrada")
    return dados


@router.get(
    "/simulacoes/{simulacao_id}/rodadas/{rodada}/ao-vivo",
    response_model=RodadaAoVivo,
    tags=["simulacoes"],
)
def obter_rodada_ao_vivo(simulacao_id: int, rodada: int):
    """Os jogos de uma rodada já jogada com os gols por minuto (placar dos
    outros jogos na transmissão ao vivo)."""
    dados = simulacao_service.ao_vivo(simulacao_id, rodada)
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
            posicionamento=_posicionamento(decisao.posicionamento),
        )
    except TemporadaConcluida as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ValueError as e:
        raise _erro_de_valor(e) from e
    if resultado is None:
        raise HTTPException(status_code=404, detail="Simulação não encontrada")
    return resultado


@router.patch(
    "/simulacoes/{simulacao_id}/decisao",
    response_model=DecisaoSalva,
    tags=["simulacoes"],
)
def salvar_decisao(simulacao_id: int, decisao: RodadaDecisao):
    """Autosave da escalação: grava `tatica`, `formacao` e `xi` para a
    próxima rodada sem jogá-la. O que não vier fica como está."""
    try:
        salva = escalacao_service.salvar_decisao(
            simulacao_id,
            tatica=decisao.tatica,
            formacao=decisao.formacao,
            xi_preferido=decisao.xi,
            posicionamento=_posicionamento(decisao.posicionamento),
        )
    except (TemporadaConcluida, PartidaEmAndamento) as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ValueError as e:
        raise _erro_de_valor(e) from e
    if salva is None:
        raise HTTPException(status_code=404, detail="Simulação não encontrada")
    return salva


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


def _erro_de_mercado(e):
    if isinstance(e, TemporadaConcluida):
        return HTTPException(status_code=409, detail=str(e))
    return _erro_de_valor(e)


@router.post(
    "/simulacoes/{simulacao_id}/propostas",
    response_model=RespostaProposta,
    tags=["mercado"],
)
def fazer_proposta(simulacao_id: int, proposta: NovaProposta):
    """Proposta de compra por um jogador de outro clube. O clube aceita,
    contrapropõe ou recusa; cobrindo a multa rescisória, não pode recusar."""
    try:
        resposta = mercado_service.propor(
            simulacao_id, proposta.jogador_id, proposta.valor
        )
    except (TemporadaConcluida, PartidaEmAndamento, TransferenciaInvalida) as e:
        raise _erro_de_mercado(e) from e
    if resposta is None:
        raise HTTPException(status_code=404, detail="Simulação ou jogador não encontrado")
    return resposta


@router.post(
    "/simulacoes/{simulacao_id}/livres/contratar",
    response_model=ContratacaoLivre,
    tags=["mercado"],
)
def contratar_livre(simulacao_id: int, contratacao: NovaContratacaoLivre):
    """Contrata um jogador sem clube: sem transferência, só as luvas."""
    try:
        feita = mercado_service.contratar_livre(simulacao_id, contratacao.nome)
    except (TemporadaConcluida, PartidaEmAndamento, TransferenciaInvalida) as e:
        raise _erro_de_mercado(e) from e
    if feita is None:
        raise HTTPException(status_code=404, detail="Simulação ou jogador livre não encontrado")
    return feita


@router.get(
    "/simulacoes/{simulacao_id}/jogadores/{jogador_id}/ofertas",
    response_model=OfertasJogador,
    tags=["mercado"],
)
def obter_ofertas(simulacao_id: int, jogador_id: int):
    """O que cada clube paga por um jogador do seu elenco."""
    try:
        dados = mercado_service.ofertas(simulacao_id, jogador_id)
    except (TemporadaConcluida, PartidaEmAndamento, TransferenciaInvalida) as e:
        raise _erro_de_mercado(e) from e
    if dados is None:
        raise HTTPException(status_code=404, detail="Simulação ou jogador não encontrado")
    return dados


@router.post(
    "/simulacoes/{simulacao_id}/vendas",
    response_model=TransferenciaResultado,
    tags=["mercado"],
)
def fazer_venda(simulacao_id: int, venda: NovaVenda):
    """Aceita a oferta de um clube por um jogador do seu elenco."""
    try:
        feita = mercado_service.vender(simulacao_id, venda.jogador_id, venda.clube)
    except (TemporadaConcluida, PartidaEmAndamento, TransferenciaInvalida) as e:
        raise _erro_de_mercado(e) from e
    if feita is None:
        raise HTTPException(status_code=404, detail="Simulação ou jogador não encontrado")
    return feita


@router.put(
    "/simulacoes/{simulacao_id}/jogadores/{jogador_id}/a-venda",
    response_model=ListaTransferencia,
    tags=["elenco"],
)
def marcar_a_venda(simulacao_id: int, jogador_id: int, lista: NovaListaTransferencia):
    """Põe ou tira um jogador do seu elenco da lista de transferências."""
    try:
        feito = mercado_service.marcar_a_venda(simulacao_id, jogador_id, lista.a_venda)
    except (TemporadaConcluida, PartidaEmAndamento, TransferenciaInvalida) as e:
        raise _erro_de_mercado(e) from e
    if feito is None:
        raise HTTPException(status_code=404, detail="Simulação ou jogador não encontrado")
    return feito


@router.put(
    "/simulacoes/{simulacao_id}/jogadores/{jogador_id}/papel",
    response_model=PapelDefinido,
    tags=["elenco"],
)
def definir_papel(simulacao_id: int, jogador_id: int, novo: NovoPapel):
    """Muda o papel prometido (titular, rotacao, promessa ou reserva).
    Rebaixar deixa o jogador incomodado; promover, contente."""
    try:
        feito = mercado_service.definir_papel(simulacao_id, jogador_id, novo.papel)
    except (TemporadaConcluida, PartidaEmAndamento, TransferenciaInvalida) as e:
        raise _erro_de_mercado(e) from e
    if feito is None:
        raise HTTPException(status_code=404, detail="Simulação ou jogador não encontrado")
    return feito


@router.post(
    "/simulacoes/{simulacao_id}/jogadores/{jogador_id}/dispensa",
    response_model=Dispensa,
    tags=["elenco"],
)
def dispensar(simulacao_id: int, jogador_id: int):
    """Rescinde com um jogador do seu elenco: paga metade dos salários que
    o contrato ainda deve e ele fica sem clube. Vale a qualquer rodada."""
    try:
        feita = mercado_service.dispensar(simulacao_id, jogador_id)
    except (TemporadaConcluida, PartidaEmAndamento, TransferenciaInvalida) as e:
        raise _erro_de_mercado(e) from e
    if feita is None:
        raise HTTPException(status_code=404, detail="Simulação ou jogador não encontrado")
    return feita


@router.get(
    "/simulacoes/{simulacao_id}/jogadores/{jogador_id}/contrato",
    response_model=ContratoJogador,
    tags=["contratos"],
)
def obter_contrato(simulacao_id: int, jogador_id: int):
    """Contrato atual de um jogador do seu elenco e as opções de renovação."""
    try:
        dados = contrato_service.ver_contrato(simulacao_id, jogador_id)
    except (TemporadaConcluida, PartidaEmAndamento, ContratoInvalido) as e:
        raise _erro_de_mercado(e) from e
    if dados is None:
        raise HTTPException(status_code=404, detail="Simulação ou jogador não encontrado")
    return dados


@router.post(
    "/simulacoes/{simulacao_id}/renovacoes",
    response_model=RespostaRenovacao,
    tags=["contratos"],
)
def fazer_renovacao(simulacao_id: int, proposta: NovaRenovacao):
    """Proposta de renovação: o jogador aceita, contrapropõe ou recusa."""
    try:
        resposta = contrato_service.renovar(
            simulacao_id, proposta.jogador_id, proposta.salario,
            proposta.anos, proposta.multa, proposta.papel,
        )
    except (TemporadaConcluida, PartidaEmAndamento, ContratoInvalido) as e:
        raise _erro_de_mercado(e) from e
    if resposta is None:
        raise HTTPException(status_code=404, detail="Simulação ou jogador não encontrado")
    return resposta


@router.get(
    "/simulacoes/{simulacao_id}/marketing",
    response_model=Marketing,
    tags=["torcida"],
)
def ver_marketing(simulacao_id: int):
    """Torcida do clube dirigido e as campanhas de marketing possíveis."""
    try:
        dados = marketing_service.ver(simulacao_id)
    except TemporadaConcluida as e:
        raise _erro_de_mercado(e) from e
    if dados is None:
        raise HTTPException(status_code=404, detail="Simulação não encontrada")
    return dados


@router.post(
    "/simulacoes/{simulacao_id}/marketing",
    response_model=Marketing,
    tags=["torcida"],
)
def fazer_campanha(simulacao_id: int, campanha: NovaCampanha):
    """Faz uma campanha de marketing (uma por turno, com caixa para pagar)."""
    try:
        dados = marketing_service.lancar(simulacao_id, campanha.tipo)
    except (TemporadaConcluida, PartidaEmAndamento, CampanhaInvalida) as e:
        raise _erro_de_mercado(e) from e
    if dados is None:
        raise HTTPException(status_code=404, detail="Simulação não encontrada")
    return dados


@router.get(
    "/simulacoes/{simulacao_id}/copa",
    response_model=Copa,
    tags=["copa"],
)
def ver_copa(simulacao_id: int):
    """Copa entre as ligas (v1.6): as fases com os jogos, o campeão, a
    próxima data e onde o clube do técnico está. `copa` vem null quando o
    save não tem copa (só uma liga)."""
    dados = copa_service.ver(simulacao_id)
    if dados is None:
        raise HTTPException(status_code=404, detail="Simulação não encontrada")
    return dados


@router.get(
    "/simulacoes/{simulacao_id}/estadio",
    response_model=Estadio,
    tags=["estadio"],
)
def ver_estadio(simulacao_id: int):
    """Estádio do clube dirigido: capacidade, faixas do ingresso (com
    público e receita estimados) e o público da temporada."""
    try:
        dados = estadio_service.ver(simulacao_id)
    except TemporadaConcluida as e:
        raise _erro_de_mercado(e) from e
    if dados is None:
        raise HTTPException(status_code=404, detail="Simulação não encontrada")
    return dados


@router.post(
    "/simulacoes/{simulacao_id}/estadio/ingresso",
    response_model=Estadio,
    tags=["estadio"],
)
def trocar_ingresso(simulacao_id: int, ingresso: NovoIngresso):
    """Troca a faixa do ingresso (popular, normal ou premium); vale a
    partir do próximo jogo em casa."""
    try:
        dados = estadio_service.definir_ingresso(simulacao_id, ingresso.faixa)
    except (TemporadaConcluida, PartidaEmAndamento, IngressoInvalido) as e:
        raise _erro_de_mercado(e) from e
    if dados is None:
        raise HTTPException(status_code=404, detail="Simulação não encontrada")
    return dados


@router.post(
    "/simulacoes/{simulacao_id}/estadio/obra",
    response_model=Estadio,
    tags=["estadio"],
)
def ampliar_estadio(simulacao_id: int, obra: NovaObra):
    """Começa uma ampliação (pequena, média ou grande), paga à vista; uma
    por vez. Fica pronta depois do prazo, em rodadas jogadas."""
    try:
        dados = estadio_service.iniciar_obra(simulacao_id, obra.tipo)
    except (TemporadaConcluida, PartidaEmAndamento, ObraInvalida) as e:
        raise _erro_de_mercado(e) from e
    if dados is None:
        raise HTTPException(status_code=404, detail="Simulação não encontrada")
    return dados


@router.post(
    "/simulacoes/{simulacao_id}/proxima-temporada",
    response_model=TemporadaCriada,
    status_code=201,
    tags=["carreira"],
)
def continuar_carreira(simulacao_id: int):
    """Modo carreira: cria a temporada seguinte de uma temporada concluída
    (com clube dirigido). Elencos, contratos e caixa são herdados; o resto
    começa do zero. Na primeira vez, a carreira é criada e esta temporada
    vira a temporada 1."""
    try:
        criada = carreira_service.proxima_temporada(simulacao_id)
    except CarreiraInvalida as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    if criada is None:
        raise HTTPException(status_code=404, detail="Simulação não encontrada")
    return criada


@router.get(
    "/carreiras/{carreira_id}",
    response_model=CarreiraDetalhe,
    tags=["carreira"],
)
def obter_carreira(carreira_id: int):
    """A carreira e suas temporadas, com o campeão de cada."""
    carreira = carreira_service.detalhe_carreira(carreira_id)
    if carreira is None:
        raise HTTPException(status_code=404, detail="Carreira não encontrada")
    return carreira


@router.get(
    "/simulacoes/{simulacao_id}",
    response_model=SimulacaoResponse,
    tags=["simulacoes"],
)
def obter_simulacao(
    simulacao_id: int,
    liga: str | None = Query(None, description="taldo ou premier; sem dizer, a do técnico"),
):
    """Classificação, rankings e recordes de uma liga de uma simulação
    salva (v1.6: por padrão, a liga do técnico)."""
    visao = simulacao_service.carregar_temporada(simulacao_id, liga)
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


# ---------------------------------------------------------------------------
# simulação interativa (v1.2): a partida do técnico transmitida
# ---------------------------------------------------------------------------

def _erro_transmissao(e):
    if isinstance(e, TransmissaoInvalida):
        return HTTPException(status_code=400, detail=str(e))
    return HTTPException(status_code=409, detail=str(e))


@router.post(
    "/simulacoes/{simulacao_id}/transmissao",
    response_model=Transmissao,
    tags=["simulacoes"],
)
def iniciar_transmissao(simulacao_id: int, decisao: RodadaDecisao | None = None):
    """Rola a bola na partida do técnico: grava a escalação (como o PATCH
    /decisao) e devolve a partida inteira. Nada da rodada é gravado até o
    `POST /rodadas`, que aplica as mudanças feitas durante o jogo. Se a
    partida já começou, retoma (e o corpo é ignorado)."""
    decisao = decisao or RodadaDecisao()
    try:
        dados = transmissao_service.iniciar(
            simulacao_id, decisao.tatica, decisao.formacao, decisao.xi,
            _posicionamento(decisao.posicionamento),
        )
    except (TemporadaConcluida, TransmissaoInvalida) as e:
        raise _erro_transmissao(e) from e
    except ValueError as e:
        raise _erro_de_valor(e) from e
    if dados is None:
        raise HTTPException(status_code=404, detail="Simulação não encontrada")
    return dados


@router.get(
    "/simulacoes/{simulacao_id}/transmissao",
    response_model=Transmissao,
    tags=["simulacoes"],
)
def obter_transmissao(simulacao_id: int):
    """A partida em andamento (404 se não há)."""
    try:
        dados = transmissao_service.atual(simulacao_id)
    except TemporadaConcluida as e:
        raise _erro_transmissao(e) from e
    if dados is None:
        raise HTTPException(status_code=404, detail="Nenhuma partida em andamento")
    return dados


@router.get(
    "/simulacoes/{simulacao_id}/transmissao/estado",
    response_model=MomentoPartida,
    tags=["simulacoes"],
)
def obter_momento(simulacao_id: int, minuto: int = Query(..., ge=0)):
    """Os dois times ao fim do minuto: em campo, banco, substituições e
    tática — o que o técnico vê ao pausar."""
    try:
        dados = transmissao_service.estado(simulacao_id, minuto)
    except (TemporadaConcluida, TransmissaoInvalida) as e:
        raise _erro_transmissao(e) from e
    if dados is None:
        raise HTTPException(status_code=404, detail="Simulação não encontrada")
    return dados


@router.post(
    "/simulacoes/{simulacao_id}/transmissao/decisoes",
    response_model=Transmissao,
    tags=["simulacoes"],
)
def decidir_na_partida(simulacao_id: int, decisao: DecisaoNova):
    """Muda a tática, a formação ou faz uma substituição a partir de
    `minuto` e devolve a partida refeita (igual até o minuto anterior)."""
    try:
        dados = transmissao_service.decidir(
            simulacao_id, decisao.minuto,
            tatica=decisao.tatica, sai=decisao.sai, entra=decisao.entra,
            formacao=decisao.formacao,
        )
    except (TemporadaConcluida, TransmissaoInvalida) as e:
        raise _erro_transmissao(e) from e
    if dados is None:
        raise HTTPException(status_code=404, detail="Simulação não encontrada")
    return dados


# ---------------------------------------------------------------------------
# planos de jogo (v1.2): escalações com nome; o padrão vem a cada rodada
# ---------------------------------------------------------------------------

def _posicionamento(p):
    """Posicionamento do corpo (Pydantic) → dict para os serviços."""
    return p.model_dump() if p is not None else None


def _resposta_planos(chamada):
    try:
        dados = chamada()
    except (TemporadaConcluida, PartidaEmAndamento) as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except (PlanoInvalido, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if dados is None:
        raise HTTPException(status_code=404, detail="Simulação ou plano não encontrado")
    return dados


@router.get("/simulacoes/{simulacao_id}/planos", response_model=Planos, tags=["planos"])
def listar_planos(simulacao_id: int):
    """Os planos de jogo, qual está carregado para a próxima partida e se a
    escalação foi mexida depois de carregar. Save sem plano ganha o
    "Titular", com a escalação atual."""
    return _resposta_planos(lambda: plano_service.listar(simulacao_id))


@router.post("/simulacoes/{simulacao_id}/planos", response_model=Planos,
             status_code=201, tags=["planos"])
def criar_plano(simulacao_id: int, plano: NovoPlano):
    """Plano novo (o que não vier sai da escalação atual). Ele passa a ser
    o carregado."""
    return _resposta_planos(lambda: plano_service.criar(
        simulacao_id, plano.nome, plano.formacao, plano.tatica, plano.xi, plano.padrao,
        _posicionamento(plano.posicionamento),
    ))


@router.patch("/simulacoes/{simulacao_id}/planos/{plano_id}", response_model=Planos,
              tags=["planos"])
def editar_plano(simulacao_id: int, plano_id: int, plano: PlanoEdicao):
    """Renomeia, muda o molde ou marca como padrão. Não mexe na escalação
    da próxima partida."""
    return _resposta_planos(lambda: plano_service.atualizar(
        simulacao_id, plano_id, plano.nome, plano.formacao, plano.tatica,
        plano.xi, plano.padrao, _posicionamento(plano.posicionamento),
    ))


@router.delete("/simulacoes/{simulacao_id}/planos/{plano_id}", response_model=Planos,
               tags=["planos"])
def apagar_plano(simulacao_id: int, plano_id: int):
    """Apaga um plano (não o último); se era o padrão, outro assume."""
    return _resposta_planos(lambda: plano_service.apagar(simulacao_id, plano_id))


@router.post("/simulacoes/{simulacao_id}/planos/{plano_id}/usar", response_model=Planos,
             tags=["planos"])
def usar_plano(simulacao_id: int, plano_id: int):
    """Carrega o plano na escalação da próxima partida (409 com a partida
    já rolando)."""
    return _resposta_planos(lambda: plano_service.usar(simulacao_id, plano_id))


# ---------------------------------------------------------------------------
# caixa de entrada (v1.3): mensagens dos setores do clube
# ---------------------------------------------------------------------------

def _caixa_ou_404(caixa, oque="Simulação não encontrada"):
    if caixa is None:
        raise HTTPException(status_code=404, detail=oque)
    return caixa


@router.get("/simulacoes/{simulacao_id}/mensagens", response_model=CaixaDeEntrada,
            tags=["caixa"])
def listar_mensagens(simulacao_id: int):
    """As mensagens do diretor de futebol, do departamento médico, do
    auxiliar técnico e da diretoria, da mais nova para a mais antiga."""
    return _caixa_ou_404(mensagem_service.listar(simulacao_id))


@router.post("/simulacoes/{simulacao_id}/mensagens/{mensagem_id}/lida",
             response_model=CaixaDeEntrada, tags=["caixa"])
def ler_mensagem(simulacao_id: int, mensagem_id: int):
    """Marca uma mensagem como lida."""
    return _caixa_ou_404(
        mensagem_service.ler(simulacao_id, mensagem_id), "Mensagem não encontrada"
    )


@router.post("/simulacoes/{simulacao_id}/mensagens/lidas",
             response_model=CaixaDeEntrada, tags=["caixa"])
def ler_todas_as_mensagens(simulacao_id: int):
    """Marca todas como lidas."""
    return _caixa_ou_404(mensagem_service.ler_todas(simulacao_id))
