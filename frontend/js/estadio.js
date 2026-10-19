// Estádio (v1.5): capacidade, faixa do ingresso e o público da temporada.
// A faixa vale a partir do próximo jogo em casa; trocar é reversível, então
// basta um clique (sem confirmação).

import { $, api, estado, limparAviso, ocupado, pedir } from "./nucleo.js";
import { dinheiro } from "./tabelas.js";
import { icone } from "./icones.js";
import { carregarMarketing } from "./marketing.js";

const es = { dados: null, aviso: "", ruim: false };

const caminho = () => `/simulacoes/${estado.simId}/estadio`;
const milhar = (n) => n.toLocaleString("pt-BR");
const pct = (n) => `${n.toLocaleString("pt-BR", { maximumFractionDigits: 0 })}%`;
const reais = (v) =>
  `R$ ${v.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const mando = (m) =>
  `+${m.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}`;

export async function carregarEstadio() {
  if (!estado.simId) return;
  const dados = await pedir(caminho());
  if (!dados) return;
  es.dados = dados;
  renderEstadio();
}

function renderHubEstadio() {
  const d = es.dados;
  const faixa = d.faixas.find((f) => f.faixa === d.ingresso);
  $("hub-estadio").textContent = `${milhar(d.capacidade)} lugares`;
  $("hub-estadio-info").textContent = d.temporada.jogos_em_casa
    ? `ingresso ${faixa.nome.toLowerCase()} · ${pct(d.temporada.ocupacao_media)} de ocupação`
    : `ingresso ${faixa.nome.toLowerCase()}`;
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
    <p id="es-msg" class="mk-msg${es.ruim ? " ruim" : ""}" role="status">${es.aviso}</p>
    <div class="mk-campanhas">${d.faixas.map((f) => cardFaixa(f, d.ingresso)).join("")}</div>`;

  $("r-estadio").querySelectorAll(".es-usar:not([disabled])").forEach((b) =>
    b.addEventListener("click", () => trocarFaixa(b.dataset.faixa))
  );
}

async function trocarFaixa(faixa) {
  limparAviso();
  ocupado(true, "Trocando o ingresso…");
  let dados = {};
  let erro = null;
  try {
    const resp = await fetch(`${api()}${caminho()}/ingresso`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ faixa }),
    });
    dados = await resp.json().catch(() => ({}));
    if (!resp.ok) erro = dados.detail || `HTTP ${resp.status}`;
  } catch (e) {
    erro = e.message;
  } finally {
    ocupado(false);
  }
  if (erro) {
    es.aviso = `${icone("nao")} Não deu: ${erro}.`;
    es.ruim = true;
    return carregarEstadio();
  }
  es.dados = dados;
  const nome = dados.faixas.find((f) => f.faixa === faixa).nome;
  es.aviso = `${icone("ok")} Ingresso ${nome.toLowerCase()} a partir do próximo jogo em casa.`;
  es.ruim = false;
  renderEstadio();
  carregarMarketing();   // a força em casa do card de marketing mudou
}
