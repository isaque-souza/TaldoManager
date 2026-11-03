// As copas (v1.6; v2.6, várias): a Copa entre as ligas (os 8 melhores de
// cada Série A) e a copa nacional de cada país (os 20 da A e os 12 melhores
// da B), em mata-mata no meio da semana. Aqui só se mostra: o card do hub, o
// chaveamento de cada copa (uma aba para cada) e os jogos da copa no
// resultado da rodada. O jogo do técnico na copa (v2.0) é na quarta, com
// pré-jogo e transmissão como os da liga (rodada.js / aovivo.js).

import { $, estado, pedir } from "./nucleo.js";
import { escudo } from "./identidade.js";
import { icone } from "./icones.js";
import { reais, tabela } from "./tabelas.js";
import { nomeLiga } from "./ligas.js";

const SIGLA_LIGA = { taldo: "TAL", premier: "PL", taldo_b: "TAL B", championship: "CHA", laliga: "LL", segunda: "LL2",
  brasileirao: "BR", brasileirao_b: "BR B" };
const ESTADOS = {
  vivo: ["Na copa", "chip-batida"],
  eliminado: ["Eliminado", "chip-longe"],
  campeao: ["Campeão", "chip-batida"],
  fora: ["Fora da copa", ""],
};

// "caiu nas oitavas", "está na semifinal"
const NA_FASE = {
  "16-avos": "nos 16 avos", oitavas: "nas oitavas", quartas: "nas quartas", semi: "na semifinal", final: "na final",
};

// copas: todas (as do técnico primeiro); aba: o id da copa aberta
const cp = { copas: [], aba: null };

export async function carregarCopa() {
  if (!estado.simId) return;
  const dados = await pedir(`/simulacoes/${estado.simId}/copa`);
  if (!dados) return;
  cp.copas = dados.copas || (dados.copa ? [dados.copa] : []);
  if (!cp.copas.some((c) => c.id === cp.aba)) cp.aba = cp.copas[0]?.id ?? null;
  renderHubCopa();
  renderCopa();
}

// a copa que o card do hub mostra: a do próximo jogo do técnico; senão,
// uma em que ele ainda está vivo; senão, a primeira dele
function copaDoHub() {
  const dele = cp.copas.filter((c) => c.seu_clube.estado !== "fora");
  const vivas = dele.filter((c) => c.seu_clube.estado === "vivo")
    .sort((a, b) => depoisDa(a) - depoisDa(b));
  return vivas[0] || dele[0] || cp.copas[0] || null;
}

function depoisDa(c) {
  const f = c.fases.find((x) => x.fase === c.seu_clube.fase);
  return f ? f.depois_da_rodada : 99;
}

const meu = () => estado.rodadaInfo && estado.rodadaInfo.clube_usuario;
const mando = (m) => (m === "casa" ? "em casa" : "fora");

function renderHubCopa() {
  const c = copaDoHub();
  const card = $("hub-copa").closest(".hub-card");
  // save só da Taldo: sem a faixa da copa no card do jogo
  card.hidden = !c;
  if (!c) return;

  const s = c.seu_clube;
  const fase = s.fase && c.fases.find((f) => f.fase === s.fase);
  let titulo, info;
  if (s.estado === "campeao") {
    titulo = "Campeão!";
    info = `a ${c.nome} é sua nesta temporada`;
  } else if (s.estado === "eliminado") {
    titulo = "Eliminado";
    info = `${c.nome}: caiu ${NA_FASE[s.fase]}` +
      (c.campeao ? ` · campeão: ${c.campeao}` : "");
  } else if (s.estado === "fora") {
    titulo = "Fora da copa";
    info = c.campeao
      ? `${c.nome} · campeão: ${c.campeao}`
      : "só os 8 melhores de cada Série A jogam";
  } else {
    titulo = `${c.nome} · ${fase.nome}`;
    info = s.jogo
      ? `x ${s.jogo.adversario} (${mando(s.jogo.mando)}) · depois da rodada ${fase.depois_da_rodada}`
      : `adversário a definir · depois da rodada ${fase.depois_da_rodada}`;
  }
  $("hub-copa").textContent = titulo;
  $("hub-copa-info").textContent = info;
  card.classList.toggle("hub-ouro", s.estado === "campeao");
}

// ---------- chaveamento ----------

function linhaTime(nome, liga, gols, venceu, decidido) {
  if (!nome) {
    return `<div class="cp-time cp-vago"><span class="cp-nome">A definir</span></div>`;
  }
  const classes = ["cp-time"];
  if (decidido) classes.push(venceu ? "cp-venceu" : "cp-perdeu");
  if (nome === meu()) classes.push("eu");
  return `<div class="${classes.join(" ")}">
      ${escudo(nome, 18)}
      <span class="cp-nome" title="${nome}">${nome}</span>
      <abbr class="cp-liga" title="${nomeLiga(liga)}">${SIGLA_LIGA[liga] || ""}</abbr>
      <b class="cp-gols">${gols ?? ""}</b>
    </div>`;
}

function cardJogo(j) {
  const decidido = !!j.vencedor;
  const penaltis = j.penaltis
    ? `<small class="cp-penaltis">pênaltis ${j.penaltis[0]} x ${j.penaltis[1]}</small>`
    : "";
  return `<article class="cp-jogo">
      ${linhaTime(j.mandante, j.liga_mandante, j.gols_mandante, j.vencedor === j.mandante, decidido)}
      ${linhaTime(j.visitante, j.liga_visitante, j.gols_visitante, j.vencedor === j.visitante, decidido)}
      ${penaltis}
    </article>`;
}

function colunaFase(f, i, fases) {
  // fase ainda sem confrontos: os lugares vazios mantêm o desenho da chave
  const vagos = Math.max(1, fases[0].jogos.length >> i);
  const jogos = f.jogos.length
    ? f.jogos.map(cardJogo).join("")
    : Array.from({ length: vagos }, () => cardJogo({})).join("");
  return `<section class="cp-fase">
      <header>
        <h3 class="secao">${f.nome}</h3>
        <small>depois da rodada ${f.depois_da_rodada}</small>
        <small>${reais(f.premio)} por vitória</small>
      </header>
      <div class="cp-jogos">${jogos}</div>
    </section>`;
}

function topo(c) {
  const s = c.seu_clube;
  const [rotulo, classe] = ESTADOS[s.estado];
  const fase = s.fase && c.fases.find((f) => f.fase === s.fase);
  let texto;
  if (s.estado === "vivo" && s.jogo) {
    texto = `${fase.nome}: ${meu()} x ${s.jogo.adversario}, ${mando(s.jogo.mando)}, no meio da semana depois da rodada ${fase.depois_da_rodada}.`;
  } else if (s.estado === "vivo") {
    texto = `Você está ${NA_FASE[s.fase]}; o adversário sai da fase anterior.`;
  } else if (s.estado === "eliminado") {
    texto = `${s.jogo.adversario} tirou você ${NA_FASE[s.fase]}.`;
  } else if (s.estado === "campeao") {
    texto = `A ${c.nome} é sua!`;
  } else if (c.tipo === "nacional") {
    texto = "Os 20 da Série A e os 12 melhores da Série B na temporada anterior disputam a copa. Suba na tabela da B para entrar na próxima.";
  } else {
    texto = "Os 8 melhores de cada Série A na temporada anterior disputam a copa. Termine entre os 8 para entrar na próxima.";
  }
  const campeao = c.campeao
    ? `<p class="cp-campeao">${icone("trofeu")} ${escudo(c.campeao, 22)} <strong>${c.campeao}</strong> é o campeão da ${c.nome}</p>`
    : "";
  return `<div class="cp-topo">
      <p><span class="chip ${classe}">${rotulo}</span> ${texto}</p>
      ${campeao}
    </div>`;
}

const REGRA = {
  continental: "Na primeira fase, nunca dois clubes da mesma liga; joga em casa quem foi melhor na sua liga.",
  nacional: "Joga em casa quem foi melhor na temporada anterior (os da Série A antes dos da B).",
};

function abas() {
  if (cp.copas.length < 2) return "";
  return `<nav class="abas cp-abas" aria-label="Copas">${cp.copas.map((c) => {
    const s = c.seu_clube.estado;
    const marca = s === "fora" ? "" : ` <span class="chip ${ESTADOS[s][1]}">${ESTADOS[s][0]}</span>`;
    return `<button type="button" data-copa="${c.id}" class="${c.id === cp.aba ? "ativa" : ""}">${c.nome}${marca}</button>`;
  }).join("")}</nav>`;
}

function renderCopa() {
  const c = cp.copas.find((x) => x.id === cp.aba);
  if (!c) {
    $("r-copa").innerHTML = "";
    return;
  }
  $("r-copa").innerHTML = `${abas()}
    <h2 class="cp-titulo">${icone("trofeu")} ${c.nome}</h2>
    ${topo(c)}
    <p class="cp-regra">Mata-mata em jogo único, com pênaltis no empate.
      ${REGRA[c.tipo] || ""} Gols e cartões da copa não contam na liga, mas o
      cansaço e as lesões, sim.</p>
    <div class="cp-chave" style="--fases:${c.fases.length}">${c.fases.map(colunaFase).join("")}</div>`;
  $("r-copa").querySelectorAll("[data-copa]").forEach((b) =>
    b.addEventListener("click", () => { cp.aba = b.dataset.copa; renderCopa(); }));
}

// ---------- resultado da rodada ----------

export function renderCopaDaRodada(alvo, copaDaRodada, clube) {
  if (!copaDaRodada) {
    alvo.innerHTML = "";
    return;
  }
  const linhas = copaDaRodada.jogos.map((j) => ({
    mandante: j.mandante,
    placar: `${j.gols_mandante} x ${j.gols_visitante}` +
      (j.penaltis ? ` (pên. ${j.penaltis[0]} x ${j.penaltis[1]})` : ""),
    visitante: j.visitante,
  }));
  const marcarEu = (r) => (r.mandante === clube || r.visitante === clube ? "eu" : "");
  alvo.innerHTML = `<h3 class="secao" style="margin-top: 1.5rem">${icone("trofeu")} ${copaDaRodada.nome}</h3>
    ${tabela(linhas, [["mandante", "Mandante"], ["placar", "Placar"], ["visitante", "Visitante"]], marcarEu)}`;
}
