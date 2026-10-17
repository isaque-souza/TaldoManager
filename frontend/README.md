# Frontend — Taldo Manager

Interface web do jogo. **Sem build, sem npm**: HTML + CSS + JavaScript puro
(módulos ES nativos do navegador) consumindo a API.

## Como rodar

### 1. Suba a API (terminal 1)

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

A API sobe em `http://localhost:8000`. Docs interativas: `http://localhost:8000/docs`.

### 2. Sirva o frontend (terminal 2)

```bash
cd frontend
python -m http.server 5500
```

Abra `http://localhost:5500` no navegador e clique em **Nova temporada**.

> **Precisa** ser servido via `http.server`: o JavaScript usa módulos ES
> (`<script type="module">`), que o navegador não carrega de `file://` — abrir
> o `index.html` com dois cliques deixa a página sem funcionar.

## Organização

```text
frontend/
├── index.html        só a marcação (seções de cada tela)
├── style.css         estilos (sobre o Pico.css)
└── js/
    ├── main.js       ponto de entrada: liga os botões do topo e carrega os dados
    ├── nucleo.js     estado compartilhado, navegação (← Voltar) e rede (pedir)
    ├── tabelas.js    tabela genérica, links, formatação de dinheiro
    ├── saves.js      lista de simulações salvas (abrir / apagar)
    ├── escalacao.js  montar formação + XI e criar uma temporada nova
    ├── temporada.js  visão da temporada (abas de classificação e rankings)
    ├── grafico.js    gráfico de pontos por rodada (SVG puro)
    ├── rodada.js     modo rodada a rodada (antes / depois de jogar)
    ├── mercado.js    propostas de compra e ofertas de venda
    ├── contratos.js  lista de contratos e renovação
    ├── clube.js      página do clube (finanças, jogos, elenco)
    ├── partida.js    página da partida
    └── jogador.js    página do jogador
```

O estado que várias telas leem e mudam (simulação aberta, aba atual, rodada...)
fica num objeto só, `estado`, em `nucleo.js`: um módulo não pode reatribuir uma
variável importada de outro, mas pode mudar a propriedade de um objeto.

## O que dá pra fazer

- **Nova temporada** — roda e **salva** a simulação (SQLite). O campo *Seed*
  deixa reproduzível: mesmo seed → mesmo resultado.
- **Lista de simulações salvas** — troca entre temporadas já rodadas; **Apagar**
  remove a selecionada.
- **Visão da temporada** — campeão, MVP, classificação (com forma), artilharia,
  assistências, notas, clean sheets, hat-tricks, histórico, recordes.
- **Página do clube** — clique no nome de um clube na classificação: elenco
  completo + tabela das 38 partidas (mando, placar, resultado).
- **Página da partida** — clique no placar de um jogo: posse, finalizações,
  linha do tempo (gols, cartões, substituições) e as duas escalações com nota.
- **Página do jogador** — clique no nome em qualquer tabela: ficha + game log
  (nota, gols e assistências partida a partida).
- **Aba Evolução** — gráfico (SVG puro) dos pontos acumulados por rodada dos
  20 clubes; clique num clube na legenda para destacá-lo.
- **Seu clube + tática** — antes de "Nova temporada", escolha um clube e uma
  postura (ofensivo/equilibrado/defensivo). Só esse clube usa a tática; ele
  fica destacado na classificação e no gráfico, com um resumo do desempenho.
- **Escalação** — com um clube escolhido, o painel "Escalação" deixa montar a
  formação e o XI titular por posição. Slot em *automático* = o motor decide;
  o XI é a preferência (cansados cedem lugar a reservas ao longo da temporada).

O botão **← Voltar** desfaz a última navegação.

## Próximos passos

1. Abas no modo rodada a rodada (Partida / Mercado / Contratos / Finanças).
2. Dashboard financeiro (evolução do caixa, receitas × despesas).
