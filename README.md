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
* ✅ Posição específica (função) e posições secundárias
* ✅ Atributos (VEL, FIN, PAS, DRI, MAR, FIS)
* ✅ Número de camisa
* ✅ Valor de mercado, salário e contrato
* ✅ Potencial, evolução e aposentadoria

---

## Clubes

* ✅ Cadastro de clubes
* ✅ País
* ✅ Dinheiro
* ✅ Elenco de jogadores
* ✅ Cálculo automático da força
* ✅ Forma recente
* ✅ Vantagem de mando de campo
* ✅ Identidade visual (cores, escudo e camisa)
* ✅ Finanças (TV, bilheteria, salários, premiação)
* ✅ Rivais (clássicos)
* ✅ Categorias de base

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
* ✅ Táticas e formações com efeito no jogo
* ✅ Transmissão ao vivo com pausa, substituições e mudança de tática

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

## 📌 Status atual (2026-10-18)

O projeto passou do script único para **backend + frontend**:

* **Backend** (`backend/`) — API FastAPI + engine de simulação + SQLite puro
  (sem ORM). `uvicorn app.main:app --reload`, docs em `/docs`. 612 testes.
* **Frontend** (`frontend/`) — HTML + CSS + JS puro em módulos ES (sem build), consome a API.

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
disciplina/pênaltis, estatísticas da partida). **v0.7 (Mercado), v0.8
(Modo Carreira), v0.9 (Persistência/autosave), v1.0 (Jogável: um comando
só, tela inicial, meta da diretoria e demissão) e v1.1 (Cara de jogo:
escudos e camisas, tema de transmissão noturna, pré-jogo no campo e jogo ao
vivo), v1.2 (Modo técnico: hub do clube, simulação interativa, planos de
jogo e formação no meio do jogo), v1.3 (Atributos e posições: posições
específicas, formações desenhadas, caixa de entrada e atributos nos lances)
e v1.4 (Torcida: crescimento, mando de campo, marketing, rival, fama e
ídolos) concluídas** — ver as seções abaixo.

![Gráfico de pontos acumulados por rodada dos 20 clubes](screenshots/evolucao.png)

Antes disso: mando de campo + força no placar, fadiga/rodízio de elenco,
banco de reservas e substituições, e a correção do vermelho que bania o
jogador da temporada.

---

## ✅ v0.5 — Concluída

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

# ✅ Mercado (v0.7) — Concluída

* [x] Valor de mercado (calculado de overall, idade e potencial)
* [x] Salários (de contrato, por temporada; o "salário de mercado" é calculado do overall)
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
* [x] Renovação de contrato (salário, duração e multa; o jogador aceita, contrapropõe ou recusa)
* [x] Contrato novo ao ser transferido (3 temporadas, salário de mercado, sem multa)
* [ ] Vontade do jogador (querer sair, recusar renovar por estar no banco, "time do sonho")
* [x] Evolução por idade (feita na v0.8, na virada de temporada)
* [x] Potencial dos jogadores (na seed; o jogador ainda não evolui)
* [x] Duração de contrato (temporadas restantes, na seed)

---

# ✅ Modo Carreira (v0.8) — Concluída

* [x] Temporadas (uma carreira agrupa as temporadas; "▶ Próxima temporada"
      herda elencos, contratos e caixa e zera pontos e estatísticas;
      a temporada N usa `seed + N − 1`)
* [x] Histórico de campeões (`GET /carreiras/{id}`: campeão, vice,
      artilheiro, MVP e a sua posição em cada temporada; títulos por clube e
      líderes históricos de gols, assistências, partidas e prêmios)
* [x] Envelhecimento e evolução (na virada: jovens crescem rumo ao potencial,
      mais rápido se jogam; a partir dos 30 o overall cai; o potencial é
      revisado a cada temporada, então nem todo jovem chega ao teto)
* [x] Aposentadoria (chance cresce a partir dos 34; +20% sem contrato;
      adia se o elenco ficaria abaixo do mínimo)
* [x] Contratos vencendo (a CPU renova sozinha; quem o técnico não renovou
      sai de graça para o clube onde seria titular, ou deixa a liga)
* [x] Registro da virada (aposentadorias, saídas, renovações — `movimento_virada`)
* [x] Geração de jovens / categorias de base (na virada, cada clube sobe
      jovens de 16–18 anos até completar 18 jogadores, no mínimo 1; posição
      mais carente; overall = média do elenco − 10, potencial +8 a +22)
* [x] CPU dispensa veteranos reservas (30+) com o elenco acima de 18
* [x] Hall da Fama (aposentados com 5+ pontos de lenda: título 2 — só
      com 10+ jogos —, artilharia/MVP 3, 1 a cada 25 gols, pico 90+ vale 2;
      tudo calculado das temporadas, nada guardado)
* [x] Tela da carreira (botão "📜 Carreira": temporadas com campeão, vice,
      artilheiro, MVP e a sua posição — clique abre a temporada —, títulos,
      líderes históricos em abas e os cards do Hall da Fama)
* [x] Aba "Virada" (temporada 2 em diante: o que mudou no seu clube, o seu
      elenco antes → depois com quem subiu e quem caiu, e aposentadorias,
      saídas e joias da base na liga)

---

# ✅ Persistência (v0.9) — Concluída

* [x] SQLite (puro, sem ORM; schema em `backend/app/db/schema.sql`)
* [x] Sistema de Save (salvar temporada simulada)
* [x] Carregar Save (listar / abrir / apagar simulações)
* [x] Autosave
  * cada rodada, transferência e renovação já é gravada na hora
  * a escalação (formação, tática, XI) se salva sozinha, sem jogar a rodada
    (`PATCH /simulacoes/{id}/decisao`, 800 ms depois da última mudança;
    indicador "✔ salvo")
  * ao recarregar a página, o jogo reabre o último save e a aba em que você
    estava (o navegador guarda só isso; o progresso fica no servidor)
  * a lista de saves vem pela última jogada (`atualizada_em`)

---

# ✅ Web / Jogável (v1.0) — Concluída

* [x] Um comando só: a API serve o frontend em `http://localhost:8000` (sem CORS, sem campo "API" na tela)
* [x] Tela inicial de jogador (o jogo abre nela: Continuar / Novo jogo / Carregar; clubes em cards com o ranking de força — `GET /clubes` traz `forca` e `ranking_forca`; seed e "Simular tudo" num painel "🛠 Modo dev"; botão "🏠 Menu")
* [x] Meta da diretoria por temporada — força = média do melhor XI no 4-3-3;
      o ranking de força define a posição mínima (1º → campeão, 2º–4º → G-4,
      5º–8º → top 8, 9º–14º → até 12º, 15º–18º → fora do Z-4, 19º–20º → fugir
      das 2 últimas; calibrado em 60 temporadas). Fixada no início da
      temporada; card 🎯 com a situação (✅ no caminho / ⚠️ em risco, até 3
      abaixo / ❌ longe) nas telas da rodada e da temporada e nos cards de Novo jogo
* [x] Demissão no fim da temporada — ❌ longe da meta 2 temporadas seguidas,
      ou 8+ posições abaixo dela numa só, é demissão e fim de carreira (o
      último lugar conta sempre como longe); uma temporada longe deixa o
      "⚠️ cargo ameaçado". Calculado das temporadas, nada guardado. Tela de
      fim de carreira com o balanço (temporadas, títulos, metas batidas,
      melhor posição) e "✚ Novo jogo"; a próxima temporada fica bloqueada (409)

* [x] API (FastAPI, não Flask)
* [x] Interface Web (`frontend/index.html`)
* [x] Dashboard do campeonato (classificação, rankings, recordes)
* [x] Painel de jogadores (página de jogador + game log)
* [x] Gráfico de pontos por rodada (aba Evolução)
* [x] Interação: escolher clube + tática antes de simular
* [x] Interação: montar a escalação (formação + XI titular)
* [x] Interação: simular rodada a rodada
* [x] Dashboard financeiro (caixa rodada a rodada, receitas × despesas, folha; aba Finanças da liga)
* [x] Mercado de transferências (abas Partida / Mercado / Contratos / Finanças no modo rodada a rodada)
* [x] Estatísticas avançadas (chutes no gol, escanteios, faltas — v0.6)

---

# ✅ Cara de jogo (v1.1) — Concluída

Visual de jogo de verdade, no clima "estádio noturno".

* [x] Identidade dos clubes — cada clube tem cores, formato de escudo e
      padrão de camisa na seed (`identidade` em `clubes.json`, rivais sem
      a mesma cor); o front desenha escudo e camisa em SVG
      (`frontend/js/identidade.js`) no menu, tabelas, confrontos, placar e
      página do clube
* [x] Tema "transmissão noturna" + menu principal — fundo de estádio à noite,
      tarjas de TV em verde-gramado (a faixa de placar é a assinatura: menu,
      rodada, partida), Barlow/Barlow Condensed, ícones Lucide no lugar dos
      emojis da moldura, cards de clube com camisa + escudo + ficha, barra
      "Começar" fixa; celular e desktop. Sistema registrado em `DESIGN.md`
* [x] Pré-jogo — "Jogar a rodada" abre as duas escalações no campo (gramado
      listrado, deitado no computador e em pé no celular), exatamente como o
      motor vai escalar (`GET /simulacoes/{id}/pre-jogo`, só leitura); cada
      jogador com camisa numerada, overall e sinais (craque 88+, cansado,
      pendurado); banco dos dois times; "Ir para o jogo" ou "Mexer na escalação"
* [x] Número de camisa fixo por jogador (único no clube; goleiro titular é o
      1, centroavante o 9; quem chega mantém o número se estiver livre)
* [x] Jogo ao vivo minuto a minuto — "Ir para o jogo" simula a rodada e a
      tela reproduz os lances gravados: placar de TV com relógio e selo AO
      VIVO, narração em pt-BR, intervalo, placa de acréscimos (agora
      gravados na partida), faixa de GOL nas cores do clube, outros jogos com
      placar ao vivo (`GET /rodadas/{n}/ao-vivo`), velocidade 1×/2×/4×
      (lembrada; ~45 s em 1×), pular para o fim e estatísticas no apito final
* [x] Polimento — os emojis que restavam (mercado, contratos, elenco,
      lances, finanças, carreira, disciplina) viraram ícones Lucide, selos e
      cartões desenhados; escala de fontes de 8 degraus registrada no
      `DESIGN.md`; cores reaproveitadas viraram tokens; uma transição única
      entre telas (respeita "reduzir movimento")

---

# ✅ Modo técnico (v1.2) — Concluída

Inspirado no Modo Carreira do FIFA: um menu do clube e a Simulação de
Partida Interativa.

* [x] Hub do clube — a tela antes da rodada é um menu de cards (próximo jogo
      em destaque, escalação, tabela, mercado, contratos, finanças), cada um
      com um resumo; o card abre a seção e "← Menu do clube" volta
* [x] Simulação interativa — "Ir para o jogo" transmite a partida do técnico
      vista de cima: campo com os 22 jogadores e a bola indo para onde o lance
      acontece, gráfico de momentum, estatísticas e outros jogos ao vivo.
      **Pausar** abre a prancheta: muda a tática e faz substituições (em campo
      com energia, cartões e nota até ali; banco; trocas restantes), valendo
      do minuto seguinte. O intervalo pausa sozinho. A partida do técnico roda
      numa corrente de RNG própria, então uma decisão muda só o jogo dele, e
      só do minuto dela em diante; a rodada é gravada no apito final.
      Fechar a página não perde nada: "Voltar para a partida" retoma de onde
      parou, com o elenco travado (mercado, contratos e escalação) até o fim.
      API: `POST/GET /simulacoes/{id}/transmissao`,
      `GET .../transmissao/estado?minuto=N`, `POST .../transmissao/decisoes`
* [x] Planos de jogo — como as táticas personalizadas do EA FC: escalações
      com nome (formação, tática e XI), uma marcada como padrão (★). Toda
      rodada nova já começa no padrão; antes do apito dá para trocar de plano
      ou mexer só naquele jogo ("Mexido só neste jogo", com "Salvar no plano"
      e "Voltar ao plano"). Os planos seguem para a próxima temporada da
      carreira, sem quem saiu do clube. Saves antigos ganham o plano
      "Titular" com a escalação que já tinham.
      API: `GET/POST /simulacoes/{id}/planos`, `PATCH/DELETE .../planos/{id}`,
      `POST .../planos/{id}/usar`
* [x] Formação com efeito e no meio do jogo — a formação pesa na postura como
      a tática, na metade da escala (3-4-3/4-2-4 criam mais e sofrem mais;
      5-4-1/5-3-2 o contrário; 4-3-3 neutra). Na prancheta da pausa (e no
      intervalo) dá para mudar a formação, valendo do minuto seguinte e só
      naquele jogo; quem joga muda por substituição
* [x] Escalação no campo — os titulares aparecem no gramado como o motor vai
      escalar (`escalacao` em `GET /rodadas/proxima`); toque (ou arraste) um
      titular e um reserva da mesma posição para trocar. Grava na hora e
      avisa se o escolhido está exausto e vai ser poupado

---

# ✅ Atributos e posições (v1.3) — Concluída

Cada jogador tem uma posição de verdade e rende menos fora dela:

* [x] Posições mais específicas — goleiro, zagueiro, lateral, volante, meia
      central, meia-atacante, ponta, segundo atacante e centroavante
      (`Jogador.funcao`), e às vezes posições secundárias. O motor segue
      pensando por setor (`posicao`). Cada formação tem as suas vagas (o 4-3-3
      é 2 ZAG, 2 LAT, 1 VOL, 2 MC, 2 PON e 1 CA) e todo elenco da seed cabe em
      qualquer uma sem improvisar
* [x] Formações desenhadas — cada vaga tem o seu lugar no campo, como no
      FIFA/EA FC e no Football Manager: laterais na linha da zaga, um pouco à
      frente e abertos; com três zagueiros eles viram alas, bem mais à
      frente; volante logo à frente da defesa, meia central no meio e
      meia-atacante entre o meio e o ataque; meias abertos (ME/MD) e pontas
      (PE/PD) colados à lateral, o ponta mais alto; segundo atacante atrás do
      centroavante. Vale no editor, no pré-jogo e na transmissão (que
      redesenha o time quando a formação muda no meio do jogo). Formações
      novas: 4-2-3-1, 4-1-2-1-2 (losango) e 4-4-1-1
* [x] Overall por posição — fora da posição o jogador perde overall, pouco
      nas vizinhas e muito do outro lado do campo (um volante 80 rende 74 de
      zagueiro; numa secundária, 78). A força do time usa o overall na vaga.
      Escalação no campo: qualquer jogador de linha troca com qualquer um de
      linha, e o banco mostra quanto cada reserva renderia na vaga escolhida;
      goleiro só troca com goleiro (vale também nas substituições). Dois
      titulares também trocam de vaga entre si (tocando ou arrastando): onde
      o técnico põe cada um fica — o posicionamento vale na formação em que
      foi feito e vai junto nos planos de jogo. Sem posicionamento (ou numa
      formação nova), o motor distribui o XI nas vagas com a menor perda
      somada (algoritmo húngaro)
* [x] Improvisação inteligente — faltando gente numa posição, entra quem
      rende mais na vaga (um lateral ou volante na zaga, não um meia), e quem
      sai de campo deixa a vaga para quem entra
* [x] Caixa de entrada — como no Football Manager e no modo carreira do FIFA,
      cada setor do clube escreve para o técnico (card no menu do clube, com as
      não lidas e filtro por setor). O **diretor de futebol** responde cada
      proposta — aceita, contraproposta (quanto faltou) ou recusada (o que
      pesou: craque, titular, contrato longo, rival; sem revelar o pedido) — e
      avisa quando nem deu para negociar (caixa, elenco cheio...); o
      **departamento médico** fala das lesões e de quem foi liberado; o
      **auxiliar técnico**, de expulsões, suspensões, pendurados e exaustos; a
      **diretoria**, da meta e do balanço da temporada; as **categorias de
      base**, de quem subiu na virada. A resposta da proposta também aparece
      ao lado do mercado, com o link para a mensagem.
      API: `GET /simulacoes/{id}/mensagens`, `POST .../mensagens/{id}/lida`,
      `POST .../mensagens/lidas`
* [x] Atributos do jogador — como os seis do FIFA/EA FC: Velocidade,
      Finalização, Passe, Drible, Marcação e Físico (goleiro: Reflexos e
      Posicionamento). Cada um é o overall + o perfil da posição (o
      centroavante finaliza, o zagueiro marca, o ponta corre e dribla) + o
      estilo do jogador, fixo e tirado do nome — acompanha a evolução na
      carreira e não precisa ser guardado. No motor: quem chuta e quem bate
      pênalti pela finalização; o goleiro pelos reflexos e posicionamento; as
      assistências pelo passe; e, pelo ESTILO (quanto o jogador está acima
      do próprio nível naquilo, para a força não contar duas vezes), o duelo
      do atacante (velocidade e drible) contra quem tenta parar o lance
      (velocidade e marcação), a precisão do chute e o cansaço (físico).
      Calibrado para a liga ficar como antes (2,8 gols por jogo, mesma
      ordem de forças). Aparecem na página do jogador (barras), no mercado
      (os destaques de cada um) e nas dicas do campo

---

# ✅ Torcida (v1.4) — Concluída

A torcida cresce (ou encolhe) com a campanha e com as decisões do técnico,
e o tamanho dela é o que enche a bilheteria:

* [x] Crescimento da torcida — cada jogo mexe nela: vitória +0,3%, derrota
      −0,3%, goleada (3+ gols) ±0,2% a mais, 3+ vitórias seguidas +0,1%, e
      o clássico vale o dobro. No fim da temporada pesa a posição: campeão
      +5%, G-4 +2%, até o 8º +1%, Z-4 −2% (mínimo de 50 mil). Em média o
      campeão termina com ~16% a mais e o lanterna com ~10% a menos.
      Freio: cada clube tem um tamanho natural (a história dele), que
      cresce 5% a cada título, e no fim da temporada a torcida volta 15% do
      caminho até ele. Uma dinastia ainda vira clube grande (o Galaxy, com
      9 títulos em 12 temporadas, vai de 11 a 32 milhões), mas a vantagem
      não dispara: sem o freio a liga dobrava e ele chegava a 56 milhões.
      Determinístico (não sorteia nada: o mesmo seed dá o mesmo
      campeonato); vai para a temporada seguinte da carreira. Aparece no tile "Torcida"
      das finanças do clube, numa coluna da aba Finanças da liga e no
      "Balanço da torcida", mensagem do **marketing** no fim da temporada
* [x] Torcida no mando de campo — jogar em casa sempre conforta, e estádio
      cheio empurra mais: o mando (antes +2,5 fixo na força do mandante)
      vai de ~1,6 com 200 mil torcedores a ~3,0 com 12 milhões (escala
      logarítmica, entre 1,5 e 3,5). A referência é o meio da liga
      (3 milhões), então na média nada muda: 2,8 gols por jogo, ~47% de
      vitórias do mandante. A torcida que cresce com a campanha vira mando
* [x] Campanhas de marketing — card **Marketing** no menu do clube: a
      torcida, a força em casa que ela dá e três campanhas (redes sociais
      +1%, cidade +3%, nacional +6%). O custo é por torcedor novo e sobe
      com o tamanho da campanha (R$ 0,80 → 1,30; cada torcedor rende ~0,38
      por temporada de bilheteria, então se paga em 2–3 temporadas, fora o
      mando). Uma por turno, com caixa para pagar; entra como despesa
      "Marketing" nas finanças e o setor manda a mensagem.
      API: `GET/POST /simulacoes/{id}/marketing`
* [x] Fama dos jogadores — de 0 a 100, é do jogador (vai com ele numa
      transferência). No fim da temporada guarda 78% da anterior e soma
      gols, assistências, melhores em campo, jogos, jogos sem sofrer gol
      (goleiro) e o título; quem some do time é esquecido aos poucos. Os
      craques veteranos já começam famosos. Jogador famoso vale até 30% a
      mais no mercado. Aparece na página do jogador
* [x] Ídolos — fama 60+ e 3+ temporadas no mesmo clube (o tempo de casa
      zera na transferência; a liga fica com uns 15). Cada ídolo atrai
      +0,5% de torcida no fim da temporada (até 3), o clube pede 30% a mais
      para liberá-lo e vendê-lo, para qualquer clube, tira 3% da torcida
      (somado à revolta do rival). Coroa dourada ao lado do nome, lista de
      ídolos na página do clube, e o **marketing** avisa quando nasce um
      ídolo e homenageia o que se aposenta
* [x] Vender um jogador para o rival irrita a torcida — some 2% dela (3% se
      era titular, 5% se era o craque do elenco) e a torcida do rival cresce
      1%. A oferta do rival já mostra quanto a torcida vai encolher, e o
      **marketing** manda "A torcida não perdoou" depois da venda. Tirar
      um jogador do rival faz a nossa torcida crescer 1%

---

# 🏟️ Estádio (v1.5 — em andamento)

O estádio é onde a torcida vira dinheiro e empurra o time:

* [x] Público, capacidade e ingresso — a cada jogo em casa parte da torcida
      vai ao estádio, com retorno decrescente (~5 mil pagantes para 200 mil
      torcedores, ~60 mil para 12 milhões); clássico (+30%) e boa fase
      (±4% por resultado nos últimos 5) enchem mais, e quem não cabe fica de
      fora. Cada clube nasce com um estádio do tamanho da sua demanda (uns
      já lotam nos jogos grandes, ~1 em cada 4 jogos). Card **Estádio** no
      menu do clube com três faixas de ingresso: popular (−40% no preço, +35%
      de público), normal e premium (+60% no preço, −40% de público). O
      preço normal sobe com o tamanho do clube, então a bilheteria segue a
      de antes na média. O **mando de campo vem do público presente** (não
      mais da torcida inteira): ingresso barato e estádio cheio empurram o
      time. Calibrado para os placares não mudarem (2,8 gols por jogo,
      mandante vence ~47%). O público aparece na página da partida.
      API: `GET /simulacoes/{id}/estadio`, `POST /simulacoes/{id}/estadio/ingresso`
* [ ] Ampliação — obras de +5 mil (10 rodadas), +10 mil (um turno) e +20
      mil lugares (uma temporada), pagas com o caixa, uma por vez, com
      manutenção por lugar
* [ ] Clubes da CPU ampliam o estádio quando lotam

---

# 👥 Elencos e segunda liga (v1.6 — em andamento)

Elencos de verdade e, depois, uma segunda liga com jogadores reais (Premier
League 2023/24, dados abertos do OpenFootball) para uma copa entre as ligas:

* [x] Elencos de 23 com 3 goleiros — com 18 jogadores e exatamente 2
      goleiros em todo clube (o mínimo do mercado), nenhum goleiro podia ser
      contratado. Cada clube ganhou 5 reservas fictícios nas posições mais
      carentes (sempre 1 goleiro), com overall um pouco abaixo da média dos
      reservas do clube (`scripts/ampliar_elencos.py`). A base passa a
      completar o elenco até 23. Calibração mantida (2,8 gols por jogo,
      mandante vence ~47%)
* [x] Jogadores livres — 50 sem clube no começo da temporada
      (`scripts/gerar_livres.py` → `data/seeds/livres.json`: veteranos,
      jogadores no auge e jovens, na faixa dos reservas da liga, com
      goleiros). Sem transferência: o clube paga só as **luvas** (10% do
      valor de mercado) e o salário, com contrato de 2 temporadas. Ficam no
      estado do save e só ganham linha na tabela `jogador` quando assinam.
      O **diretor de futebol** avisa da contratação.
      API: `livres` em `GET /simulacoes/{id}/mercado`,
      `POST /simulacoes/{id}/livres/contratar`
      - [x] backend (seed, save, mercado e rota)
      - [x] tela — no mercado, "Jogadores: sem clube" troca a lista de
            compra pelos livres, com as luvas e o botão "Contratar por…"
      - [x] carreira — a lista segue de temporada em temporada
            (`simulacao.livres_json`, gravado quando a temporada acaba). Na
            virada os livres envelhecem (sem jogar, caem) e se aposentam;
            quem não renova e não acha clube **fica sem clube** em vez de
            deixar a liga; clubes da CPU com elenco abaixo de 23 contratam o
            melhor livre da posição carente se ele render mais que um jovem
            da base (sem luvas, como quem chega de graça na virada); no fim
            a lista volta a 50 com livres novos (`app/domain/livres.py`) e é
            cortada em 70. Em 8 temporadas a liga fica como sem livres
            (overall 77,0, idade 26,1)
* [x] Importador da Premier League 2023/24 — os elencos e os 380 jogos do
      [OpenFootball](https://github.com/openfootball/england) (domínio
      público, CC0) ficam em `data/fontes/openfootball/premier-2023-24/`
      (`scripts/baixar_openfootball.py`); `scripts/importar_premier.py` lê do
      disco e gera `data/seeds/premier/` (20 clubes de 23, 50 livres) no
      formato da Taldo, sempre igual. O corte para 23 prefere o time
      principal (camisa até 40 ou 22+ anos); o overall vem da posição na
      tabela de 23/24 (calculada dos jogos), da camisa e da idade, com teto;
      `data/fontes/estrelas-premier.json` corrige à mão ~60 estrelas
      (Haaland 91, Salah 89, Saka 86...). Cores, caixa, torcida e clássicos
      numa tabela do importador. Nomes iguais aos da Taldo ganham a
      nacionalidade ("João Gomes (BRA)"). XI de ~73 (Sheffield) a ~87 (City).
      Ainda não aparece no jogo: é o próximo passo
* [ ] Várias ligas no banco e no motor — todo jogo novo terá as duas
      ligas rodando juntas
      - [x] motor — cada clube tem a sua `liga`; `carregar_campeonato(ligas)`
            lê a seed de cada uma (`LIGAS` no `data_loader`); o calendário é
            o turno e returno de cada liga lado a lado (a rodada N joga as
            duas); tabela, premiação, fama e torcida do fim da temporada são
            por liga; os livres das ligas formam uma lista só. Sem dizer a
            liga, só a Taldo (tudo como antes). Calibrado: Taldo 2,81 gols
            por jogo e mandante 46%; Premier 2,77 e 48% (campeões: Liverpool,
            City, Arsenal); a temporada com as duas leva ~1,4 s
      - [ ] banco e serviços (`simulacao.ligas`, `clube.liga`, meta por liga,
            virada da carreira)
      - [ ] API (clubes por liga, tabela de cada liga)
* [ ] Várias ligas na tela (escolher liga, tabelas e mercado entre ligas)
* [ ] Copa entre as ligas (futuro)

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
│   └── tests/              # 612 testes (domain, db, repositories, services, api)
│
├── frontend/
│   ├── index.html          # marcação das telas
│   ├── style.css
│   └── js/                 # módulos ES (sem build): núcleo, mercado, contratos...
│
└── README.md
```

Rodar:

```bash
cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload
# abra http://localhost:8000 (o frontend é servido pela própria API)
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
* ✅ Eventos avançados (suspensões, lesões, acréscimos)
* ✅ Mercado de transferências
* ✅ Evolução dos jogadores
* ✅ Temporadas contínuas (modo carreira)

---

# 🎯 Objetivo Final

Criar um Football Manager totalmente jogável contendo:

* ✅ Banco de Dados SQLite
* ✅ API (FastAPI)
* ✅ Interface Web
* ✅ Dashboard completo
* ✅ Mercado de transferências
* ✅ Sistema financeiro
* ✅ Modo carreira
* ✅ Temporadas infinitas
* ✅ Versão jogável pelo navegador
* ✅ Torcida, fama e ídolos
* ⏳ Vontade dos jogadores e disputa por contratações

---

> 🚀 **Lembrete:** consistência vence intensidade. Desenvolver entre **1 e 3 horas por dia** representa aproximadamente **30 a 90 horas de evolução por mês**. Pequenos avanços diários constroem grandes projetos.
