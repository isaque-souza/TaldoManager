# Mapa do banco atual (SQLite)

Auditoria de 2026-11-18, `main` em 8ec9dd0 (v2.6 + #131). Somente leitura:
o mapa foi tirado de um banco vazio criado no scratchpad (`init_db`), nunca do
banco real.

## Onde fica e como nasce

| Item | Onde |
|---|---|
| Arquivo | `backend/data/database/taldo_manager.db` (padrão); `TALDO_DB` sobrescreve (testes e a VPS) |
| Conexão | `app/db/conexao.py` — `conectar()` liga `foreign_keys` e usa `timeout=15` (vários técnicos ao mesmo tempo) |
| Schema | `app/db/schema.sql`, só `CREATE ... IF NOT EXISTS` |
| Migrações | `conexao._migrar()`, roda a cada `init_db()` (na subida do app) |
| ORM | nenhum: SQL puro nos `app/repositories/*_repository.py` |

### Sistema de migrações (como é hoje)

1. `schema.sql` cria o que falta (idempotente).
2. `_COLUNAS_NOVAS`: lista de colunas por tabela; cada uma que não existe vira
   `ALTER TABLE ... ADD COLUMN` (o SQLite não tem `ADD COLUMN IF NOT EXISTS`).
   Os comentários registram a versão do jogo em que cada coluna entrou.
3. `_refazer_transferencia`: o único caso de recriar tabela (v1.7), pela
   receita do SQLite (FKs desligadas, copiar, apagar a antiga).
4. Migrações de **dados** com `UPDATE` idempotente (ex.: `copa_pendente`) e,
   para a troca de nomes da v2.5.1, `PRAGMA user_version` (= 1 hoje):
   `_renomear_jogadores` troca o nome antigo pelo novo em **todo texto do
   banco**, inclusive dentro dos JSONs.

O que isso significa para o plano:

- Migrações são **aditivas e idempotentes**, mas **não têm volta** (não existe
  "down"). Reverter = restaurar backup. Recomendo manter assim e exigir backup
  antes de cada deploy com migração, em vez de construir um sistema de
  rollback.
- Não existe tabela de versão de migrações; `user_version` é o único
  marcador e já está em uso.

## As tabelas (25)

Todas as tabelas de jogo pendem de `simulacao` (um **save** = uma temporada)
com `ON DELETE CASCADE`. Não há catálogo global de clubes/jogadores no banco.

### Contas
| Tabela | Papel |
|---|---|
| `usuario` | login (nome, senha_hash) — v2.1 |
| `sessao` | token_hash → usuario, com expiração |

### Save e carreira
| Tabela | Papel |
|---|---|
| `carreira` | agrupa as temporadas de um save (clube do técnico, seed da 1ª) |
| `simulacao` | **a temporada** (27 colunas; 28 com `mundo` na v2.7): seed, estado (`em_andamento`/`concluida`), `rodada_atual`, `data_atual`, `ligas` (JSON), `economia` (versão das regras de dinheiro), `mundo` (versão das seeds, ver [MUNDOS.md](MUNDOS.md)), dono (`usuario_id`), e os blobs de estado (abaixo) |

Blobs JSON em `simulacao` — o estado vivo **não** está nas tabelas:

| Coluna | Conteúdo |
|---|---|
| `estado_json` | snapshot da temporada em andamento (clubes, elencos, stats acumuladas, energia, contratos, RNG). ~0,86 MB num save de 2 ligas; regravado a cada rodada/dia |
| `ao_vivo_json` | decisões da partida transmitida em curso |
| `livres_json` | jogadores sem clube no fim da temporada (para a virada) |
| `copa_json` | as copas (v2.6) |
| `xi_preferido`, `ligas` | listas de nomes / ids de liga |

### O mundo do save (snapshot ao concluir)
| Tabela | Papel |
|---|---|
| `clube` (37 col.) | clube **daquele save**: nome, país, liga, tabela final, finanças, torcida, estádio, olheiro, base |
| `jogador` (40 col.) | jogador **daquele save**: nome, posição/função/secundárias, idade, overall, potencial, stats, contrato, salário, valor, fama, papel, humor, vontade |

Índices: `ix_jogador_simulacao_nome (simulacao_id, nome)` — o nome é a chave
de fato do jogador dentro do save (ver riscos).

### Partidas
| Tabela | Papel |
|---|---|
| `partida` | placar, posse, finalizações, escanteios, acréscimos, público |
| `lance` | eventos por minuto (gol, pênalti, cartão, lesão, substituição...) |
| `atuacao` | jogador × partida: titular, entrada/saída, gols, assistências, nota |

### Mercado
| Tabela | Papel |
|---|---|
| `transferencia` | compras, vendas, livres, dispensas, empréstimos (`tipo`) |
| `proposta`, `negociacao`, `renovacao` | o vai e vem de propostas e contratos |
| `oferta_recebida` | ofertas de outros clubes pelos jogadores do técnico |
| `emprestimo`, `pedido_emprestimo` | v1.7 |
| `observado`, `relatorio` | lista de observação e relatórios do olheiro |
| `movimento_virada` | o que mudou na virada (aposentadorias, saídas, chegadas) |

### Clube do técnico
| Tabela | Papel |
|---|---|
| `plano` | planos de jogo (formação, tática, XI por **nome**, posicionamento) |
| `mensagem` | caixa de entrada |
| `campanha` | marketing |
| `jovem_base`, `missao_base`, `indicado_base` | categorias de base e olheiros da base |

## Relacionamentos que importam para dados reais

```
usuario 1─* simulacao *─1 carreira
simulacao 1─* clube 1─* jogador
simulacao 1─* partida ─* lance / atuacao ─> jogador, clube
simulacao 1─* transferencia / proposta / negociacao / ... ─> jogador (id) ou nome
```

- Jogador → clube: `jogador.clube_id` (FK), só no snapshot concluído. No
  estado vivo, o elenco é a lista `elenco` (nomes) de cada clube no
  `estado_json`.
- Várias tabelas guardam o jogador **pelo nome** em texto (`negociacao.jogador`,
  `emprestimo.jogador`, `observado.nome`, `movimento_virada.jogador`,
  `plano.xi`, `simulacao.xi_preferido`, `mensagem.corpo`). A migração da
  v2.5.1 teve de varrer o banco inteiro por isso.
- Não há id externo em lugar nenhum.

## O que fica **fora** do banco (lido das seeds a cada pedido)

`scripts/data_loader.py` relê os JSON de `backend/data/seeds/<liga>/` toda vez
que um save em andamento é carregado e aplica o `estado_json` por cima
(`temporada.restaurar_estado`), casando **clube e jogador pelo nome**. Vêm
sempre da seed, mesmo em save antigo:

- o calendário (regerado com a semente guardada);
- a `identidade` do clube (cores, escudo, camisa — só visual);
- os `rivais` (`rivais_do_seed`, também no pós-jogo);
- `posicao_2023_24` (cabeça de chave da copa);
- de cada jogador, o que não está em `_JOGADOR_CAMPOS` (ex.: `posicao`,
  `funcao`, `secundarias`), salvo quem já foi recriado do snapshot;
- a lista de ligas: na virada, `divisoes.do_save_na_virada` acrescenta ao save
  as ligas novas que existirem nas seeds.

Ou seja: **as seeds são, na prática, parte do estado de todo save vivo.**

## Volume

| Medida | Valor |
|---|---|
| Seeds (8 ligas + livres) | 1,5 MB, ~3.900 jogadores no mundo |
| Fontes brutas (`data/fontes`) | 368 KB (OpenFootball, Wikipédia, estrelas) |
| Banco local (cópia) | 2,0 MB, 1 save de 2 ligas (local está parado; o jogo de verdade roda na VPS) |
| `estado_json` | ~0,86 MB com 2 ligas; estimado ~3,5 MB com 8 e ~6 MB com 14 |
