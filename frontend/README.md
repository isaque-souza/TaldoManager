# Frontend — Taldo Manager

Interface web do jogo. **Sem build, sem npm**: HTML + CSS + JavaScript puro
(módulos ES nativos do navegador) consumindo a API.

## Como rodar

O frontend é servido pela própria API — um comando só:

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Abra `http://localhost:8000` no navegador. Docs da API: `http://localhost:8000/docs`.

> Abrir o `index.html` com dois cliques (`file://`) não funciona: o JavaScript
> usa módulos ES e chama a API por caminhos relativos ao mesmo endereço.

## Organização

```text
frontend/
├── index.html        só a marcação (seções de cada tela)
├── style.css         estilos (sobre o Pico.css)
└── js/
    ├── main.js       ponto de entrada: liga o modo dev e abre a tela inicial
    ├── inicio.js     tela inicial: continuar, novo jogo (clubes em cards), carregar
    ├── icones.js     ícones (traços do Lucide) e <span data-icone> no HTML
    ├── identidade.js escudo e camisa dos clubes em SVG (cores e formatos de GET /clubes)
    ├── diretoria.js  card 🎯 da meta (e cargo ameaçado) + bloco de fim de carreira
    ├── nucleo.js     estado compartilhado, navegação (← Voltar) e rede (pedir)
    ├── tabelas.js    tabela genérica, links, formatação de dinheiro
    ├── saves.js      lista de simulações salvas (abrir / apagar)
    ├── escalacao.js  montar formação + XI e criar uma temporada nova
    ├── temporada.js  visão da temporada (abas de classificação e rankings)
    ├── grafico.js    gráfico de pontos por rodada (SVG puro)
    ├── rodada.js     modo rodada a rodada (antes / depois de jogar)
    ├── mercado.js    propostas de compra e ofertas de venda
    ├── contratos.js  lista de contratos e renovação
    ├── financas.js   dashboard financeiro (números, gráfico do caixa, fluxo, folha)
    ├── clube.js      página do clube (finanças, jogos, elenco)
    ├── partida.js    página da partida
    └── jogador.js    página do jogador
```

O estado que várias telas leem e mudam (simulação aberta, aba atual, rodada...)
fica num objeto só, `estado`, em `nucleo.js`: um módulo não pode reatribuir uma
variável importada de outro, mas pode mudar a propriedade de um objeto.

## O que dá pra fazer

- **Tela inicial** — o jogo sempre abre nela. **▶ Continuar** reabre o save
  jogado por último (e a aba em que você estava; some se ele terminou em
  demissão); **✚ Novo jogo** mostra os 20 clubes em
  cards (estrelas e posição no ranking de força, caixa, torcida) e cria a
  temporada já em rodada a rodada; **📂 Carregar** lista os saves (Apagar pede
  um segundo clique). O botão **🏠 Menu** volta para ela de qualquer tela.
- **🛠 Modo dev** (recolhido na tela inicial) — os controles antigos:
  **Nova temporada** com *Seed* (mesmo seed → mesmo resultado), modo
  "Simular tudo", escalação de pré-temporada e a lista crua de saves.
- **Visão da temporada** — campeão, MVP, classificação (com forma), artilharia,
  assistências, notas, clean sheets, hat-tricks, histórico, recordes.
- **Página do clube** — clique no nome de um clube: dashboard financeiro
  (caixa, saldo, folha, maior salário; gráfico do caixa rodada a rodada com
  crosshair; receitas × despesas; maiores salários × o que o mercado paga),
  tabela das 38 partidas e elenco.
- **Página da partida** — clique no placar de um jogo: posse, finalizações,
  linha do tempo (gols, cartões, substituições) e as duas escalações com nota.
- **Página do jogador** — clique no nome em qualquer tabela: ficha + game log
  (nota, gols e assistências partida a partida).
- **Aba Evolução** — gráfico (SVG puro) dos pontos acumulados por rodada dos
  20 clubes; clique num clube na legenda para destacá-lo.
- **Seu clube + tática** (modo dev) — antes de "Nova temporada", escolha um clube e uma
  postura (ofensivo/equilibrado/defensivo). Só esse clube usa a tática; ele
  fica destacado na classificação e no gráfico, com um resumo do desempenho.
- **Escalação** — com um clube escolhido, o painel "Escalação" deixa montar a
  formação e o XI titular por posição. Slot em *automático* = o motor decide;
  o XI é a preferência (cansados cedem lugar a reservas ao longo da temporada).

O botão **← Voltar** desfaz a última navegação.

- **Rodada a rodada** — abas ⚽ Partida (escalação, tática), 🔁 Mercado
  (propostas, ofertas; 🟢/🔒 conforme a janela), 📝 Contratos (⚠️ quantos
  acabam) e 💰 Finanças. O botão de jogar fica acima das abas.
- **Aba Finanças** da temporada — caixa, receitas, despesas, saldo e folha
  dos 20 clubes.

## Próximos passos

1. Modo carreira (v0.8): virar a temporada, envelhecimento, contratos vencendo.
