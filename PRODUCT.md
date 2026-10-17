# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users
O autor do projeto e amigos, jogando como técnico de um clube de futebol
fictício. Jogam tanto no computador quanto no celular — as duas telas
precisam ficar boas de verdade, não só "não quebrar".

## Product Purpose
Taldo Manager é um jogo de gerenciamento de futebol no navegador: você
assume um clube da liga Taldo (20 clubes fictícios), monta a escalação,
negocia no mercado, renova contratos e joga a temporada rodada a rodada,
temporada após temporada, sob a cobrança de uma meta da diretoria — longe
dela, é demissão e fim de carreira. Nasceu como projeto de estudo e está
sendo finalizado para parecer um jogo de verdade.

## Positioning
Um manager enxuto e honesto: um motor de partida próprio (fadiga, cartões,
lesões, pênaltis), economia e mercado com negociação, carreira com
envelhecimento, base e Hall da Fama — tudo rodando local, sem conta, sem
anúncio, sem microtransação.

## Operating Context
- Sessões de jogo: menu → escolher clube ou continuar → tela da rodada
  (escalação, mercado, contratos, finanças) → jogar → resultados → repetir.
- O jogador consulta muito número: classificação, rankings, elenco com
  overall/energia/situação, finanças. Ao mesmo tempo quer momentos de
  espetáculo (pré-jogo, gol, fim de temporada).
- Equilíbrio pedido: "um pouco dos dois" entre Football Manager (dados
  densos) e FIFA/EA FC (visual, cards grandes).

## Capabilities and Constraints
- Stack: FastAPI + SQLite no backend; frontend HTML + CSS + JS puro em
  módulos ES, sem build, servido pela própria API (`uvicorn app.main:app`).
  Pico.css 2 por baixo.
- Google Fonts liberado (sem internet, cai numa fonte do sistema).
- Clubes e jogadores são fictícios; cada clube tem identidade visual na
  seed (cores, escudo, padrão de camisa, sigla) desenhada em SVG no front.
- Jogadores ainda não têm número de camisa nem foto.
- Idioma: português do Brasil.

## Brand Commitments
- Nome: Taldo Manager. Liga: Taldo.
- Clima visual escolhido pelo usuário: "estádio noturno" — escuro,
  gramado, luz de refletor, placar eletrônico; referências que ele citou:
  Football Manager e FIFA/EA FC.
- Escudos e camisas gerados por código (SVG), não imagens desenhadas.

## Evidence on Hand
- 20 clubes e 360 jogadores na seed (`backend/data/seeds/`), com
  identidade visual por clube.
- Não há fotos de jogadores, logos reais, estádios reais nem patrocínios —
  e não devem ser inventados como se fossem reais.

## Product Principles
1. Parecer um jogo, não um painel administrativo.
2. Informação densa quando decide algo (escalação, mercado); espetáculo nos
   momentos (pré-jogo, gol, virada de temporada).
3. Celular e computador com o mesmo cuidado.
4. Tudo que é visual vem de dados (cores do clube, estado do jogador), não
   de enfeite solto.
