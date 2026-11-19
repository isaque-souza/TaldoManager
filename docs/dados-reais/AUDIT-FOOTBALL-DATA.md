# Auditoria — integração com dados reais (Etapa 1)

Data: 2026-11-18. Base: `main` em 8ec9dd0 (v2.6 + favicon #131).
Escopo: só leitura. Nenhum código, banco ou seed foi alterado.

Documentos irmãos:
- [CURRENT-DATABASE-MAP.md](CURRENT-DATABASE-MAP.md) — tabelas, migrações, o que mora fora do banco
- [CURRENT-SIMULATION-MAP.md](CURRENT-SIMULATION-MAP.md) — motor, rodada, virada, desempenho
- [FOOTBALL-DATA-IMPLEMENTATION-PLAN.md](FOOTBALL-DATA-IMPLEMENTATION-PLAN.md) — a proposta adaptada

## 1. Resumo em cinco linhas

1. O TaldoManager **já tem um pipeline de dados reais**, só que offline e sem
   API: `scripts/baixar_*` → `data/fontes/` → `scripts/importar_*` (determinístico)
   → `data/seeds/<liga>/` → `data_loader` → save.
2. **Cada save já é uma cópia própria do mundo** (`clube`/`jogador` com
   `simulacao_id`). A "proteção das carreiras" do plano está meio feita, com uma
   brecha séria: o save em andamento relê as seeds a cada pedido.
3. O jogador é identificado **pelo nome**, em colunas e dentro de JSONs. Não
   existe id estável nem id externo.
4. O motor **não usa atributos externos**: usa `overall` + setor + função +
   secundárias; os 6 atributos são derivados. A API-Football também não
   fornece atributos — então o encaixe é natural, mas o `overall` continuará
   sendo **estimado pelo jogo**.
5. O repositório é **público** e o site na VPS é **público, com contas**. Isso
   pesa em licenças (dados brutos da API, fotos, escudos).

## 2. Estrutura real × estrutura-alvo do plano

| Plano | O que existe | Recomendação |
|---|---|---|
| `app/services/football_data/` chamando a API | Nada em runtime; importação é por scripts em `backend/scripts/` | Manter a API **fora do runtime**: um pacote em `backend/scripts/football_data/`. O jogo nunca chama a API → "API fora do ar não impede jogar" fica garantido por construção, e a chave nunca vai para a VPS |
| Tabelas de "dados de origem" no SQLite | Seeds JSON versionadas no Git são o catálogo; o banco só guarda saves | Cache bruto da API em disco (`data/fontes/api-football/`, **fora do Git**); a saída normalizada continua sendo seed JSON. Não mexer no banco do jogo para isso |
| `migrations/` | `conexao._migrar()` aditiva/idempotente + `user_version` | Continuar nesse sistema. Sem "down": rollback = backup |
| `seeds/` na raiz | `backend/data/seeds/<liga>/{clubes,jogadores,livres}.json` | Manter; acrescentar **versão do mundo** (ver Plano, Fase 2) |
| `tests/unit|integration|regression|fixtures` | `tests/{domain,services,api,db,repositories}` + `conftest` com banco temporário | Seguir as pastas atuais; fixtures da API em `tests/fixtures/api_football/` |
| Repositórios `player/club/competition_repository` | `jogador_repository`, `clube_repository` (por save) | Não criar repositórios de catálogo: o catálogo é arquivo |
| Snapshots por carreira (Sprint 5) | Já existem (save = cópia) | Trabalho real é **fixar a versão das seeds por save**, não criar snapshots |

## 3. Respostas aos 10 itens da auditoria

1. **Estrutura**: `backend/app/{api,core,db,domain,repositories,services}`,
   `backend/scripts`, `backend/data/{seeds,fontes,database}`, `backend/tests`,
   `frontend/` (JS puro em módulos), `deploy/`, `Dockerfile`.
2. **Entradas**: `app/main.py` (FastAPI + site), `scripts/simular.py` (CLI),
   scripts de geração/importação de seeds, `scripts/dar_saves.py` (manutenção).
3. **Domínio**: `Jogador`, `Clube`, `Campeonato`, `Partida` + módulos de regra
   (atributos, posições, evolução, mercado, contrato, finanças, copa,
   divisões, torcida, estádio, base, vontade...). Ver mapa do motor.
4. **Tabelas**: 25 — ver mapa do banco.
5. **Migrações**: `schema.sql` + `_COLUNAS_NOVAS` + uma recriação de tabela +
   `user_version` para migração de dados. Rodam na subida do app.
6. **Seeds**: 8 ligas. Taldo e Taldo B fictícias; Premier 23/24 real
   (OpenFootball, CC0); Brasileirão 2017 real (Wikipédia, escolha deliberada:
   o hepta do Corinthians); La Liga, Segunda, Championship, Série B 2017 com
   clubes reais e jogadores fictícios. Clubes → jogadores por id **da seed**;
   o id da seed não vai para o save.
7. **Fluxo da partida**: ver mapa do motor (Partida minuto a minuto, notas,
   MVP, estatísticas, snapshot).
8. **Jogador ↔ clube**: `jogador.clube_id` no snapshot concluído; lista de
   nomes `elenco` no `estado_json` durante a temporada.
9. **Campeonatos**: um `Campeonato` com todas as ligas do save, cada liga com
   tabela/calendário; Séries A/B; copas; virada com acesso/rebaixamento.
10. **Testes**: 957 funções em 75 arquivos, banco temporário por teste,
    ~12 min. Baseline desta auditoria no fim do documento.

## 4. Riscos (do mais grave ao menos)

### R1 — Trocar seeds quebra ou altera saves em andamento (ALTO)
O save vivo é "seed atual + `estado_json` por cima", casado por nome
(`temporada.restaurar_estado`). Se uma seed muda:
- clube novo ou renomeado na seed → `blob["clubes"][clube.nome]` dá
  `KeyError` (temporada.py:152) e o save em andamento não abre;
- clube removido da seed → some do save no meio da temporada;
- jogador com nome trocado → o save o recria do snapshot, mas `posicao`,
  `funcao`, `secundarias` passam a vir de outra fonte;
- calendário, rivais, identidade e cabeças de chave mudam no meio da temporada;
- na virada, `do_save_na_virada` puxa ligas novas para carreiras antigas.

**Mitigação obrigatória antes de importar qualquer coisa**: versionar o mundo
(seeds congeladas por versão) e gravar no save qual versão ele usa. Saves
existentes ficam presos à versão atual. É a Fase 2 do plano.

### R2 — Nome como identidade do jogador (ALTO)
Nomes repetidos são comuns no futebol real ("Rodrigo", "Danilo", "Pedro").
Hoje os importadores garantem nomes únicos no mundo inteiro (ganham
sobrenome) e a v2.5.1 precisou de uma migração que varre **todo texto do
banco** para trocar nomes. Com ~7.000 jogadores reais e sincronizações, isso
vira rotina.
**Mitigação**: (a) toda seed nova ganha um `ref` estável (`apif:<id>`) ao
lado do nome; (b) o importador continua garantindo nome único por versão do
mundo; (c) trocar a chave interna de nome para `ref` fica como trabalho
futuro e separado — é refatoração grande (estado_json, planos, mensagens).

### R3 — Licenças e repositório público (ALTO, não técnico)
- **Dados da API**: os termos da API-Football não puderam ser lidos nesta
  auditoria (a página devolveu 403). Até verificar, tratar respostas brutas
  como **não redistribuíveis**: cache fora do Git (`.gitignore`). Gerar seeds
  normalizadas no Git a partir delas também precisa de confirmação nos termos.
- **Fotos e escudos**: a própria API diz não ser dona dos direitos. Escudos são
  marcas registradas dos clubes; fotos têm direitos de fotógrafos/agências.
  Num site público, recomendo **não** usar até haver licença. O jogo já tem
  identidade visual própria por clube (`identidade`: cores, escudo
  desenhado, sigla).
- **Nomes reais de jogadores** num site público: já é o caso hoje (Premier,
  Brasileirão). Risco existente, não novo — mas cresce com o escopo.

### R4 — Desempenho com 14 ligas + continentais (MÉDIO)
8 ligas: ~0,75 s por rodada e `estado_json` de alguns MB regravado a cada dia.
14 ligas: ~7.000 jogadores. Os gargalos crescem com o tamanho do mundo. Medir
antes de adotar; talvez as ligas "sem o técnico" precisem de simulação mais
barata. A VPS é pequena e atende vários técnicos.

### R5 — `overall` continua sendo estimativa (MÉDIO, de produto)
A API-Football dá perfil (nome, nascimento, nacionalidade, posição, camisa,
foto) e estatísticas por temporada (minutos, gols, nota média "rating"). Não
dá Velocidade 95 nem overall. O jogo vai continuar estimando — a diferença é
que as estatísticas reais (minutos, rating) podem melhorar a estimativa de
hoje (força do clube + camisa + idade + estrelas à mão). A posição da API é só
o setor (G/D/M/A): a função (zagueiro, lateral, ponta...) também será
estimada.

### R6 — Limites da API (MÉDIO)
Plano grátis: 100 requisições/dia (confirmado) e um teto por minuto (fontes
divergem: 10 a 30). Não foi possível confirmar **quais temporadas** o plano
grátis cobre — verificar com `/leagues/seasons` antes de começar. Conta
aproximada: elenco atual (`/players/squads?team=`) = 1 requisição por clube →
14 ligas ≈ 300 clubes ≈ 3 dias no grátis; estatísticas (`/players?league&season`,
20 por página) ≈ +500. Um mês de plano pago (Pro, ~US$ 19 segundo o guia
oficial) faz tudo num dia.

### R7 — Competições continentais reais (MÉDIO, escopo)
Champions/Europa/Conference reais exigem clubes de ligas que não estão no jogo
(Portugal, Holanda, Turquia...) e o formato de liga de 36. A copa entre ligas
da v2.6 já cobre "clubes de várias ligas se enfrentando". Recomendo tratar como
fase própria, depois das ligas.

### R8 — Conflito com decisões de produto já tomadas (BAIXO, mas decidir)
- Brasileirão **2017** foi escolha explícita (Corinthians). A API traria o
  atual. Recomendo manter 2017 e não importar o Brasil da API.
- Liga Taldo / Taldo B são a identidade do jogo: continuam fictícias.
- La Liga, Segunda, Championship e Série B 2017 têm jogadores fictícios hoje;
  a importação os trocaria por reais (só em mundos novos — R1).

### R9 — Migrações sem volta e backup (BAIXO com processo)
`ADD COLUMN` não se desfaz no sistema atual. Antes de cada deploy com migração:
cópia do banco na própria VPS (`cp` com data) — não é backup externo, só um
ponto de retorno.

## 5. O que **não** precisa mudar

- O motor (`app/domain/partida.py`) — nenhum ponto exige alteração; a
  integração entra pelos dados de entrada.
- O banco do jogo para guardar dados de origem — o catálogo segue em arquivo.
- A API do jogo — os endpoints atuais continuam; dados novos (nacionalidade,
  por exemplo) entram como campos opcionais.
- Os saves antigos — com a Fase 2, nunca mais leem uma seed diferente da que
  usaram para nascer.

## 6. Decisões que preciso de você

> **Respondidas em 2026-11-18** — as cinco aprovadas como recomendado, mais
> dois requisitos (identidade do jogador e versionamento imutável). Ver o
> topo do [plano](FOOTBALL-DATA-IMPLEMENTATION-PLAN.md).

1. **Licença/escopo visual**: seguir sem fotos e escudos da API (recomendado)
   até haver licença?
2. **Plano da API**: começar no grátis (piloto Premier: ~25 requisições) e só
   pagar um mês quando for importar as 14 ligas?
3. **Brasil**: manter o Brasileirão 2017 (recomendado) ou trocar pelo atual?
4. **Carreiras antigas**: ficam no mundo em que nasceram, sem receber as ligas
   novas na virada (recomendado), ou continuam "crescendo" como na v2.5?
5. **Ordem**: confirmar piloto só com a Premier atual antes de expandir.

## 7. Baseline de testes

`main` em 8ec9dd0, 2026-11-18, Windows, 12 núcleos:

```
python -m pytest -q -p no:cacheprovider -n auto     (pytest-xdist 3.8.0)
994 passed in 188.13s (0:03:08)
```

994 testes coletados (957 funções + parametrizações), **todos passando**,
nenhum pulado. Em série a suíte leva ~12 min; com `-n auto` (cada teste já usa
banco temporário próprio, então paraleliza sem ajuste), ~3 min. Toda fase do
plano compara com este número.
