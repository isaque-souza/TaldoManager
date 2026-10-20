-- Schema do Taldo Manager (SQLite).
-- Cada simulação é um "save" independente: os clubes e jogadores são um
-- snapshot daquela temporada, não referências ao catálogo da seed.

-- Modo carreira (v0.8): agrupa as temporadas (simulações) de um mesmo save.
-- Nasce sob demanda, quando uma temporada concluída é continuada.
CREATE TABLE IF NOT EXISTS carreira (
    id             INTEGER PRIMARY KEY,
    clube_usuario  TEXT NOT NULL,
    seed           INTEGER,           -- seed da temporada 1 (NULL = aleatória)
    criada_em      TEXT NOT NULL      -- ISO 8601 (UTC)
);

CREATE TABLE IF NOT EXISTS simulacao (
    id             INTEGER PRIMARY KEY,
    seed           INTEGER,           -- NULL quando a temporada foi aleatória
    criada_em      TEXT NOT NULL,     -- ISO 8601 (UTC)
    campeao        TEXT NOT NULL,     -- '' enquanto a temporada está em andamento
    rodadas        INTEGER NOT NULL,
    clube_usuario  TEXT,              -- clube "dirigido" pelo usuário (ou NULL)
    tatica         TEXT,              -- tática desse clube (ou NULL)
    formacao       TEXT,              -- formação desse clube (ou NULL)
    xi_preferido   TEXT,              -- JSON com os nomes do XI titular (ou NULL)
    estado         TEXT NOT NULL DEFAULT 'concluida',  -- 'em_andamento' | 'concluida'
    rodada_atual   INTEGER,           -- próxima rodada a jogar (só em andamento)
    estado_json    TEXT,              -- snapshot do estado vivo (só em andamento)
    -- carreira (v0.8): NULL = save avulso; temporada = 1, 2, 3...
    carreira_id    INTEGER REFERENCES carreira(id) ON DELETE SET NULL,
    temporada      INTEGER NOT NULL DEFAULT 1,
    -- autosave (v0.9): última vez que o save mudou (ISO 8601, UTC)
    atualizada_em  TEXT,
    -- diretoria (v1.0), fixadas no início da temporada (NULL sem clube
    -- dirigido ou em saves antigos): posição mínima cobrada e o ranking
    -- de força do clube que a definiu
    meta_posicao   INTEGER,
    ranking_forca  INTEGER
);

CREATE TABLE IF NOT EXISTS clube (
    id             INTEGER PRIMARY KEY,
    simulacao_id   INTEGER NOT NULL REFERENCES simulacao(id) ON DELETE CASCADE,
    nome           TEXT NOT NULL,
    pais           TEXT NOT NULL,
    posicao_final  INTEGER NOT NULL,
    pontos         INTEGER NOT NULL,
    jogos          INTEGER NOT NULL,
    vitorias       INTEGER NOT NULL,
    empates        INTEGER NOT NULL,
    derrotas       INTEGER NOT NULL,
    gols_marcados  INTEGER NOT NULL,
    gols_sofridos  INTEGER NOT NULL,
    -- finanças da temporada (v0.7); dinheiro = caixa atual / final
    dinheiro_inicial   INTEGER NOT NULL DEFAULT 0,
    dinheiro           INTEGER NOT NULL DEFAULT 0,
    receita_tv         INTEGER NOT NULL DEFAULT 0,
    receita_bilheteria INTEGER NOT NULL DEFAULT 0,
    receita_premiacao  INTEGER NOT NULL DEFAULT 0,
    despesa_salarios   INTEGER NOT NULL DEFAULT 0,
    receita_vendas     INTEGER NOT NULL DEFAULT 0,
    despesa_compras    INTEGER NOT NULL DEFAULT 0,
    historico_caixa    TEXT NOT NULL DEFAULT '[]',  -- JSON: caixa após cada rodada
    -- torcida (v1.4): atual / final e no início da temporada
    torcedores         INTEGER NOT NULL DEFAULT 0,
    torcedores_inicial INTEGER NOT NULL DEFAULT 0,
    despesa_marketing  INTEGER NOT NULL DEFAULT 0,  -- campanhas (v1.4)
    torcedores_base    INTEGER NOT NULL DEFAULT 0,  -- tamanho natural (v1.4)
    capacidade         INTEGER NOT NULL DEFAULT 0,  -- lugares no estádio (v1.5)
    ingresso           TEXT NOT NULL DEFAULT 'normal',  -- popular | normal | premium
    -- ampliação (v1.5): obra em andamento (0 = nenhuma) e lugares já feitos
    obra_lugares       INTEGER NOT NULL DEFAULT 0,
    obra_rodadas       INTEGER NOT NULL DEFAULT 0,   -- quantas faltam
    lugares_ampliados  INTEGER NOT NULL DEFAULT 0,
    despesa_estadio    INTEGER NOT NULL DEFAULT 0    -- obras + manutenção
);

CREATE TABLE IF NOT EXISTS jogador (
    id              INTEGER PRIMARY KEY,
    simulacao_id    INTEGER NOT NULL REFERENCES simulacao(id) ON DELETE CASCADE,
    clube_id        INTEGER NOT NULL REFERENCES clube(id) ON DELETE CASCADE,
    nome            TEXT NOT NULL,
    posicao         TEXT NOT NULL,
    idade           INTEGER NOT NULL,
    overall         INTEGER NOT NULL,
    partidas        INTEGER NOT NULL,
    gols            INTEGER NOT NULL,
    assistencias    INTEGER NOT NULL,
    nota_media      REAL NOT NULL,
    melhor_nota     REAL NOT NULL,
    pior_nota       REAL NOT NULL,
    melhor_em_campo INTEGER NOT NULL,
    clean_sheets    INTEGER NOT NULL,
    hat_tricks      INTEGER NOT NULL,
    amarelos        INTEGER NOT NULL,
    vermelhos       INTEGER NOT NULL,
    penaltis        INTEGER NOT NULL DEFAULT 0,
    penaltis_perdidos INTEGER NOT NULL DEFAULT 0,
    faltas          INTEGER NOT NULL DEFAULT 0,
    potencial       INTEGER NOT NULL DEFAULT 0,
    contrato_anos   INTEGER NOT NULL DEFAULT 0,
    valor_mercado   INTEGER NOT NULL DEFAULT 0,  -- snapshot do valor no fim do save
    salario         INTEGER NOT NULL DEFAULT 0,  -- por temporada
    multa_rescisoria INTEGER,                    -- NULL = sem multa
    numero          INTEGER,                     -- camisa (v1.1); NULL em saves antigos
    funcao          TEXT,                        -- posição específica (v1.3); NULL em saves antigos
    secundarias     TEXT,                        -- JSON: posições secundárias (v1.3)
    fama            INTEGER,                     -- v1.4; NULL em saves antigos
    temporadas_no_clube INTEGER,
    a_venda         INTEGER NOT NULL DEFAULT 0,  -- na lista de transferências (v1.7)
    papel           TEXT,                        -- papel no elenco (v1.7); só o clube do técnico
    humor           TEXT NOT NULL DEFAULT 'contente',
    titularidades   INTEGER NOT NULL DEFAULT 0,  -- jogos como titular (liga)
    jogos_disponivel INTEGER NOT NULL DEFAULT 0, -- jogos do clube em que podia jogar
    formador        TEXT,                        -- clube formador (v1.9); NULL em saves antigos
    clube_historia  TEXT,                        -- onde foi ídolo por último
    sonho           TEXT,                        -- clube do sonho (muda na virada)
    -- dispensado no meio da temporada (v1.7): está nos livres, mas a linha
    -- fica (lances e atuações apontam para ela); o clube_id é o do clube
    -- por onde jogou
    livre           INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS partida (
    id                     INTEGER PRIMARY KEY,
    simulacao_id           INTEGER NOT NULL REFERENCES simulacao(id) ON DELETE CASCADE,
    rodada                 INTEGER NOT NULL,
    mandante_id            INTEGER NOT NULL REFERENCES clube(id) ON DELETE CASCADE,
    visitante_id           INTEGER NOT NULL REFERENCES clube(id) ON DELETE CASCADE,
    gols_mandante          INTEGER NOT NULL,
    gols_visitante         INTEGER NOT NULL,
    posse_mandante         INTEGER NOT NULL,
    finalizacoes_mandante  INTEGER NOT NULL,
    finalizacoes_visitante INTEGER NOT NULL,
    finalizacoes_gol_mandante  INTEGER NOT NULL DEFAULT 0,
    finalizacoes_gol_visitante INTEGER NOT NULL DEFAULT 0,
    escanteios_mandante        INTEGER NOT NULL DEFAULT 0,
    escanteios_visitante       INTEGER NOT NULL DEFAULT 0,
    acrescimos                 INTEGER,  -- minutos de acréscimo (v1.1); NULL em saves antigos
    publico                    INTEGER   -- pagantes (v1.5); NULL em saves antigos
);

-- Transferências feitas numa temporada rodada a rodada (v0.7). Desde a
-- v1.7 também os livres contratados (sem clube de origem; valor = luvas) e
-- as dispensas (sem clube de destino; valor = rescisão), para o histórico.
CREATE TABLE IF NOT EXISTS transferencia (
    id            INTEGER PRIMARY KEY,
    simulacao_id  INTEGER NOT NULL REFERENCES simulacao(id) ON DELETE CASCADE,
    rodada        INTEGER NOT NULL,   -- feita antes desta rodada
    jogador_id    INTEGER NOT NULL REFERENCES jogador(id) ON DELETE CASCADE,
    de_clube_id   INTEGER REFERENCES clube(id) ON DELETE CASCADE,   -- NULL = livre
    para_clube_id INTEGER REFERENCES clube(id) ON DELETE CASCADE,   -- NULL = dispensado
    valor         INTEGER NOT NULL,
    tipo          TEXT NOT NULL DEFAULT 'transferencia'   -- transferencia | livre | dispensa | emprestimo
);

-- Propostas de compra feitas pelo técnico (v0.7): contam o limite por
-- janela e guardam o histórico da negociação.
CREATE TABLE IF NOT EXISTS proposta (
    id            INTEGER PRIMARY KEY,
    simulacao_id  INTEGER NOT NULL REFERENCES simulacao(id) ON DELETE CASCADE,
    rodada        INTEGER NOT NULL,
    jogador_id    INTEGER NOT NULL REFERENCES jogador(id) ON DELETE CASCADE,
    valor         INTEGER NOT NULL,
    resposta      TEXT NOT NULL,    -- aceita | multa | contraproposta | recusada
    valor_pedido  INTEGER           -- só nas contrapropostas
);

-- Negociações de contratação do técnico (v1.7): o acordo com o clube (etapa
-- 1, nas propostas) trava o valor; a etapa 2 é o contrato com o jogador.
-- Livres vão direto à etapa 2 (sem jogador_id nem clube; valor = luvas).
CREATE TABLE IF NOT EXISTS negociacao (
    id            INTEGER PRIMARY KEY,
    simulacao_id  INTEGER NOT NULL REFERENCES simulacao(id) ON DELETE CASCADE,
    rodada        INTEGER NOT NULL,   -- a janela (antes desta rodada)
    jogador_id    INTEGER REFERENCES jogador(id) ON DELETE CASCADE,
    jogador       TEXT NOT NULL,      -- nome (livres não têm id)
    clube         TEXT,               -- de onde vem; NULL = livre
    valor         INTEGER NOT NULL,   -- transferência acertada (ou luvas)
    status        TEXT NOT NULL,      -- aberta | fechada | desistiu | expirada
    tentativas    INTEGER NOT NULL DEFAULT 0,   -- propostas de contrato feitas
    contra_salario INTEGER,           -- última contraproposta do jogador
    contra_anos   INTEGER,
    contra_multa  TEXT,
    contra_papel  TEXT,
    -- opção de compra de um empréstimo (v1.7): o valor é o da cláusula e a
    -- etapa 2 não depende da janela
    emprestimo_id INTEGER REFERENCES emprestimo(id) ON DELETE CASCADE
);

-- Campanhas de marketing do técnico (v1.4): uma por turno.
CREATE TABLE IF NOT EXISTS campanha (
    id                 INTEGER PRIMARY KEY,
    simulacao_id       INTEGER NOT NULL REFERENCES simulacao(id) ON DELETE CASCADE,
    rodada             INTEGER NOT NULL,   -- próxima rodada a jogar quando foi feita
    tipo               TEXT NOT NULL,      -- redes | cidade | nacional
    custo              INTEGER NOT NULL,
    torcedores_antes   INTEGER NOT NULL,
    torcedores_depois  INTEGER NOT NULL
);

-- Propostas de renovação de contrato do técnico (v0.7).
CREATE TABLE IF NOT EXISTS renovacao (
    id            INTEGER PRIMARY KEY,
    simulacao_id  INTEGER NOT NULL REFERENCES simulacao(id) ON DELETE CASCADE,
    rodada        INTEGER NOT NULL,
    jogador_id    INTEGER NOT NULL REFERENCES jogador(id) ON DELETE CASCADE,
    salario       INTEGER NOT NULL,
    anos          INTEGER NOT NULL,
    multa         TEXT NOT NULL,     -- opção: sem | 2x | 3x | 5x
    resposta      TEXT NOT NULL,     -- aceita | contraproposta | recusada
    salario_pedido INTEGER,          -- só nas contrapropostas
    papel         TEXT               -- papel prometido (v1.7); NULL = o atual
);

-- Timeline da partida: um registro por evento (gol, cartão, substituição, ...).
CREATE TABLE IF NOT EXISTS lance (
    id          INTEGER PRIMARY KEY,
    partida_id  INTEGER NOT NULL REFERENCES partida(id) ON DELETE CASCADE,
    minuto      INTEGER NOT NULL,
    tipo        TEXT NOT NULL,          -- gol, penalti, penalti_perdido, chute_fora,
                                        -- cartao_amarelo, expulsao, substituicao
    clube_id    INTEGER REFERENCES clube(id) ON DELETE CASCADE,
    jogador_id  INTEGER REFERENCES jogador(id) ON DELETE SET NULL,
    detalhe     TEXT                    -- texto livre (ex.: "sai Fulano")
);

-- Atuação de um jogador numa partida: nota e contribuição, mais o snapshot
-- da escalação (titular / quando entrou / quando saiu).
CREATE TABLE IF NOT EXISTS atuacao (
    id           INTEGER PRIMARY KEY,
    partida_id   INTEGER NOT NULL REFERENCES partida(id) ON DELETE CASCADE,
    jogador_id   INTEGER NOT NULL REFERENCES jogador(id) ON DELETE CASCADE,
    clube_id     INTEGER NOT NULL REFERENCES clube(id) ON DELETE CASCADE,
    titular      INTEGER NOT NULL,      -- 0/1
    entrou_min   INTEGER,               -- NULL quando começou jogando
    saiu_min     INTEGER,               -- NULL quando terminou em campo
    gols         INTEGER NOT NULL,
    assistencias INTEGER NOT NULL,
    nota         REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_clube_simulacao   ON clube(simulacao_id);
CREATE INDEX IF NOT EXISTS ix_jogador_simulacao ON jogador(simulacao_id);
CREATE INDEX IF NOT EXISTS ix_jogador_clube     ON jogador(clube_id);
CREATE INDEX IF NOT EXISTS ix_partida_simulacao ON partida(simulacao_id);
CREATE INDEX IF NOT EXISTS ix_partida_mandante  ON partida(mandante_id);
CREATE INDEX IF NOT EXISTS ix_partida_visitante ON partida(visitante_id);
CREATE INDEX IF NOT EXISTS ix_lance_partida     ON lance(partida_id);
CREATE INDEX IF NOT EXISTS ix_atuacao_partida   ON atuacao(partida_id);
CREATE INDEX IF NOT EXISTS ix_atuacao_jogador   ON atuacao(jogador_id);

-- O que aconteceu na virada que abriu esta temporada (v0.8): aposentadorias,
-- saídas de graça, renovações automáticas... Guarda nomes, e não ids, porque
-- quem se aposentou não existe mais na tabela `jogador` da temporada nova.
CREATE TABLE IF NOT EXISTS movimento_virada (
    id            INTEGER PRIMARY KEY,
    simulacao_id  INTEGER NOT NULL REFERENCES simulacao(id) ON DELETE CASCADE,
    tipo          TEXT NOT NULL,   -- aposentou | adiou | saiu_livre | chegou_livre | renovou
    jogador       TEXT NOT NULL,
    clube         TEXT NOT NULL,
    posicao       TEXT NOT NULL,
    idade         INTEGER NOT NULL,
    overall       INTEGER NOT NULL,
    detalhe       TEXT NOT NULL DEFAULT ''
);

-- Planos de jogo (v1.2): escalações com nome que o técnico deixa salvas
-- (formação, tática e XI, na ordem dos slots). O padrão é carregado a cada
-- rodada nova; mexer antes do apito vale só para aquele jogo.
CREATE TABLE IF NOT EXISTS plano (
    id            INTEGER PRIMARY KEY,
    simulacao_id  INTEGER NOT NULL REFERENCES simulacao(id) ON DELETE CASCADE,
    nome          TEXT NOT NULL,
    formacao      TEXT NOT NULL,
    tatica        TEXT NOT NULL,
    xi            TEXT NOT NULL DEFAULT '[]',   -- JSON: nomes dos titulares
    padrao        INTEGER NOT NULL DEFAULT 0,
    posicionamento TEXT                         -- JSON {formacao, nomes} (v1.3)
);
CREATE INDEX IF NOT EXISTS ix_plano_simulacao ON plano(simulacao_id);

-- Caixa de entrada do técnico (v1.3): mensagens dos setores do clube
-- (diretor de futebol, departamento médico, auxiliar técnico, diretoria...).
CREATE TABLE IF NOT EXISTS mensagem (
    id            INTEGER PRIMARY KEY,
    simulacao_id  INTEGER NOT NULL REFERENCES simulacao(id) ON DELETE CASCADE,
    rodada        INTEGER,                      -- NULL = antes da 1ª rodada
    setor         TEXT NOT NULL,
    assunto       TEXT NOT NULL,
    corpo         TEXT NOT NULL,
    lida          INTEGER NOT NULL DEFAULT 0,
    criada_em     TEXT NOT NULL                 -- ISO 8601 (UTC)
);
CREATE INDEX IF NOT EXISTS ix_mensagem_simulacao ON mensagem(simulacao_id);

-- Ofertas da CPU pelos jogadores do técnico (v1.7): chegam quando a janela
-- abre (ou quando ele põe alguém na lista) e valem até a rodada ser jogada.
CREATE TABLE IF NOT EXISTS oferta_recebida (
    id            INTEGER PRIMARY KEY,
    simulacao_id  INTEGER NOT NULL REFERENCES simulacao(id) ON DELETE CASCADE,
    rodada        INTEGER NOT NULL,   -- a janela (antes desta rodada)
    jogador_id    INTEGER NOT NULL REFERENCES jogador(id) ON DELETE CASCADE,
    clube         TEXT NOT NULL,      -- quem oferece
    valor         INTEGER NOT NULL,
    teto          INTEGER NOT NULL,   -- até quanto aceita na contraproposta (escondido)
    espontanea    INTEGER NOT NULL DEFAULT 0,   -- assédio: ele não estava à venda
    status        TEXT NOT NULL DEFAULT 'aberta',
                  -- aberta | aceita | recusada | retirada | expirada
    pedido        INTEGER             -- a contraproposta do técnico, se houve
);
CREATE INDEX IF NOT EXISTS ix_oferta_simulacao ON oferta_recebida(simulacao_id);

-- Jogadores observados pelo técnico (v1.7), de qualquer clube ou livres:
-- vão pelo nome (livres não têm id e os ids mudam a cada temporada) e seguem
-- na virada. Guardam como ele estava quando entrou na lista.
CREATE TABLE IF NOT EXISTS observado (
    id            INTEGER PRIMARY KEY,
    simulacao_id  INTEGER NOT NULL REFERENCES simulacao(id) ON DELETE CASCADE,
    nome          TEXT NOT NULL,
    clube         TEXT,               -- onde estava; NULL = livre
    overall       INTEGER NOT NULL,
    valor         INTEGER NOT NULL,   -- valor de mercado
    temporada     INTEGER NOT NULL,   -- desde quando (temporada da carreira)
    rodada        INTEGER NOT NULL,
    UNIQUE (simulacao_id, nome)
);

-- Empréstimos (v1.7): quem recebe paga a taxa e uma parte do salário; o
-- jogador volta ao clube de origem antes da rodada `volta`. O estado vivo
-- fica no snapshot (`Jogador.emprestimo`); aqui, o registro de cada um.
CREATE TABLE IF NOT EXISTS emprestimo (
    id            INTEGER PRIMARY KEY,
    simulacao_id  INTEGER NOT NULL REFERENCES simulacao(id) ON DELETE CASCADE,
    rodada        INTEGER NOT NULL,   -- a janela em que foi feito
    jogador_id    INTEGER NOT NULL REFERENCES jogador(id) ON DELETE CASCADE,
    jogador       TEXT NOT NULL,
    de_clube      TEXT NOT NULL,
    para_clube    TEXT NOT NULL,
    duracao       TEXT NOT NULL,      -- turno | temporada
    volta         INTEGER NOT NULL,   -- volta antes desta rodada
    parte_salario INTEGER NOT NULL,   -- % que quem recebe paga
    taxa          INTEGER NOT NULL,
    opcao_compra  INTEGER,            -- preço fixo; NULL = sem opção
    comprado      INTEGER NOT NULL DEFAULT 0   -- a opção foi exercida
);
CREATE INDEX IF NOT EXISTS ix_emprestimo_simulacao ON emprestimo(simulacao_id);

-- Pedidos de empréstimo do técnico (v1.7): como as propostas de compra,
-- contam o limite por janela e guardam a última contraproposta.
CREATE TABLE IF NOT EXISTS pedido_emprestimo (
    id            INTEGER PRIMARY KEY,
    simulacao_id  INTEGER NOT NULL REFERENCES simulacao(id) ON DELETE CASCADE,
    rodada        INTEGER NOT NULL,
    jogador_id    INTEGER NOT NULL REFERENCES jogador(id) ON DELETE CASCADE,
    duracao       TEXT NOT NULL,
    parte_salario INTEGER NOT NULL,
    opcao         INTEGER NOT NULL DEFAULT 0,
    taxa          INTEGER NOT NULL,
    resposta      TEXT NOT NULL,      -- aceita | contraproposta | recusada
    taxa_pedida   INTEGER             -- só nas contrapropostas
);
