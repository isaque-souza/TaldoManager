// Estádio (v1.5): capacidade, faixa do ingresso, ampliação e o público da
// temporada. A faixa vale a partir do próximo jogo em casa; trocar é
// reversível, então basta um clique (sem confirmação). A obra sai do caixa
// e não volta: dois cliques, como nas campanhas.

import { $, api, estado, limparAviso, ocupado, pedir } from "./nucleo.js";
import { dinheiro } from "./tabelas.js";
import { icone } from "./icones.js";
import { carregarMarketing } from "./marketing.js";
import { carregarCaixa } from "./caixa.js";
import { carregarProximaRodada } from "./rodada.js";

// onde: o aviso aparece perto do que foi clicado ("faixa" ou "obra");
// avisoRodada: o aviso some quando a rodada vira (como no marketing)
const es = { dados: null, aviso: "", ruim: false, onde: "faixa", avisoRodada: null };
const rodadaAtual = () => estado.rodadaInfo && estado.rodadaInfo.rodada;

const caminho = () => `/simulacoes/${estado.simId}/estadio`;
const milhar = (n) => n.toLocaleString("pt-BR");
const pct = (n) => `${n.toLocaleString("pt-BR", { maximumFractionDigits: 0 })}%`;
const reais = (v) =>
  `R$ ${v.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const rodadas = (n) => (n === 1 ? "1 rodada" : `${n} rodadas`);
const mando = (m) =>
  `+${m.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}`;

export async function carregarEstadio() {
  if (!estado.simId) return;
  const dados = await pedir(caminho());
  if (!dados) return;
  es.dados = dados;
  if (es.avisoRodada !== rodadaAtual()) es.aviso = "";
  renderEstadio();
}

function renderHubEstadio() {
  const d = es.dados;
  const faixa = d.faixas.find((f) => f.faixa === d.ingresso);
  $("hub-estadio").textContent = `${milhar(d.capacidade)} lugares`;
  const info = d.temporada.jogos_em_casa
    ? `ingresso ${faixa.nome.toLowerCase()} · ${pct(d.temporada.ocupacao_media)} de ocupação`
    : `ingresso ${faixa.nome.toLowerCase()}`;
  $("hub-estadio-info").textContent = d.obra
    ? `${info} · em obra (+${milhar(d.obra.lugares)})`
    : info;
}

function cardFaixa(f, atual) {
  const escolhida = f.faixa === atual;
  return `<article class="mk-campanha es-faixa${escolhida ? " es-escolhida" : ""}">
      <header><strong>${f.nome}</strong>${escolhida ? ` <small class="es-atual">${icone("ok")} em uso</small>` : ""}</header>
      <p>${f.descricao}</p>
      <dl class="mk-ficha">
        <div><dt>Ingresso</dt><dd>${reais(f.preco)}</dd></div>
        <div><dt>Público</dt><dd>${milhar(f.publico)} <small>(${pct(f.ocupacao)})</small></dd></div>
      </dl>
      <dl class="mk-ficha">
        <div><dt>Por jogo</dt><dd>R$ ${dinheiro(f.bilheteria)}</dd></div>
        <div><dt>Força em casa</dt><dd>${mando(f.mando_de_campo)}</dd></div>
      </dl>
      <button class="es-usar${escolhida ? " secondary" : ""}" data-faixa="${f.faixa}" ${escolhida ? "disabled" : ""}>
        ${escolhida ? "Em uso" : "Usar esta faixa"}</button>
    </article>`;
}

function aviso(onde) {
  const texto = es.onde === onde ? es.aviso : "";
  return `<p class="mk-msg${es.ruim ? " ruim" : ""}" role="status">${texto}</p>`;
}

function cardObra(o) {
  const bloqueio = o.bloqueio
    ? `<small class="mk-bloqueio">${icone("cadeado")} ${o.bloqueio}</small>`
    : "";
  return `<article class="mk-campanha">
      <header><strong>${o.nome}</strong></header>
      <p>${o.descricao}</p>
      <dl class="mk-ficha">
        <div><dt>Lugares</dt><dd>+${milhar(o.lugares)}</dd></div>
        <div><dt>Prazo</dt><dd>${rodadas(o.rodadas)}</dd></div>
      </dl>
      <dl class="mk-ficha">
        <div><dt>Custo</dt><dd>R$ ${dinheiro(o.custo)}</dd></div>
        <div><dt>Manutenção</dt><dd>R$ ${dinheiro(o.manutencao)} <small>por jogo</small></dd></div>
      </dl>
      ${bloqueio}
      <button class="es-obra" data-tipo="${o.tipo}" ${o.bloqueio ? "disabled" : ""}>Contratar obra</button>
    </article>`;
}

function blocoAmpliacao(d) {
  let andamento = "";
  if (d.obra) {
    const feito = d.obra.rodadas - d.obra.faltam;
    andamento = `<div class="es-andamento">
        <p><strong>${icone("obra")} ${d.obra.nome}</strong>: +${milhar(d.obra.lugares)} lugares,
          ${feito} de ${rodadas(d.obra.rodadas)} · ${d.obra.faltam === 1 ? "falta 1 rodada" : `faltam ${rodadas(d.obra.faltam)}`}.</p>
        <span class="es-progresso" role="progressbar" aria-valuemin="0"
          aria-valuemax="${d.obra.rodadas}" aria-valuenow="${feito}"
          aria-label="Andamento da obra"><span style="width:${((feito / d.obra.rodadas) * 100).toFixed(1)}%"></span></span>
      </div>`;
  }
  const ampliados = d.lugares_ampliados
    ? `<p class="mk-intro">Já ampliados: ${milhar(d.lugares_ampliados)} lugares, com
        manutenção de R$ ${dinheiro(d.manutencao)} por jogo em casa.</p>`
    : "";
  return `<h3 class="es-titulo">${icone("obra")} Ampliação</h3>
    <p class="mk-intro">Mais lugares só rendem se o estádio lota. A obra é paga à
      vista, uma por vez, e o estádio segue funcionando até ficar pronta; o prazo
      conta as rodadas jogadas, e uma obra que não acabar na temporada segue na
      próxima. Os lugares novos pagam manutenção a cada jogo em casa.</p>
    ${aviso("obra")}${andamento}${ampliados}
    <div class="mk-campanhas">${d.obras.map(cardObra).join("")}</div>`;
}

function renderEstadio() {
  const d = es.dados;
  const t = d.temporada;
  renderHubEstadio();

  const temporada = t.jogos_em_casa
    ? `média de ${milhar(t.publico_medio)} por jogo`
    : "nenhum jogo em casa ainda";

  $("r-estadio").innerHTML = `
    <div class="tiles">
      <div class="tile"><span class="tile-rotulo">Capacidade</span>
        <span class="tile-valor">${milhar(d.capacidade)}</span>
        <span class="tile-detalhe">lugares</span></div>
      <div class="tile"><span class="tile-rotulo">Ocupação</span>
        <span class="tile-valor">${t.jogos_em_casa ? pct(t.ocupacao_media) : "—"}</span>
        <span class="tile-detalhe">${t.jogos_em_casa ? `${t.lotados} de ${t.jogos_em_casa} lotados` : temporada}</span></div>
      <div class="tile"><span class="tile-rotulo">Bilheteria</span>
        <span class="tile-valor">${dinheiro(t.bilheteria)}</span>
        <span class="tile-detalhe">${t.jogos_em_casa ? temporada : "na temporada"}</span></div>
    </div>
    <p class="mk-intro">Parte da torcida vai a cada jogo em casa; clássicos e boa
      fase enchem mais, e quem não cabe fica de fora. O público é o que empurra
      o time: estádio cheio, mais força em casa. As estimativas são de um jogo
      comum, na fase atual.</p>
    ${aviso("faixa")}
    <div class="mk-campanhas">${d.faixas.map((f) => cardFaixa(f, d.ingresso)).join("")}</div>
    ${blocoAmpliacao(d)}`;

  $("r-estadio").querySelectorAll(".es-usar:not([disabled])").forEach((b) =>
    b.addEventListener("click", () => trocarFaixa(b.dataset.faixa))
  );
  $("r-estadio").querySelectorAll(".es-obra:not([disabled])").forEach((b) =>
    b.addEventListener("click", () => cliqueObra(b))
  );
}

// dois cliques, como nas campanhas (sem confirm(), que trava a página)
async function cliqueObra(botao) {
  if (botao.dataset.confirmar !== "1") {
    botao.dataset.confirmar = "1";
    botao.textContent = "Confirmar?";
    return;
  }
  const { dados, erro } = await postar("/obra", { tipo: botao.dataset.tipo }, "Contratando a obra…");
  if (erro) {
    es.aviso = `${icone("nao")} Não deu: ${erro}.`;
    es.ruim = true;
    es.onde = "obra";
  es.avisoRodada = rodadaAtual();
    return carregarEstadio();
  }
  es.dados = dados;
  es.aviso = `${icone("ok")} ${dados.obra.nome} contratado: +${milhar(dados.obra.lugares)} lugares em ${rodadas(dados.obra.rodadas)}.`;
  es.ruim = false;
  es.onde = "obra";
  es.avisoRodada = rodadaAtual();
  renderEstadio();
  carregarCaixa();
  await carregarProximaRodada();   // o caixa mudou
}

// POST com o motivo do 400 visível, aqui na seção
async function postar(sufixo, corpo, texto) {
  limparAviso();
  ocupado(true, texto);
  try {
    const resp = await fetch(`${api()}${caminho()}${sufixo}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(corpo),
    });
    const dados = await resp.json().catch(() => ({}));
    if (!resp.ok) return { erro: dados.detail || `HTTP ${resp.status}` };
    return { dados };
  } catch (e) {
    return { erro: e.message };
  } finally {
    ocupado(false);
  }
}

async function trocarFaixa(faixa) {
  const { dados, erro } = await postar("/ingresso", { faixa }, "Trocando o ingresso…");
  if (erro) {
    es.aviso = `${icone("nao")} Não deu: ${erro}.`;
    es.ruim = true;
    es.onde = "faixa";
  es.avisoRodada = rodadaAtual();
    return carregarEstadio();
  }
  es.dados = dados;
  const nome = dados.faixas.find((f) => f.faixa === faixa).nome;
  es.aviso = `${icone("ok")} Ingresso ${nome.toLowerCase()} a partir do próximo jogo em casa.`;
  es.ruim = false;
  es.onde = "faixa";
  es.avisoRodada = rodadaAtual();
  renderEstadio();
  carregarMarketing();   // a força em casa do card de marketing mudou
}
