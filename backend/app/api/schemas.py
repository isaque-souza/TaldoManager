"""Schemas Pydantic da API.

Servem para: (1) validar/serializar a resposta, (2) gerar a documentacao
automatica em /docs. Os campos batem com o dict devolvido por
`simular_temporada`.
"""

from typing import Literal

from pydantic import BaseModel

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


class SimulacaoResponse(BaseModel):
    campeonato: str
    seed: int | None
    rodadas: int
    campeao: str | None
    estado: str = "concluida"           # 'em_andamento' | 'concluida'
    rodada_atual: int | None = None     # próxima rodada (só em andamento)
    clube_usuario: str | None = None    # clube dirigido pelo usuário
    tatica: Tatica | None = None
    formacao: str | None = None
    xi_preferido: list[str] | None = None
    classificacao: list[ClubeClassificacao]
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


class SimulacaoCriada(BaseModel):
    id: int


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


class RodadaDecisao(BaseModel):
    """Corpo do POST /simulacoes/{id}/rodadas — o que o técnico muda antes da
    próxima rodada. Tudo opcional: o que não vier fica como está."""
    tatica: Tatica | None = None
    formacao: str | None = None
    xi: list[str] | None = None


class ConfrontoRodada(BaseModel):
    mandante: str
    visitante: str


class ElencoSituacao(BaseModel):
    nome: str
    posicao: str
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


class ResultadoRodada(BaseModel):
    partida_id: int
    mandante: str
    visitante: str
    gols_mandante: int
    gols_visitante: int


class RodadaJogada(SimulacaoResponse):
    rodada_jogada: int
    concluida: bool
    resultados: list[ResultadoRodada]


class ClubeSeed(BaseModel):
    nome: str
    pais: str


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


class JogadorDetalhe(BaseModel):
    jogador: JogadorInfo
    jogos: list[JogoLog]
