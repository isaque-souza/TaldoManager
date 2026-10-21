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
    # fama (v1.4); None em saves antigos
    fama: int | None = None
    temporadas_no_clube: int | None = None
    idolo: bool = False


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
    torcedores: int = 0                  # torcida (v1.4); 0 em saves antigos
    torcedores_inicial: int = 0


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


class LigaResumo(BaseModel):
    id: str
    nome: str


class SimulacaoResponse(BaseModel):
    campeonato: str
    # v1.6: a liga mostrada (a do técnico, ou ?liga=) e as do save
    liga: str = "taldo"
    ligas: list[LigaResumo] = []
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
    # copa entre as ligas (v1.6): o campeão e até onde o técnico foi
    # ("campeao", a fase em que caiu, ou None se não entrou)
    campeao_copa: str | None = None
    copa_usuario: str | None = None
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
    copas: int = 0                       # copa entre as ligas (v1.6)
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
    titulos_copa: list[TituloClube] = []   # copa entre as ligas (v1.6)
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
    # ligas que rodam juntas (v1.6); sem dizer, todas
    ligas: list[Literal["taldo", "premier"]] | None = None


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
    liga: str = "taldo"                  # v1.6


class ElencoSituacao(BaseModel):
    nome: str
    posicao: str
    funcao: str | None = None          # v1.3: posição específica
    secundarias: list[str] = []
    atributos: dict[str, int] = {}     # v1.3: VEL, FIN, PAS... (ou REF, POS)
    overall: int
    energia: int
    condicao: str
    suspenso: bool = False
    jogos_suspensao: int = 0
    amarelos_ciclo: int = 0
    lesionado: bool = False
    rodadas_lesao: int = 0


class Calendario(BaseModel):
    """O dia do save (v2.0)."""
    temporada: str                         # "2026/27"
    data: str                              # ISO
    data_fmt: str                          # "sáb, 8 ago 2026"
    periodo: Literal["pre_temporada", "pausa", "temporada", "dia_de_jogo", "concluida"]
    rodada: int | None
    data_do_jogo: str | None
    dias_ate_o_jogo: int | None
    janela_aberta: bool


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
    calendario: Calendario | None = None   # v2.0


class ResultadoRodada(BaseModel):
    partida_id: int
    mandante: str
    visitante: str
    gols_mandante: int
    gols_visitante: int
    liga: str = "taldo"                  # v1.6


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
    atributos: dict[str, int] = {}     # v1.3
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


class GolCopa(BaseModel):
    minuto: int
    jogador: str | None
    clube: str | None
    tipo: str                            # gol | penalti


class JogoCopa(BaseModel):
    mandante: str
    visitante: str
    liga_mandante: str | None = None
    liga_visitante: str | None = None
    gols_mandante: int | None            # None = ainda não jogado
    gols_visitante: int | None
    penaltis: list[int] | None           # [mandante, visitante]
    vencedor: str | None
    publico: int | None
    gols: list[GolCopa]


class CopaDaRodada(BaseModel):
    fase: str
    nome: str
    jogos: list[JogoCopa]


class RodadaJogada(SimulacaoResponse):
    rodada_jogada: int
    concluida: bool
    resultados: list[ResultadoRodada]
    # a fase da copa jogada no meio da semana (v1.6), se teve
    copa: CopaDaRodada | None = None


class FaseCopa(BaseModel):
    fase: str
    nome: str
    depois_da_rodada: int
    premio: int                          # por vitória nesta fase
    jogos: list[JogoCopa]                # vazio = confrontos ainda não definidos
    jogada: bool


class ProximaFaseCopa(BaseModel):
    fase: str
    nome: str
    depois_da_rodada: int


class AdversarioCopa(BaseModel):
    adversario: str
    mando: Literal["casa", "fora"]


class SituacaoCopa(BaseModel):
    estado: Literal["fora", "vivo", "eliminado", "campeao"]
    fase: str | None
    jogo: AdversarioCopa | None


class CopaVisao(BaseModel):
    fases: list[FaseCopa]
    campeao: str | None
    proxima: ProximaFaseCopa | None
    seu_clube: SituacaoCopa


class Copa(BaseModel):
    copa: CopaVisao | None               # None = save sem copa (uma liga só)


class Identidade(BaseModel):
    """Visual do clube (v1.1): o frontend desenha escudo e camisa em SVG."""
    cor_primaria: str        # "#C8102E"
    cor_secundaria: str
    camisa: Literal["lisa", "listras", "aros", "faixa", "metade"]
    escudo: Literal["classico", "redondo", "moderno"]
    sigla: str               # 3 letras, vai no escudo


class ClubeSeed(BaseModel):
    nome: str
    liga: str = "taldo"     # v1.6
    pais: str
    forca: float            # média de overall do melhor XI no 4-3-3
    ranking_forca: int      # 1 = elenco mais forte da liga dele
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
    # torcida (v1.4); saves antigos vêm zerados
    torcedores: int = 0
    torcedores_inicial: int = 0
    despesa_marketing: int = 0
    despesa_estadio: int = 0             # obras e manutenção (v1.5)
    despesa_olheiros: int = 0            # salário do olheiro (v2.0)
    despesa_base: int = 0                # categorias de base (v2.0)


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
    publico: int | None = None      # pagantes (v1.5); None em partidas antigas


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
    funcao: str | None = None              # v1.3
    atributos: dict[str, int] = {}         # v1.3
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
    # estimativa do olheiro (v2.0): [mín, máx]; None = exato (o meio vai em potencial)
    potencial_faixa: list[int] | None = None
    contrato_anos: int = 0
    valor_mercado: int = 0
    salario: int = 0
    multa_rescisoria: int | None = None
    # fama (v1.4); None em saves antigos
    fama: int | None = None
    temporadas_no_clube: int | None = None
    idolo: bool = False
    # vontade (v1.9): nomes de clubes; None em saves antigos
    formador: str | None = None
    formador_pais: str | None = None
    clube_historia: str | None = None
    sonho: str | None = None
    sonho_encerrar: bool = False


class JogadorDetalhe(BaseModel):
    jogador: JogadorInfo
    jogos: list[JogoLog]


# --- mercado de transferências (v0.7) ---

class ContraContratoChegada(BaseModel):
    salario: int
    anos: int
    multa: str
    papel: str


class NegociacaoResumo(BaseModel):
    """Uma contratação em duas etapas (v1.7)."""
    negociacao_id: int
    jogador_id: int | None = None       # livres não têm
    jogador: str
    clube: str | None = None            # None = estava sem clube
    valor: int                          # transferência acertada (ou luvas)
    status: Literal["aberta", "fechada", "desistiu", "expirada", "perdida"]
    tentativas_restantes: int
    contraproposta: ContraContratoChegada | None = None
    opcao_compra: bool = False          # exercendo a opção de um empréstimo (v1.7)
    concorrente: "ConcorrenteResumo | None" = None   # disputa (v1.9)


class ConcorrenteResumo(BaseModel):
    """O clube da CPU que também quer o jogador (v1.9)."""
    clube: str
    salario_aproximado: int             # o técnico sabe "cerca de"


class NegociacaoDetalhe(NegociacaoResumo):
    idade: int | None = None
    overall: int | None = None
    funcao: str | None = None
    salario_atual: int | None = None    # None = livre
    salario_referencia: int | None = None
    salario_sugerido: int | None = None  # ponto de partida (sem os fatores escondidos)
    duracao_max: int | None = None
    opcoes_multa: list["OpcaoMultaValor"] = []
    papeis: list[str] = []
    papel_esperado: str | None = None
    interesse: "InteresseFicha | None" = None   # v1.9


class NovoContratoChegada(BaseModel):
    salario: int
    anos: int
    multa: str
    papel: str | None = None


class RespostaContrato(BaseModel):
    resposta: Literal["aceita", "contraproposta", "recusada"]
    motivo: str
    status: Literal["aberta", "fechada", "desistiu", "expirada"]
    salario_pedido: int | None = None
    tentativas_restantes: int
    transferencia: "TransferenciaResultado | None" = None
    contrato: "ContratoNovo | None" = None
    caixa: int


# --- empréstimos (v1.7) ---

DuracaoEmprestimo = Literal["turno", "temporada"]


class EmprestadoAqui(BaseModel):
    """O jogador está no elenco emprestado por outro clube (v1.7)."""
    emprestimo_id: int | None = None
    de_clube: str
    volta: int                           # volta antes desta rodada
    parte_salario: int                   # % do salário que pagamos
    opcao_compra: int | None = None      # preço fixo; None = sem opção


class DuracaoPossivel(BaseModel):
    duracao: DuracaoEmprestimo
    volta: int
    taxas: dict[str, int]                # taxa de partida por % do salário


class ContraEmprestimo(BaseModel):
    duracao: DuracaoEmprestimo
    parte_salario: int
    opcao: bool
    taxa: int


class PedidoEmprestimoFicha(BaseModel):
    """O que dá para pedir emprestado por um jogador de outro clube."""
    bloqueio: str | None = None
    duracoes: list[DuracaoPossivel] = []
    opcao_compra: int
    propostas_restantes: int
    contraproposta: ContraEmprestimo | None = None


class PropostaCessao(BaseModel):
    """Um clube da CPU que quer o jogador do técnico emprestado."""
    clube: str
    parte_salario: int                   # % do salário que ele banca
    taxa: int
    seria_titular: bool


class DuracaoCessao(BaseModel):
    duracao: DuracaoEmprestimo
    volta: int
    propostas: list[PropostaCessao]


class CessaoFicha(BaseModel):
    """Emprestar um jogador do técnico (v1.7): os interessados por duração."""
    bloqueio: str | None = None
    duracoes: list[DuracaoCessao] = []


class NovaCessao(BaseModel):
    jogador_id: int
    clube: str
    duracao: DuracaoEmprestimo


class Emprestimo(BaseModel):
    emprestimo_id: int
    rodada: int
    jogador_id: int
    jogador: str
    de_clube: str
    para_clube: str
    duracao: DuracaoEmprestimo
    volta: int
    parte_salario: int
    taxa: int
    opcao_compra: int | None = None
    status: Literal["ativo", "encerrado", "comprado"]


class NovoEmprestimo(BaseModel):
    jogador_id: int
    duracao: DuracaoEmprestimo
    parte_salario: int
    taxa: int
    opcao: bool = False


class RespostaEmprestimo(BaseModel):
    resposta: Literal["aceita", "contraproposta", "recusada"]
    motivo: str
    taxa_pedida: int | None = None       # só na contraproposta
    propostas_restantes: int
    emprestimo: Emprestimo | None = None
    caixa: int


class CessaoFeita(BaseModel):
    emprestimo: Emprestimo
    caixa: int


class OpcaoExercida(BaseModel):
    """A opção de compra trava o valor: falta o contrato com o jogador."""
    negociacao_id: int
    jogador: str
    clube: str
    valor: int


class InteresseFicha(BaseModel):
    """O quanto o jogador quer vir para o clube do técnico (v1.9)."""
    nivel: Literal["quer_vir", "aberto", "resistente", "nao_vem"]
    pontos: int
    motivos: list[str] = []
    bloqueio: str | None = None


class RelatorioFicha(BaseModel):
    """O relatório de contratação do olheiro (v2.0)."""
    status: Literal["andamento", "pronto"]
    pronto_em: str                         # ISO
    preco: list[int] | None = None         # [mín, máx] do preço pedido (ou das luvas)
    salario: list[int] | None = None       # [mín, máx] do salário que ele pede
    dificuldade: Literal["facil", "media", "dificil", "impossivel"] | None = None
    motivo: str | None = None
    chance_disputa: int | None = None      # % de outro clube entrar


class FichaMercado(BaseModel):
    jogador_id: int | None = None          # livres (v1.6) não têm id: vão pelo nome
    nome: str
    clube: str | None = None               # None = sem clube (v1.6)
    liga: str | None = None                # liga do clube (v1.7); None = livre
    posicao: str
    funcao: str | None = None              # v1.3
    atributos: dict[str, int] = {}         # v1.3
    idade: int
    overall: int
    potencial: int
    potencial_faixa: list[int] | None = None   # olheiro (v2.0)
    valor_mercado: int
    salario: int
    contrato_anos: int
    multa_rescisoria: int | None = None
    salario_referencia: int = 0          # quanto o mercado paga a esse overall
    fama: int = 0                        # v1.4
    idolo: bool = False
    a_venda: bool = False                # na lista de transferências (v1.7)
    sonho: str | None = None             # clube do sonho (v1.9)
    numero: int | None = None            # v1.7: a temporada até aqui
    partidas: int = 0
    gols: int = 0
    assistencias: int = 0
    nota_media: float = 0.0
    bloqueio: str | None = None          # por que não dá pra negociar (None = dá)
    # só nos jogadores de outros clubes
    rival: bool = False
    propostas_restantes: int | None = None
    contraproposta: int | None = None    # valor pedido na última contraproposta
    # só no próprio elenco
    ofertas: int | None = None
    rescisao: int | None = None          # quanto custa dispensar (v1.7)
    dispensa_bloqueada: str | None = None
    # papel no elenco (v1.7)
    papel: str | None = None
    humor: str | None = None
    titularidades: int = 0
    jogos_disponivel: int = 0
    meta_conta: str | None = None        # "titular" (começar) ou "jogou" (entrar)
    meta_fracao: float | None = None
    aproveitamento: float | None = None
    # só nos livres (v1.6): o bônus de assinatura, no lugar da transferência
    luvas: int | None = None
    negociacao: "NegociacaoResumo | None" = None   # v1.7: a desta janela
    observado: bool = False              # na lista de observados (v1.7)
    interesse: InteresseFicha | None = None   # só de outros clubes e livres (v1.9); sem relatório, escondido (v2.0)
    relatorio: RelatorioFicha | None = None   # do olheiro (v2.0)
    emprestimo: EmprestadoAqui | None = None        # v1.7: veio emprestado
    pedir_emprestado: PedidoEmprestimoFicha | None = None   # só de outros clubes
    emprestar: CessaoFicha | None = None    # só do elenco do técnico


class TransferenciaFeita(BaseModel):
    temporada: int = 1
    rodada: int
    # transferencia | livre (sem clube de origem; valor = luvas) |
    # dispensa (sem clube de destino; valor = rescisão) — v1.7
    tipo: str = "transferencia"
    jogador_id: int
    jogador: str
    posicao: str
    de_clube: str | None = None
    para_clube: str | None = None
    valor: int


class MovimentoTecnico(TransferenciaFeita):
    """Uma movimentação do clube dirigido (v1.7), do ponto de vista dele."""
    tipo: Literal["compra", "venda", "livre", "dispensa", "emprestimo", "cedido"]


class SaldoTransferencias(BaseModel):
    gasto: int                           # compras + luvas + rescisões
    arrecadado: int                      # vendas
    saldo: int


class SaldoTemporada(SaldoTransferencias):
    temporada: int


class HistoricoTransferencias(BaseModel):
    """O histórico do técnico na carreira inteira (v1.7)."""
    clube_usuario: str | None = None
    temporada_atual: int
    movimentos: list[MovimentoTecnico]
    temporadas: list[SaldoTemporada]
    total: SaldoTransferencias


class Observado(BaseModel):
    """Um jogador na lista de observados (v1.7)."""
    nome: str
    situacao: Literal["clube", "livre", "no_elenco", "aposentado"]
    desde_temporada: int
    desde_rodada: int
    clube_inicial: str | None = None     # onde estava ao entrar; None = livre
    overall_inicial: int
    valor_inicial: int
    avisos: list[str] = []
    jogador: FichaMercado | None = None  # None = aposentou


class Observados(BaseModel):
    limite: int
    observados: list[Observado]


class NovoObservado(BaseModel):
    nome: str
    observar: bool = True


class ObservadoMarcado(BaseModel):
    nome: str
    observado: bool
    total: int
    limite: int


class OfertaRecebida(BaseModel):
    """Uma oferta da CPU por um jogador do técnico (v1.7)."""
    oferta_id: int
    jogador_id: int
    jogador: str
    clube: str
    valor: int
    status: Literal["aberta", "aceita", "recusada", "retirada", "expirada"]
    espontanea: bool = False             # assédio: ele não estava à venda
    sonho: bool = False                  # é o clube do sonho dele (v1.9)
    pedido: int | None = None            # a contraproposta do técnico
    rival: bool = False
    # só enquanto está aberta
    seria_titular: bool | None = None
    valor_mercado: int | None = None
    revolta_torcida: float | None = None   # % da torcida que vai embora (v1.4)


# --- olheiro (v2.0) ----------------------------------------------------------

class NivelOlheiro(BaseModel):
    nivel: int
    faixa: int                      # ± no potencial
    custo_temporada: int
    custo_agora: int                # o que a troca custa hoje (descer: 0)
    bloqueio: str | None = None


class Olheiro(BaseModel):
    nivel: int
    caixa: int
    gasto_temporada: int
    niveis: list[NivelOlheiro]
    # relatórios de contratação (v2.0); só no GET /mercado
    relatorios_em_andamento: int | None = None
    relatorios_limite: int | None = None
    relatorio_dias: int | None = None


class NovoRelatorio(BaseModel):
    nome: str


class RelatorioPedido(BaseModel):
    nome: str
    pronto_em: str


class NovoNivelOlheiro(BaseModel):
    nivel: int


class Mercado(BaseModel):
    rodada: int
    janela_aberta: bool
    janelas: list[int]
    clube_usuario: str
    liga_usuario: str | None = None        # v1.7
    rivais: list[str]
    caixa: int
    elenco_min: int
    elenco_max: int
    max_propostas: int
    elenco: list[FichaMercado]
    disponiveis: list[FichaMercado]
    livres: list[FichaMercado] = []        # sem clube (v1.6)
    negociacoes: list[NegociacaoResumo] = []   # desta janela (v1.7)
    ofertas_recebidas: list[OfertaRecebida] = []   # da CPU, nesta janela (v1.7)
    transferencias: list[TransferenciaFeita]
    emprestimos: list[Emprestimo] = []     # da temporada (v1.7)
    partes_salario: list[int] = []
    olheiro: Olheiro | None = None         # v2.0


class NovaListaTransferencia(BaseModel):
    a_venda: bool


class ListaTransferencia(BaseModel):
    jogador_id: int
    jogador: str
    a_venda: bool
    ofertas: int = 0                     # as que chegaram na hora (v1.7)


class NovoPapel(BaseModel):
    papel: str


class PapelDefinido(BaseModel):
    jogador_id: int
    jogador: str
    papel: str
    humor: str


class Dispensa(BaseModel):
    rodada: int
    jogador_id: int
    jogador: str
    rescisao: int
    caixa: int


class NovaContratacaoLivre(BaseModel):
    nome: str


class ContratacaoLivre(BaseModel):
    """O livre topou conversar (v1.7): a negociação vai direto ao contrato."""
    negociacao_id: int
    jogador: str
    clube: str | None = None
    valor: int                           # as luvas


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
    # v1.7: o aceite do clube abre a negociação (a etapa 2 é o contrato)
    negociacao_id: int | None = None


class OfertasJogador(BaseModel):
    jogador_id: int
    jogador: str
    valor_mercado: int
    idolo: bool = False                  # v1.4: vender ídolo revolta a torcida
    a_venda: bool = False
    bloqueio: str | None = None
    ofertas: list[OfertaRecebida]


class NovaContrapropostaOferta(BaseModel):
    valor: int = Field(gt=0)


class OfertaRecusada(BaseModel):
    oferta_id: int
    jogador: str
    clube: str
    status: Literal["recusada"]


class RespostaContrapropostaOferta(BaseModel):
    """O clube aceitou o pedido (a venda fechou) ou retirou a oferta."""
    resposta: Literal["aceita", "retirada"]
    transferencia: TransferenciaResultado | None = None
    caixa: int


# --- renovação de contrato (v0.7) ---

OpcaoMulta = Literal["sem", "2x", "3x", "5x"]


class OpcaoMultaValor(BaseModel):
    opcao: OpcaoMulta
    valor: int | None                    # None = sem multa


class ContraContrato(BaseModel):
    salario: int
    anos: int
    multa: OpcaoMulta
    papel: str | None = None             # v1.7


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
    papel: str | None = None             # papel no elenco (v1.7)
    humor: str | None = None
    papeis: list[str] = []               # os que cabem nele (promessa só até 21)


class NovaRenovacao(BaseModel):
    jogador_id: int
    salario: int
    anos: int
    multa: OpcaoMulta
    papel: str | None = None             # v1.7; None = o atual


class ContratoNovo(BaseModel):
    contrato_anos: int
    salario: int
    multa_rescisoria: int | None = None
    papel: str | None = None             # v1.7


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
    posicoes: list[str] | None = None   # troca de posição (v1.7)


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


class MudancaNaPausa(BaseModel):
    """Uma coisa só: a tática, a formação, uma substituição (`sai` e
    `entra`) ou dois em campo trocando de vaga (`posicoes`, v1.7)."""
    tatica: Tatica | None = None
    formacao: str | None = None
    sai: str | None = None
    entra: str | None = None
    posicoes: list[str] | None = None


class DecisaoNova(MudancaNaPausa):
    """Corpo do POST /simulacoes/{id}/transmissao/decisoes: uma mudança a
    mais, valendo a partir de `minuto`."""
    minuto: int = Field(ge=1)


class PausaNova(BaseModel):
    """Corpo do PUT /simulacoes/{id}/transmissao/pausa (v1.7): todas as
    mudanças da pausa, na ordem; trocam as já marcadas para `minuto` (vazia
    desfaz todas)."""
    minuto: int = Field(ge=1)
    mudancas: list[MudancaNaPausa] = []


class JogadorEmCampo(BaseModel):
    nome: str
    numero: int | None
    posicao: str
    funcao: str | None = None          # v1.3
    vaga: str | None = None            # posição em que está jogando
    slot: int | None = None            # a vaga no desenho da formação (v1.7)
    overall_vaga: int | None = None    # o overall nela
    overall_por_posicao: dict[str, int] = {}   # para trocar de posição (v1.7)
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


class Mensagem(BaseModel):
    id: int
    rodada: int | None           # None = antes da 1ª rodada
    setor: str                   # Diretor de futebol, Departamento médico...
    assunto: str
    corpo: str
    lida: bool
    criada_em: str
    data: str | None = None      # o dia no calendário (v2.0), ISO


class CaixaDeEntrada(BaseModel):
    """GET /simulacoes/{id}/mensagens (v1.3)."""
    mensagens: list[Mensagem]
    nao_lidas: int
    setores: list[str]


ProximaRodada.model_rebuild()   # `escalacao` aponta para um schema definido depois
NegociacaoResumo.model_rebuild()   # `concorrente` (v1.9)
NegociacaoDetalhe.model_rebuild()   # `interesse` (v1.9) também


# ---------------------------------------------------------------------------
# marketing (v1.4)
# ---------------------------------------------------------------------------

class CampanhaOpcao(BaseModel):
    tipo: str
    nome: str
    descricao: str
    ganho_pct: float
    torcedores_novos: int
    custo: int
    bloqueio: str | None = None


class CampanhaFeita(BaseModel):
    rodada: int
    nome: str
    custo: int
    torcedores_novos: int


class Marketing(BaseModel):
    torcedores: int
    torcedores_inicial: int
    mando_de_campo: float        # pontos de força num jogo comum em casa (pelo público, v1.5)
    caixa: int
    turno: int
    disponivel: bool             # ainda dá para fazer uma campanha neste turno
    campanhas: list[CampanhaOpcao]
    feitas: list[CampanhaFeita]


class NovaCampanha(BaseModel):
    tipo: str


# --- estádio (v1.5) ---

class FaixaIngresso(BaseModel):
    faixa: str                   # popular | normal | premium
    nome: str
    descricao: str
    preco: float                 # ingresso nesta faixa
    publico: int                 # estimativa para um jogo comum em casa
    ocupacao: float              # % da capacidade
    bilheteria: int              # estimativa por jogo
    mando_de_campo: float        # força em casa com esse público


class EstadioTemporada(BaseModel):
    jogos_em_casa: int
    publico_medio: int
    ocupacao_media: float        # %
    lotados: int
    bilheteria: int              # arrecadada na temporada


class ObraEstadio(BaseModel):
    tipo: str                    # pequena | media | grande
    nome: str
    descricao: str
    lugares: int
    rodadas: int                 # prazo
    custo: int                   # à vista
    manutencao: int              # dos lugares novos, por jogo em casa
    bloqueio: str | None         # por que não dá para começar agora


class ObraEmAndamento(BaseModel):
    tipo: str
    nome: str
    lugares: int
    rodadas: int                 # prazo total
    faltam: int


class Estadio(BaseModel):
    capacidade: int
    ingresso: str
    torcedores: int
    caixa: int
    faixas: list[FaixaIngresso]
    temporada: EstadioTemporada
    obras: list[ObraEstadio]
    obra: ObraEmAndamento | None
    lugares_ampliados: int
    manutencao: int              # por jogo em casa, hoje


class NovaObra(BaseModel):
    tipo: str


class NovoIngresso(BaseModel):
    faixa: str


# ---------------------------------------------------------------------------
# categorias de base do técnico (v2.0)
# ---------------------------------------------------------------------------

class NivelBase(BaseModel):
    nivel: int
    ritmo: float                 # 1 = cresce como um jovem titular
    margem_max: int              # até quanto o potencial passa do overall
    custo_temporada: int
    custo_agora: int
    bloqueio: str | None = None


class JovemBase(BaseModel):
    id: int
    nome: str
    idade: int
    funcao: str
    posicao: str
    overall: int
    progresso: float             # fração até o próximo ponto de overall
    potencial: int
    chegou_em: str
    ultimo_ano: bool             # faz 20 na virada: promova ou ele vai embora


class PeneiraBase(BaseModel):
    data: str
    data_fmt: str
    feita: bool


class ElencoBase(BaseModel):
    jogadores: int
    maximo: int


class Base(BaseModel):
    nivel: int
    caixa: int
    gasto_temporada: int
    niveis: list[NivelBase]
    vagas: int
    idade_limite: int
    peneira: PeneiraBase
    elenco: ElencoBase
    bloqueio_promocao: str | None = None
    jovens: list[JovemBase]


class NovoNivelBase(BaseModel):
    nivel: int


class Promovido(BaseModel):
    jogador: str
    base: Base
