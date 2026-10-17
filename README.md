# ⚽ Taldo Manager

Um Football Manager desenvolvido em Python com foco em aprendizado prático de programação.

O projeto está sendo construído do zero para estudar lógica de programação, orientação a objetos, arquitetura de software e desenvolvimento de sistemas.

---

# 🚀 Funcionalidades

## Jogadores

* ✅ Cadastro de jogadores
* ✅ Nome
* ✅ Idade
* ✅ Posição
* ✅ Overall
* ✅ Jogos
* ✅ Gols
* ✅ Assistências
* ✅ Média de nota
* ✅ Melhor nota
* ✅ Pior nota
* ✅ Melhor em campo
* ✅ Hat-tricks
* ✅ Pênaltis convertidos
* ✅ Pênaltis perdidos
* ✅ Clean Sheets
* ✅ Cartões amarelos
* ✅ Cartões vermelhos

---

## Clubes

* ✅ Cadastro de clubes
* ✅ País
* ✅ Dinheiro
* ✅ Elenco de jogadores
* ✅ Cálculo automático da força
* ✅ Forma recente
* ✅ Vantagem de mando de campo

---

## Partidas

* ✅ Simulação baseada na força dos clubes
* ✅ Geração de gols
* ✅ Distribuição de gols por posição
* ✅ Distribuição de assistências por posição
* ✅ Sistema de notas
* ✅ Melhor jogador da partida
* ✅ Clean Sheets
* ✅ Chutes no gol
* ✅ Escanteios
* ✅ Resultado automático
* ✅ Empates
* ✅ Placar completo
* ✅ Hat-tricks
* ✅ Pênaltis
* ✅ Pênaltis perdidos
* ✅ Cartões amarelos
* ✅ Cartões vermelhos
* ✅ Segundo amarelo
* ✅ Pênaltis defendidos
* ✅ Suspensões automáticas (vermelho + acúmulo de amarelos)
* ✅ Lesões (jogador fora por N rodadas)
* ✅ Acréscimos
* ✅ Eventos cronológicos
* ✅ Ordenação por minuto

---

## Campeonato

* ✅ Cadastro de campeonatos
* ✅ Calendário turno e returno
* ✅ Sorteio automático de rodadas
* ✅ Histórico de partidas
* ✅ Classificação
* ✅ Critérios de desempate
* ✅ Artilharia
* ✅ Assistências
* ✅ Ranking de notas
* ✅ MVP do campeonato
* ✅ Ranking de Clean Sheets
* ✅ Ranking de Hat-tricks
* ✅ Ranking de disciplina (cartões + faltas)
* ✅ Ranking de pênaltis (convertidos / perdidos)
* ✅ Recordes do campeonato

---

## Estrutura

* ✅ Separação dos dados (Seed)
* ✅ Arquivos JSON
* ✅ Carregamento automático dos dados
* ✅ Código refatorado em métodos menores
* ✅ Eventos estruturados em dicionários
* ✅ Processamento cronológico de eventos

---

# 📚 Tecnologias

* Python 3
* Programação Orientada a Objetos (POO)
* FastAPI + Pydantic
* SQLite (`sqlite3` puro, sem ORM)
* HTML + JavaScript puro (frontend sem build)
* JSON (seed)
* Git / GitHub

---

# 🎯 Objetivo

Este projeto tem como objetivo estudar:

* Lógica de programação
* Orientação a Objetos
* Arquitetura de Software
* Estruturação de projetos
* Simulação de sistemas
* Git e GitHub
* Banco de Dados (SQLite)
* APIs web (FastAPI)

---

# 🗺️ Roadmap

## 📌 Status atual (2026-09-02)

O projeto passou do script único para **backend + frontend**:

* **Backend** (`backend/`) — API FastAPI + engine de simulação + SQLite puro
  (sem ORM). `uvicorn app.main:app --reload`, docs em `/docs`. 211 testes.
* **Frontend** (`frontend/`) — `index.html` único, JS puro, consome a API.

Já dá pra:

* Simular uma temporada (38 rodadas) com seed reproduzível.
* **Salvar** cada temporada no SQLite e navegar entre elas.
* Ver classificação (com forma), artilharia, assistências, notas, clean
  sheets, hat-tricks, histórico e recordes.
* Abrir a **página de um clube** (elenco + tabela das 38 partidas).
* Abrir a **página de uma partida** (posse, finalizações, linha do tempo,
  as duas escalações com nota).
* Abrir a **página de um jogador** (ficha + game log: nota, gols e
  assistências partida a partida).
* Ver o **gráfico de pontos por rodada** (corrida pelo título, aba Evolução).
* **Escolher um clube e uma tática** (ofensivo/equilibrado/defensivo) antes de
  simular — a tática mexe nos pesos da engine só desse clube. Ofensivo faz
  mais gols pró e contra; defensivo, menos dos dois lados.
* **Montar a escalação** — formação (4-4-2, 3-5-2, ...) e o XI titular por
  posição. É a preferência: jogadores muito cansados dão lugar a reservas
  ao longo das 38 rodadas.
* **Simular rodada a rodada** — o save nasce "em andamento" e você joga
  uma rodada de cada vez, mexendo na escalação e na tática entre os jogos
  e vendo a tabela evoluir. Sem mudar nada, reproduz a temporada contínua
  com o mesmo seed.
* **Suspensões automáticas** — vermelho (direto ou 2º amarelo) tira o
  jogador do jogo seguinte; a cada 5 amarelos no campeonato, mais um jogo
  de gancho. No modo rodada a rodada os suspensos aparecem fora da
  escalação.
* **Lesões** — durante a partida um titular pode se machucar (evento 🚑 na
  linha do tempo) e ficar de 1 a 12 rodadas fora. No modo rodada a rodada
  aparecem em "Fora desta rodada".
* **Rankings de disciplina e pênaltis** — abas novas: 🟥/🟨/faltas por
  jogador e aproveitamento de pênalti.
* **Pênaltis defendidos e acréscimos** — o goleiro pode pegar o pênalti
  (🧤), e cada jogo tem 1–5 min de acréscimo (eventos "90+N'").
* **Estatísticas da partida** — chutes no gol e escanteios, no card da
  página da partida.

**v0.6 concluída** (eventos avançados, suspensões, lesões, rankings de
disciplina/pênaltis, estatísticas da partida).

![Gráfico de pontos acumulados por rodada dos 20 clubes](screenshots/evolucao.png)

Antes disso: mando de campo + força no placar, fadiga/rodízio de elenco,
banco de reservas e substituições, e a correção do vermelho que bania o
jogador da temporada.

---

## ✅ Versão Atual (v0.5) — Concluída

### Base do jogo

* [x] Cadastro de jogadores
* [x] Cadastro de clubes
* [x] Contratação de jogadores
* [x] Seed em JSON
* [x] Loader automático

### Simulação

* [x] Cálculo de força dos clubes
* [x] Mando de campo
* [x] Forma recente
* [x] Simulação de partidas
* [x] Distribuição de gols
* [x] Distribuição de assistências
* [x] Sistema de notas
* [x] Melhor jogador da partida
* [x] Clean Sheets
* [x] Hat-tricks
* [x] Pênaltis
* [x] Pênaltis perdidos
* [x] Cartões amarelos
* [x] Cartões vermelhos
* [x] Segundo amarelo
* [x] Eventos cronológicos
* [x] Ordenação dos eventos

### Campeonato

* [x] Campeonato
* [x] Calendário turno e returno
* [x] Histórico
* [x] Classificação
* [x] Critérios de desempate
* [x] Artilharia
* [x] Assistências
* [x] Ranking de notas
* [x] MVP do campeonato
* [x] Ranking de Hat-tricks
* [x] Recordes do campeonato

### Código

* [x] Refatoração da classe Partida
* [x] Refatoração da classe Campeonato
* [x] Métodos reutilizáveis
* [x] Organização do projeto
* [x] Sistema de eventos estruturados

---

# ✅ v0.6 — Concluída

## Eventos Avançados

* [x] Expulsão afetando força do time (`penalidade_expulsao`)
* [x] Substituições (banco de reservas + rodízio por fadiga)
* [x] Defesas difíceis (`goleiro_defendeu`)
* [x] Suspensão automática por vermelho (perde o jogo seguinte)
* [x] Suspensão por acúmulo de amarelos (a cada 5 no campeonato)
* [x] Lesões (evento na partida + jogador fora por 1–12 rodadas)
* [x] Pênaltis defendidos (goleiro pega; ~14% das cobranças)
* [x] Acréscimos (1–5 min; eventos aparecem como "90+N'")

## Estatísticas da Partida

* [x] Posse de bola
* [x] Finalizações
* [x] Chutes no gol (persistido + card na página da partida)
* [x] Escanteios (persistido + card na página da partida)
* [x] Faltas (total por jogador — coluna no ranking de disciplina)

## Estatísticas Gerais

* [x] Histórico individual dos jogadores (game log por jogador)
* [x] Estatísticas por temporada (cada simulação salva é um snapshot)
* [x] Ranking de melhores em campo (MVP do campeonato)
* [x] Ranking de cartões (aba Disciplina: 🟥, 🟨, faltas — cartões saem de faltas)
* [x] Ranking de pênaltis (convertidos / perdidos)

---

# 💰 Mercado (v0.7) — em andamento

* [x] Valor de mercado (calculado de overall, idade e potencial)
* [x] Salários (por temporada, calculado do overall)
* [x] Sistema financeiro (cota de TV, bilheteria, salários e premiação; card na página do clube)
* [x] Compra de jogadores (pelo valor de mercado, no modo rodada a rodada)
* [x] Venda de jogadores (os clubes fazem ofertas; você escolhe qual aceitar)
* [x] Janela de transferências (pré-temporada e virada do turno) + limites de elenco (16–25, 2+ goleiros)
* [x] Negociações (preço pedido pela importância do jogador; aceita / contraproposta / recusa; até 3 propostas por janela)
* [x] Multa rescisória (nem todo jogador tem; pagando, o clube não pode recusar)
* [x] Rivais (clássicos na seed; negociar com o rival custa 1,5×)
* [ ] Disputa pela contratação, como no futebol real: qual clube paga mais,
      qual é mais famoso, onde o jogador seria titular (ou banco, se já há
      jogadores melhores na posição), se é o "time do sonho" dele...
* [ ] Renovação de contrato
* [ ] Evolução por idade
* [x] Potencial dos jogadores (na seed; o jogador ainda não evolui)
* [x] Duração de contrato (temporadas restantes, na seed)

---

# 🧬 Atributos e posições (ideia futura — a desenvolver)

Hoje cada jogador tem uma posição e um overall só. A ideia é ele ter
qualidades próprias e um mapa de rendimento por posição:

* [ ] Atributos do jogador (ex.: passe, finalização, marcação, velocidade...)
* [ ] Overall por posição (ex.: um volante que rende 80 de volante e 74 de zagueiro)
* [ ] Posições mais específicas (zagueiro, lateral, volante, meia, ponta, centroavante)
* [ ] Improvisação inteligente: sem zagueiros disponíveis, o volante que sabe
      jogar de zagueiro recua e outro volante entra no lugar dele (hoje a
      escalação só pega o melhor jogador de linha que sobrou)

---

# 📣 Torcida (ideia futura — a desenvolver)

Hoje `torcedores` é fixo e só alimenta a bilheteria. A ideia é a torcida
crescer (ou encolher) com as decisões do técnico:

* [ ] Crescimento da torcida (campanha boa, títulos, sequência de vitórias)
* [ ] Campanhas de marketing (gastar dinheiro para atrair torcedores)
* [ ] Fama dos jogadores (cada jogador tem sua fama; craques famosos atraem torcida)
* [ ] Contratar ídolos que a torcida ama (impacto na torcida e na bilheteria)
* [ ] Vender um jogador para o rival irrita a torcida (hoje a oferta só vem marcada com ⚔️)

---

# 🏆 Modo Carreira (v0.8)

* [ ] Temporadas
* [ ] Histórico de campeões
* [ ] Envelhecimento
* [ ] Aposentadoria
* [ ] Geração de jovens
* [ ] Categorias de base
* [ ] Hall da Fama

---

# 💾 Persistência (v0.9) — em andamento

* [x] SQLite (puro, sem ORM; schema em `backend/app/db/schema.sql`)
* [x] Sistema de Save (salvar temporada simulada)
* [x] Carregar Save (listar / abrir / apagar simulações)
* [ ] Autosave

---

# 🌐 Web (v1.0) — em andamento

* [x] API (FastAPI, não Flask)
* [x] Interface Web (`frontend/index.html`)
* [x] Dashboard do campeonato (classificação, rankings, recordes)
* [x] Painel de jogadores (página de jogador + game log)
* [x] Gráfico de pontos por rodada (aba Evolução)
* [x] Interação: escolher clube + tática antes de simular
* [x] Interação: montar a escalação (formação + XI titular)
* [x] Interação: simular rodada a rodada
* [ ] Dashboard financeiro
* [ ] Mercado de transferências (painel básico no modo rodada a rodada já existe)
* [ ] Estatísticas avançadas (chutes no gol, escanteios, faltas)

---

# 📁 Estrutura

```text
TaldoManager/
│
├── backend/
│   ├── app/
│   │   ├── api/            # rotas + schemas Pydantic (FastAPI)
│   │   ├── core/           # config
│   │   ├── db/             # schema.sql + conexão SQLite
│   │   ├── domain/         # Jogador, Clube, Partida, Campeonato (engine)
│   │   ├── repositories/   # acesso a cada tabela
│   │   ├── services/       # simulacao_service (orquestra tudo)
│   │   └── main.py         # app FastAPI
│   ├── data/               # seed JSON + banco local (gerado)
│   ├── scripts/            # data_loader
│   └── tests/              # 211 testes (domain, db, repositories, services, api)
│
├── frontend/
│   └── index.html          # SPA em JS puro, consome a API
│
└── README.md
```

Rodar:

```bash
# terminal 1 — API
cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload

# terminal 2 — frontend
cd frontend && python -m http.server 5500
```

---

# 🎯 Meta de Desenvolvimento

**Objetivo:** manter uma rotina consistente de **1 a 3 horas por dia**.

## Regras do Projeto

* ✅ Desenvolver pelo menos uma funcionalidade por semana
* ✅ Não iniciar um sistema novo antes de concluir o atual
* ✅ Testar todas as implementações
* ✅ Refatorar quando necessário
* ✅ Fazer commit ao final de cada sessão
* ✅ Executar `git push` após cada commit
* ✅ Atualizar o roadmap sempre que uma funcionalidade for concluída

---

# 🎯 Objetivo de Curto Prazo

Transformar o Taldo Manager em um simulador completo de campeonatos com:

* ✅ Estatísticas completas
* ✅ Sistema de Save (temporadas salvas em SQLite)
* ✅ Interface web para navegar nos resultados
* ⏳ Eventos avançados (suspensões, lesões, acréscimos)
* ⏳ Mercado de transferências
* ⏳ Evolução dos jogadores
* ⏳ Temporadas contínuas (modo carreira)

---

# 🎯 Objetivo Final

Criar um Football Manager totalmente jogável contendo:

* Banco de Dados SQLite
* API Flask
* Interface Web
* Dashboard completo
* Mercado de transferências
* Sistema financeiro
* Modo carreira
* Temporadas infinitas
* Versão jogável pelo navegador

---

> 🚀 **Lembrete:** consistência vence intensidade. Desenvolver entre **1 e 3 horas por dia** representa aproximadamente **30 a 90 horas de evolução por mês**. Pequenos avanços diários constroem grandes projetos.
