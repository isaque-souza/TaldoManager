---
name: Taldo Manager
description: O jogo como a transmissão de um jogo de futebol à noite.
colors:
  noite: "#070b10"
  superficie: "#0f1620"
  superficie-2: "#152030"
  linha: "#22324a"
  texto: "#eef3f7"
  texto-2: "#9fb2c4"
  gramado: "#14834b"
  gramado-claro: "#22b46a"
  gramado-escuro: "#0b5a33"
  refletor: "#f4c430"
  ao-vivo: "#e63946"
  ambar: "#f0a52a"
  branco: "#ffffff"
  gramado-listra-a: "#17683b"
  gramado-listra-b: "#1b7543"
  campo-borda: "#0d3d24"
  cartao-amarelo: "#f7d117"
typography:
  tarja:
    fontFamily: "Barlow Condensed, Arial Narrow, system-ui, sans-serif"
    fontWeight: 800
    letterSpacing: "0.01em"
  display:
    fontFamily: "Barlow Condensed, Arial Narrow, system-ui, sans-serif"
    fontSize: "clamp(2rem, 5vw, 3.4rem)"
    fontWeight: 800
    lineHeight: 0.98
  titulo-tela:
    fontFamily: "Barlow Condensed, Arial Narrow, system-ui, sans-serif"
    fontSize: "clamp(1.6rem, 3.2vw, 2.1rem)"
    fontWeight: 800
  rotulo:
    fontFamily: "Barlow Condensed, Arial Narrow, system-ui, sans-serif"
    fontSize: "0.82rem"
    fontWeight: 700
    letterSpacing: "0.08em"
  body:
    fontFamily: "Barlow, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
rounded:
  chip: "2px"
  base: "4px"
  card: "6px"
spacing:
  gutter: "clamp(1rem, 3vw, 2rem)"
  grid: "0.8rem"
components:
  button-primary:
    backgroundColor: "{colors.gramado}"
    textColor: "{colors.texto}"
    typography: "{typography.rotulo}"
    rounded: "{rounded.base}"
  button-secondary:
    backgroundColor: "{colors.superficie-2}"
    textColor: "{colors.texto-2}"
    rounded: "{rounded.base}"
  tarja-clube:
    backgroundColor: "{colors.gramado}"
    textColor: "{colors.texto}"
    typography: "{typography.titulo-tela}"
  chip-batida:
    backgroundColor: "{colors.gramado}"
    textColor: "{colors.texto}"
    rounded: "{rounded.chip}"
  chip-perto:
    backgroundColor: "{colors.ambar}"
    textColor: "#1b1300"
    rounded: "{rounded.chip}"
  chip-longe:
    backgroundColor: "{colors.ao-vivo}"
    textColor: "{colors.texto}"
    rounded: "{rounded.chip}"
  card-clube:
    backgroundColor: "{colors.superficie}"
    textColor: "{colors.texto}"
    rounded: "{rounded.card}"
---

# Design System: Taldo Manager

## Overview

O jogo inteiro se apresenta como a **transmissão de um jogo à noite**: fundo de
estádio escuro com a luz fria do refletor vindo do alto, tarjas de TV em
verde-gramado com letras brancas condensadas, placar em caixa branca. É uma
interface de uso (montar escalação, ler tabela, negociar): a transmissão
empresta tipografia, paleta, densidade e um gesto marcante — **a tarja de
placar** — e nunca troca navegação nem controles conhecidos.

Fontes do sistema: tokens em `frontend/style.css` (bloco "Tema transmissão
noturna", que sobrescreve as variáveis do Pico.css 2); identidade dos clubes
em SVG em `frontend/js/identidade.js`; ícones em `frontend/js/icones.js`.

## Colors

- **Noite** (`noite`, `superficie`, `superficie-2`, `linha`): o chão e as camadas.
  O fundo do `body` soma um brilho frio no topo (refletor) e um verde fraco no
  rodapé (gramado), fixos na rolagem.
- **Gramado** (`gramado`, `-claro`, `-escuro`): a cor da emissora — tarjas,
  botão principal, aba ativa, seleção de texto.
- **Refletor** (`refletor`, dourado): só para "você" (sua linha na tabela,
  posição no ranking) e o anel de foco. Nunca decoração.
- **Ao vivo** (`ao-vivo`, vermelho): só para estado ruim/urgente — derrota,
  "longe da meta", demissão, ao vivo.
- **Âmbar**: alerta intermediário (em risco, pendurado, contrato acabando).
- **Campo** (`gramado-listra-a/b`, `campo-borda`): o gramado listrado do
  pré-jogo, com linhas brancas a 50%; `cartao-amarelo` só no sinal de
  pendurado. `branco` é o texto sobre as tarjas e a caixa do placar.
- Cores dos clubes vêm da seed (`identidade`) e só aparecem nos escudos e
  camisas, nunca no cromo da interface.

## Typography

- **Barlow Condensed** é a voz da transmissão: títulos de tela, tarjas,
  abas, cabeçalhos de tabela, botões, selos — em maiúsculas com espaçamento
  aberto nos rótulos (`0.06–0.08em`).
- **Barlow** é o texto corrido e os dados das células.
- Números sempre tabulares (`font-variant-numeric: tabular-nums` no `body`).
- Escala: display `clamp(2rem, 5vw, 3.4rem)` (só a abertura do menu), título
  de tela `clamp(1.6rem, 3.2vw, 2.1rem)`, título de seção `0.95rem` em caixa
  alta cinza (`h3.secao`), rótulo `0.72–0.82rem`.

## Layout

- Coluna única de até `1180px`, margem lateral fluida
  `clamp(1rem, 3vw, 2rem)`.
- Barra superior fixa (sticky) com o "logo do canal" à esquerda e o Menu à
  direita; a barra de ação "Começar" fica fixa no rodapé quando há escolha.
- Grade de clubes `repeat(auto-fill, minmax(13.5rem, 1fr))`, 2 colunas
  abaixo de 640px.
- Em grades de duas colunas, os itens têm `min-width: 0` para uma tabela larga
  rolar dentro do próprio quadro em vez de esticar a página.

## Elevation & Depth

- Profundidade por camada de cor, não por sombra: `noite` → `superficie` →
  `superficie-2`.
- Sombras só com deslocamento e desfoque (`0 14px 28px -16px rgba(0,0,0,.9)`),
  no hover dos cards e na barra fixa (com `backdrop-filter: blur(10px)`).

## Shapes

- Cantos retos de TV: `2px` nos selos, `4px` na base, `6px` nos cards de clube.
- O corte diagonal da tarja (`clip-path` de 4 pontos, inclinação de 16–18px) é
  a forma-assinatura: logo do canal, bloco do clube na tarja, título da rodada.
  No celular o corte some e a tarja empilha.

## Components

- **Tarja (`.tarja`, `#rodada > hgroup`)**: bloco verde com corte diagonal
  (escudo + nome/título) + faixa escura de informação + ação à direita.
- **Selo (`.chip`)**: retângulo `2px`, caixa alta condensada; variantes
  `chip-batida`, `chip-perto`, `chip-longe` e neutro (status: Pré-jogo,
  Encerrada).
- **Placar (`#partida-placar .placar b`)**: caixa branca com o resultado em
  preto, entre os dois escudos.
- **Card de clube**: camisa grande com o escudo sobreposto no canto, nome
  condensado, estrelas em dourado, ficha FORÇA/CAIXA/TORCIDA e a meta. Hover
  sobe 3px; selecionado ganha anel verde.
- **Abas**: texto cinza condensado; ativa em branco com indicador interno de
  3px em `gramado-claro` (`box-shadow: inset`), não borda.
- **Meta da diretoria**: tarja inferior em `superficie` com ícone de alvo
  dourado, rótulo, meta e o selo de situação à direita.
- **Ícones**: Lucide em traço de 2px, cor herdada; nada de emoji como ícone.
- **Campo do pré-jogo (`.campo`)**: gramado listrado com o brilho do
  refletor, marcações em SVG (deitado no computador, em pé no celular), seu
  time à esquerda/embaixo. Cada jogador é uma **peça**: camisa do clube com o
  número, sobrenome numa tarja escura, overall numa caixinha branca e sinais
  no canto (estrela dourada = craque, raio âmbar = cansado, cartão = pendurado).

- **Placar de TV (`.placar-tv`, jogo ao vivo)**: bloco verde da rodada com
  corte diagonal, siglas dos clubes com escudo, gols em caixas brancas,
  relógio dourado à direita e o selo de fase (AO VIVO vermelho com luz
  piscando, INTERVALO neutro, FIM DE JOGO verde). No gol, as caixas pulsam
  em dourado.
- **Faixa de GOL (`.faixa-gol`)**: atravessa a tela na **cor principal do
  clube que marcou** (texto pela regra de contraste da identidade), com
  escudo, "GOL!" e o autor; dura 2,4 s em 1× e encurta com a velocidade.
  Some com "reduzir movimento".
- **Narração (`.narracao`)**: o lance mais novo em cima, minuto à esquerda
  em condensado; gol com fundo verde, apitos e placa em itálico.
- **Outros jogos (`.outros`)**: siglas + escudos e placar; a linha que
  mudou pisca em dourado.

## Do's and Don'ts

- Faça a cor trabalhar: verde = emissora/ação, dourado = você, vermelho = ruim.
- Use a tarja nos cabeçalhos de momentos de jogo (pré-jogo, partida, ao vivo).
- Não use borda colorida grossa na lateral de cards ou avisos; o estado vai
  num selo.
- Não use emoji como ícone na moldura do jogo.
- Não pinte o cromo com as cores dos clubes; elas vivem nos escudos e camisas.
