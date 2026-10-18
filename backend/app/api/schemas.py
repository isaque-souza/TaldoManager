"""Schemas Pydantic da API.

Servem para: (1) validar/serializar a resposta, (2) gerar a documentacao
automatica em /docs. Os campos batem com o dict devolvido por
`simular_temporada`.
"""

from typing import Literal

from pydantic import BaseModel, Field

Tatica = Literal["ofensivo", "equilibrado", "defensivo"]


class ClubeClassificacao(BaseModel):
    id: int | None = None        # presente só nas simulações salvas
    posicao: int
    clube: str
    pais: str
    pontos: int
    jogos: int
    vitorias: int
    empates: int
    derrotas: int
    gols_marcados: int
    gols_sofridos: int
    saldo_gols: int
    forma: list[str]


class JogadorStats(BaseModel):
    id: int | None = None        # presente só nas simulações salvas
    nome: str
    clube: str
    posicao: str
    overall: int
    idade: int
    partidas: int
    gols: int
    assistencias: int
    nota_media: float
    melhor_nota: float
    pior_nota: float
    melhor_em_campo: int
    hat_tricks: int
    clean_sheets: int
    amarelos: int
    vermelhos: int
    penaltis: int = 0
    penaltis_perdidos: int = 0
    faltas: int = 0
    potencial: int = 0
    contrato_anos: int = 0
    valor_mercado: int = 0
    salario: int = 0
    multa_rescisoria: int | None = None
    salario_referencia: int | None = None   # só no elenco da página do clube


class Recorde(BaseModel):
    valor: int
    partida: str


class EvolucaoSerie(BaseModel):
    clube: str
    id: int | None = None            # presente só nas simulações salvas
    pontos: list[int]                # acumulado ao fim de cada rodada


class Evolucao(BaseModel):
    rodadas: list[int]
    series: list[EvolucaoSerie]      # na ordem da classificação final


class FinancaClube(BaseModel):
    id: int | None = None
    posicao: int
    clube: str
    caixa_inicial: int
    caixa: int
    saldo: int
    receitas: int
    despesas: int
    folha: int                           # salários do elenco, por temporada


class MovimentoVirada(BaseModel):
    tipo: str        # aposentou | adiou | saiu_livre | chegou_livre | renovou
                     # | subiu_da_base
    jogador: str
    clube: str
    posicao: str
    idade: int
    overall: int
    detalhe: str = ""


class EvolucaoVirada(BaseModel):
    """Um jogador do técnico antes e depois da virada (None = veio da base)."""
    nome: str
    posicao: str
    idade: int
    overall_antes: int | None
    overall: int
    potencial_antes: int | None
    potencial: int
    clube_antes: str | None


class MetaDiretoria(BaseModel):
    """Meta da temporada (v1.0), fixada no início pelo ranking de força."""
    posicao: int             # posição mínima cobrada
    descricao: str           # "Terminar no G-4"
    ranking_forca: int       # o clube era o Nº elenco mais forte
    posicao_atual: int       # na tabela de agora (a final, se concluída)
    situacao: Literal["batida", "perto", "longe"]


class Cargo(BaseModel):
    """O cargo do técnico (v1.0): avaliado no fim de cada temporada."""
    estado: Literal["mantido", "ameacado", "demitido"]
    motivo: str | None = None


class FimDeCarreira(BaseModel):
    """Balanço do técnico demitido (temporadas concluídas da carreira)."""
    clube: str
    motivo: str
    temporadas: int
    titulos: int
    metas_batidas: int
    metas_avaliadas: int          # temporadas com meta (saves antigos não têm)
    melhor_posicao: int | None


class SimulacaoResponse(BaseModel):
    campeonato: str
    seed: int | None
    rodadas: int
    campeao: str | None
    estado: str = "concluida"           # 'em_andamento' | 'concluida'
    rodada_atual: int | None = None     # próxima rodada (só em andamento)
    # carreira (v0.8): None = save avulso
    carreira_id: int | None = None
    temporada: int = 1
    proxima_temporada_id: int | None = None   # já continuada → id da seguinte
    movimentos_virada: list[MovimentoVirada] = []   # o que a virada mudou
    evolucao_virada: list[EvolucaoVirada] = []      # seu elenco: subiu/caiu
    clube_usuario: str | None = None    # clube dirigido pelo usuário
    meta: MetaDiretoria | None = None   # None sem clube ou em save antigo
    cargo: Cargo | None = None          # None quando não há meta
    fim_de_carreira: FimDeCarreira | None = None   # só quando demitido
    tatica: Tatica | None = None
    formacao: str | None = None
    xi_preferido: list[str] | None = None
    classificacao: list[ClubeClassificacao]
    financas: list[FinancaClube] = []
    artilharia: list[JogadorStats]
    assistencias: list[JogadorStats]
    melhores_notas: list[JogadorStats]
    clean_sheets: list[JogadorStats]
    hat_tricks: list[JogadorStats]
    disciplina: list[JogadorStats] = []
    penaltis: list[JogadorStats] = []
    mvp: JogadorStats | None
    historico: list[str]
    recordes: dict[str, Recorde]
    evolucao: Evolucao


class HealthResponse(BaseModel):
    status: str


# --- simulações persistidas ---

class SimulacaoResumo(BaseModel):
    id: int
    seed: int | None
    criada_em: str
    campeao: str
    rodadas: int
    clube_usuario: str | None = None
    tatica: Tatica | None = None
    formacao: str | None = None
    estado: str = "concluida"           # 'em_andamento' | 'concluida'
    rodada_atual: int | None = None
    carreira_id: int | None = None
    temporada: int = 1
    atualizada_em: str | None = None   # última mudança (autosave, v0.9)
    fim_de_carreira: bool = False      # técnico demitido nesta temporada (v1.0)


class SimulacaoCriada(BaseModel):
    id: int


# --- carreira (v0.8) ---

class TemporadaCriada(BaseModel):
    simulacao_id: int
    carreira_id: int
    temporada: int


class DestaqueTemporada(BaseModel):
    """Artilheiro (valor = gols) ou MVP (valor = vezes melhor em campo)."""
    nome: str
    clube: str
    valor: int


class TemporadaDaCarreira(BaseModel):
    simulacao_id: int
    temporada: int
    seed: int | None
    campeao: str | None
    vice: str | None = None
    artilheiro: DestaqueTemporada | None = None
    mvp: DestaqueTemporada | None = None
    posicao_usuario: int | None = None
    estado: str
    rodada_atual: int | None = None


class TituloClube(BaseModel):
    clube: str
    titulos: int
    temporadas: list[int]


class TotalCarreira(BaseModel):
    """Um jogador somado em todas as temporadas concluídas da carreira."""
    nome: str
    posicao: str
    clube: str
    temporadas: int
    partidas: int
    gols: int
    assistencias: int
    titulos: int
    artilharias: int
    mvps: int
    pico_overall: int


class LideresCarreira(BaseModel):
    gols: list[TotalCarreira]
    assistencias: list[TotalCarreira]
    partidas: list[TotalCarreira]
    premios: list[TotalCarreira]


class Lenda(TotalCarreira):
    """Um aposentado no Hall da Fama."""
    idade: int
    ultima_temporada: int
    pontos: int
    motivo: str


class CarreiraDetalhe(BaseModel):
    id: int
    clube_usuario: str
    seed: int | None
    criada_em: str
    temporadas: list[TemporadaDaCarreira]
    titulos: list[TituloClube]
    lideres: LideresCarreira
    hall_da_fama: list[Lenda]


class NovaSimulacao(BaseModel):
    """Corpo do POST /simulacoes. Tudo opcional — sem `clube`, roda uma
    temporada neutra. `modo="rodada_a_rodada"` cria um save em andamento
    (exige `clube`); avança com POST /simulacoes/{id}/rodadas."""
    seed: int | None = None
    clube: str | None = None
    tatica: Tatica = "equilibrado"
    formacao: str | None = None
    xi: list[str] | None = None        # nomes do XI titular preferido
    modo: Literal["completa", "rodada_a_rodada"] = "completa"


class Posicionamento(BaseModel):
    """Onde o técnico pôs cada titular (v1.3): `nomes[i]` joga na vaga i do
    desenho da `formacao` (o goleiro é a 0; null = vaga livre). Só vale
    enquanto o time joga nessa formação."""
    formacao: str
    nomes: list[str | None]


class RodadaDecisao(BaseModel):
    """Corpo do POST /simulacoes/{id}/rodadas — o que o técnico muda antes da
    próxima rodada. Tudo opcional: o que não vier fica como está. `xi: []`
    põe todos os slots no automático (limpa o XI preferido)."""
    tatica: Tatica | None = None
    formacao: str | None = None
    xi: list[str] | None = None
    posicionamento: Posicionamento | None = None


class DecisaoSalva(BaseModel):
    """Resposta do PATCH /simulacoes/{id}/decisao — a escalação que ficou
    gravada para a próxima rodada."""
    tatica: Tatica
    formacao: str
    xi_preferido: list[str] | None
    atualizada_em: str


class ConfrontoRodada(BaseModel):
    mandante: str
    visitante: str


class ElencoSituacao(BaseModel):
    nome: str
    posicao: str
    funcao: str | None = None          # v1.3: posição específica
    secundarias: list[str] = []
    overall: int
    energia: int
    condicao: str
    suspenso: bool = False
    jogos_suspensao: int = 0
    amarelos_ciclo: int = 0
    lesionado: bool = False
    rodadas_lesao: int = 0


class ProximaRodada(BaseModel):
    concluida: bool
    rodada: int | None
    total_rodadas: int
    clube_usuario: str | None
    adversario: str | None
    mando: str | None
    tatica: Tatica | None
    formacao: str | None
    xi_preferido: list[str] | None
    formacoes: list[str]
    confrontos: list[ConfrontoRodada]
    elenco: list[ElencoSituacao]
    transmissao_ativa: bool = False   # v1.2: a partida já começou
    escalacao: "EscalacaoPreJogo | None" = None   # v1.2: como o motor vai escalar


class ResultadoRodada(BaseModel):
    partida_id: int
    mandante: str
    visitante: str
    gols_mandante: int
    gols_visitante: int


class JogadorPreJogo(BaseModel):
    nome: str
    numero: int | None
    posicao: str
    overall: int
    energia: int
    condicao: str                 # "Normal" | "Cansado" | "Exausto"
    pendurado: bool               # mais um amarelo e está suspenso
    craque: bool                  # overall 88+
    linha: int | None = None      # titular: 0 goleiro, 1 defesa, 2 meio, 3 ataque
    # v1.3: posição específica, onde está escalado e quanto rende ali
    funcao: str | None = None
    secundarias: list[str] = []
    vaga: str | None = None
    overall_vaga: int | None = None
    overall_por_posicao: dict[str, int] = {}
    # titular: lugar no desenho da formação (x largura, y profundidade, 0–100)
    x: float | None = None
    y: float | None = None
    rotulo: str | None = None          # LE, ZAG, VOL, MC, PD...
    slot: int | None = None            # a vaga no desenho (índice)


class EscalacaoPreJogo(BaseModel):
    clube: str
    formacao: str
    tatica: Tatica
    titulares: list[JogadorPreJogo]
    banco: list[JogadorPreJogo]


class PreJogo(BaseModel):
    """GET /simulacoes/{id}/pre-jogo (v1.1)."""
    rodada: int
    total_rodadas: int
    clube_usuario: str
    adversario: str | None        # None = folga nesta rodada
    mando: Literal["casa", "fora"] | None
    mandante: EscalacaoPreJogo | None
    visitante: EscalacaoPreJogo | None


class GolAoVivo(BaseModel):
    minuto: int
    clube: str


class PartidaAoVivo(BaseModel):
    partida_id: int
    mandante: str
    visitante: str
    gols_mandante: int
    gols_visitante: int
    acrescimos: int | None          # None em partidas de antes da v1.1
    gols: list[GolAoVivo]           # em ordem de minuto


class RodadaAoVivo(BaseModel):
    """GET /simulacoes/{id}/rodadas/{rodada}/ao-vivo (v1.1)."""
    rodada: int
    partidas: list[PartidaAoVivo]


class RodadaJogada(SimulacaoResponse):
    rodada_jogada: int
    concluida: bool
    resultados: list[ResultadoRodada]


class Identidade(BaseModel):
    """Visual do clube (v1.1): o frontend desenha escudo e camisa em SVG."""
    cor_primaria: str        # "#C8102E"
    cor_secundaria: str
    camisa: Literal["lisa", "listras", "aros", "faixa", "metade"]
    escudo: Literal["classico", "redondo", "moderno"]
    sigla: str               # 3 letras, vai no escudo


class ClubeSeed(BaseModel):
    nome: str
    pais: str
    forca: float            # média de overall do melhor XI no 4-3-3
    ranking_forca: int      # 1 = elenco mais forte da liga
    meta_posicao: int       # a meta que a diretoria daria
    meta: str               # descrição dela ("Terminar no G-4")
    dinheiro: int
    torcedores: int
    identidade: Identidade


class ElencoJogador(BaseModel):
    nome: str
    posicao: str
    overall: int


class ClubeComElenco(BaseModel):
    nome: str
    pais: str
    formacoes: list[str]
    elenco: list[ElencoJogador]


class ClubeInfo(BaseModel):
    id: int
    nome: str
    pais: str
    posicao_final: int
    pontos: int
    jogos: int
    vitorias: int
    empates: int
    derrotas: int
    gols_marcados: int
    gols_sofridos: int
    saldo_gols: int
    # finanças (v0.7); saves antigos vêm zerados
    dinheiro_inicial: int = 0
    dinheiro: int = 0
    receita_tv: int = 0
    receita_bilheteria: int = 0
    receita_premiacao: int = 0
    despesa_salarios: int = 0
    receita_vendas: int = 0
    despesa_compras: int = 0
    historico_caixa: list[int] = []      # caixa após cada rodada


class JogoResumo(BaseModel):
    partida_id: int
    rodada: int
    adversario: str
    mando: str
    gols_pro: int
    gols_contra: int
    resultado: str


class ClubeDetalhe(BaseModel):
    clube: ClubeInfo
    elenco: list[JogadorStats]
    jogos: list[JogoResumo]


# --- detalhe de partida (fase 2b) ---

class LanceOut(BaseModel):
    minuto: int
    tipo: str
    jogador: str | None = None
    jogador_id: int | None = None
    clube: str | None = None
    detalhe: str | None = None


class AtuacaoOut(BaseModel):
    jogador_id: int
    jogador: str
    posicao: str
    titular: bool
    entrou_min: int | None = None
    saiu_min: int | None = None
    gols: int
    assistencias: int
    nota: float


class LadoPartida(BaseModel):
    id: int
    nome: str


class PartidaInfo(BaseModel):
    id: int
    rodada: int
    mandante: LadoPartida
    visitante: LadoPartida
    gols_mandante: int
    gols_visitante: int
    posse_mandante: int
    posse_visitante: int
    finalizacoes_mandante: int
    finalizacoes_visitante: int
    finalizacoes_gol_mandante: int = 0
    finalizacoes_gol_visitante: int = 0
    escanteios_mandante: int = 0
    escanteios_visitante: int = 0
    acrescimos: int | None = None   # v1.1; None em partidas antigas


class PartidaDetalhe(BaseModel):
    partida: PartidaInfo
    eventos: list[LanceOut]
    escalacao_mandante: list[AtuacaoOut]
    escalacao_visitante: list[AtuacaoOut]


# --- game log de jogador (fase 2b) ---

class JogoLog(BaseModel):
    partida_id: int
    rodada: int
    adversario: str
    mando: str
    gols_pro: int
    gols_contra: int
    resultado: str
    titular: bool
    entrou_min: int | None = None
    saiu_min: int | None = None
    gols: int
    assistencias: int
    nota: float


class JogadorInfo(BaseModel):
    id: int
    nome: str
    clube: str
    clube_id: int
    posicao: str
    overall: int
    idade: int
    partidas: int
    gols: int
    assistencias: int
    nota_media: float
    melhor_nota: float
    pior_nota: float
    melhor_em_campo: int
    amarelos: int = 0
    vermelhos: int = 0
    penaltis: int = 0
    penaltis_perdidos: int = 0
    faltas: int = 0
    potencial: int = 0
    contrato_anos: int = 0
    valor_mercado: int = 0
    salario: int = 0
    multa_rescisoria: int | None = None


class JogadorDetalhe(BaseModel):
    jogador: JogadorInfo
    jogos: list[JogoLog]


# --- mercado de transferências (v0.7) ---

class FichaMercado(BaseModel):
    jogador_id: int
    nome: str
    clube: str
    posicao: str
    idade: int
    overall: int
    potencial: int
    valor_mercado: int
    salario: int
    contrato_anos: int
    multa_rescisoria: int | None = None
    salario_referencia: int = 0          # quanto o mercado paga a esse overall
    bloqueio: str | None = None          # por que não dá pra negociar (None = dá)
    # só nos jogadores de outros clubes
    rival: bool = False
    propostas_restantes: int | None = None
    contraproposta: int | None = None    # valor pedido na última contraproposta
    # só no próprio elenco
    ofertas: int | None = None


class TransferenciaFeita(BaseModel):
    rodada: int
    jogador_id: int
    jogador: str
    posicao: str
    de_clube: str
    para_clube: str
    valor: int


class Mercado(BaseModel):
    rodada: int
    janela_aberta: bool
    janelas: list[int]
    clube_usuario: str
    rivais: list[str]
    caixa: int
    elenco_min: int
    elenco_max: int
    max_propostas: int
    elenco: list[FichaMercado]
    disponiveis: list[FichaMercado]
    transferencias: list[TransferenciaFeita]


class TransferenciaResultado(BaseModel):
    rodada: int
    jogador_id: int
    jogador: str
    de_clube: str
    para_clube: str
    valor: int
    caixa: int


class NovaProposta(BaseModel):
    jogador_id: int
    valor: int


class RespostaProposta(BaseModel):
    resposta: Literal["aceita", "multa", "contraproposta", "recusada"]
    motivo: str
    valor_pedido: int | None = None      # só na contraproposta
    propostas_restantes: int
    transferencia: TransferenciaResultado | None = None


class OfertaClube(BaseModel):
    clube: str
    valor: int
    seria_titular: bool
    rival: bool


class OfertasJogador(BaseModel):
    jogador_id: int
    jogador: str
    valor_mercado: int
    bloqueio: str | None = None
    ofertas: list[OfertaClube]


class NovaVenda(BaseModel):
    jogador_id: int
    clube: str                           # o clube cuja oferta foi aceita


# --- renovação de contrato (v0.7) ---

OpcaoMulta = Literal["sem", "2x", "3x", "5x"]


class OpcaoMultaValor(BaseModel):
    opcao: OpcaoMulta
    valor: int | None                    # None = sem multa


class ContraContrato(BaseModel):
    salario: int
    anos: int
    multa: OpcaoMulta


class ContratoJogador(BaseModel):
    jogador_id: int
    jogador: str
    idade: int
    overall: int
    contrato_anos: int
    salario: int
    salario_referencia: int
    multa_rescisoria: int | None = None
    valor_mercado: int
    duracao_max: int
    opcoes_multa: list[OpcaoMultaValor]
    tentativas_restantes: int
    contraproposta: ContraContrato | None = None


class NovaRenovacao(BaseModel):
    jogador_id: int
    salario: int
    anos: int
    multa: OpcaoMulta


class ContratoNovo(BaseModel):
    contrato_anos: int
    salario: int
    multa_rescisoria: int | None = None


class RespostaRenovacao(BaseModel):
    resposta: Literal["aceita", "contraproposta", "recusada"]
    motivo: str
    salario_pedido: int | None = None    # só na contraproposta
    tentativas_restantes: int
    contrato: ContratoNovo | None = None


# ---------------------------------------------------------------------------
# simulação interativa (v1.2): a partida do técnico transmitida
# ---------------------------------------------------------------------------

class LanceMinuto(BaseModel):
    lado: Literal["mandante", "visitante"]   # quem atacou
    fim: Literal["cortado", "fora", "defesa", "gol", "penalti", "penalti_perdido"]


class MinutoTransmissao(BaseModel):
    """Um minuto do jogo; os números são acumulados até ele, [mandante, visitante]."""
    minuto: int
    lance: LanceMinuto | None      # None = minuto sem ataque
    placar: list[int]
    posse: list[int]
    finalizacoes: list[int]
    no_gol: list[int]
    escanteios: list[int]


class DecisaoAoVivo(BaseModel):
    minuto: int
    clube: str
    tatica: Tatica | None = None
    formacao: str | None = None
    sai: str | None = None
    entra: str | None = None


class OutroJogo(BaseModel):
    mandante: str
    visitante: str
    gols: list[GolAoVivo]


class Transmissao(BaseModel):
    """POST/GET /simulacoes/{id}/transmissao: a partida do técnico inteira,
    como sai com as decisões até aqui. Decisões novas só mudam do minuto
    delas em diante."""
    rodada: int
    clube_usuario: str
    mandante: EscalacaoPreJogo     # no apito inicial
    visitante: EscalacaoPreJogo
    acrescimos: int
    minutos: list[MinutoTransmissao]
    eventos: list[LanceOut]
    decisoes: list[DecisaoAoVivo]
    outros: list[OutroJogo]
    # v1.3: o desenho de cada formação, para redesenhar o time quando ela
    # muda no meio do jogo — {formação: [{funcao, x, y, rotulo}]}
    desenhos: dict[str, list[dict]] = {}


class DecisaoNova(BaseModel):
    """Corpo do POST /simulacoes/{id}/transmissao/decisoes: a tática nova, a
    formação nova OU uma substituição, valendo a partir de `minuto`."""
    minuto: int = Field(ge=1)
    tatica: Tatica | None = None
    formacao: str | None = None
    sai: str | None = None
    entra: str | None = None


class JogadorEmCampo(BaseModel):
    nome: str
    numero: int | None
    posicao: str
    funcao: str | None = None          # v1.3
    vaga: str | None = None            # posição em que está jogando
    overall_vaga: int | None = None    # o overall nela
    overall: int
    energia: int
    amarelos: int
    expulso: bool
    gols: int
    nota: float


class JogadorNoBanco(BaseModel):
    nome: str
    numero: int | None
    posicao: str
    funcao: str | None = None                # v1.3
    overall_por_posicao: dict[str, int] = {}
    overall: int
    energia: int
    disponivel: bool               # False = já jogou e saiu


class TimeNoMomento(BaseModel):
    clube: str
    tatica: Tatica
    formacao: str
    substituicoes_restantes: int
    em_campo: list[JogadorEmCampo]
    banco: list[JogadorNoBanco]


class MomentoPartida(BaseModel):
    """GET /simulacoes/{id}/transmissao/estado?minuto=N: os dois times ao
    fim do minuto N (o que o técnico vê ao pausar)."""
    minuto: int
    placar: list[int]
    clubes: list[TimeNoMomento]    # [mandante, visitante]


# ---------------------------------------------------------------------------
# planos de jogo (v1.2)
# ---------------------------------------------------------------------------

class Plano(BaseModel):
    id: int
    nome: str
    formacao: str
    tatica: Tatica
    xi: list[str]                  # titulares do molde (pode estar incompleto)
    padrao: bool                   # carregado a cada rodada nova
    posicionamento: Posicionamento | None = None   # v1.3


class Planos(BaseModel):
    """GET /simulacoes/{id}/planos (e a resposta de toda mudança neles)."""
    planos: list[Plano]
    em_uso: int | None             # plano carregado para a próxima partida
    modificado: bool               # a escalação da partida foi mexida depois


class NovoPlano(BaseModel):
    """Corpo do POST /simulacoes/{id}/planos. O que não vier sai da
    escalação atual da próxima partida."""
    nome: str
    formacao: str | None = None
    tatica: Tatica | None = None
    xi: list[str] | None = None
    padrao: bool = False
    posicionamento: Posicionamento | None = None


class PlanoEdicao(BaseModel):
    """Corpo do PATCH /simulacoes/{id}/planos/{plano_id}."""
    nome: str | None = None
    formacao: str | None = None
    tatica: Tatica | None = None
    xi: list[str] | None = None
    padrao: bool | None = None
    posicionamento: Posicionamento | None = None


ProximaRodada.model_rebuild()   # `escalacao` aponta para um schema definido depois
