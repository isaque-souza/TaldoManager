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
    historico_caixa    TEXT NOT NULL DEFAULT '[]'   -- JSON: caixa após cada rodada
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
    secundarias     TEXT                         -- JSON: posições secundárias (v1.3)
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
    acrescimos                 INTEGER   -- minutos de acréscimo (v1.1); NULL em saves antigos
);

-- Transferências feitas numa temporada rodada a rodada (v0.7).
CREATE TABLE IF NOT EXISTS transferencia (
    id            INTEGER PRIMARY KEY,
    simulacao_id  INTEGER NOT NULL REFERENCES simulacao(id) ON DELETE CASCADE,
    rodada        INTEGER NOT NULL,   -- feita antes desta rodada
    jogador_id    INTEGER NOT NULL REFERENCES jogador(id) ON DELETE CASCADE,
    de_clube_id   INTEGER NOT NULL REFERENCES clube(id) ON DELETE CASCADE,
    para_clube_id INTEGER NOT NULL REFERENCES clube(id) ON DELETE CASCADE,
    valor         INTEGER NOT NULL
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
    salario_pedido INTEGER           -- só nas contrapropostas
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
