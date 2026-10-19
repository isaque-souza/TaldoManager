// Copa entre as ligas (v1.6): 16 clubes (8 de cada liga) em mata-mata, no
// meio da semana depois das rodadas 8, 17, 26 e 35. Aqui só se mostra: o
// card do hub, o chaveamento e os jogos da copa no resultado da rodada. O
// jogo do técnico na copa é simulado junto com a rodada.

import { $, estado, pedir } from "./nucleo.js";
import { escudo } from "./identidade.js";
import { icone } from "./icones.js";
import { dinheiro, tabela } from "./tabelas.js";
import { nomeLiga } from "./ligas.js";

const SIGLA_LIGA = { taldo: "TAL", premier: "PL" };
const ESTADOS = {
  vivo: ["Na copa", "chip-batida"],
  eliminado: ["Eliminado", "chip-longe"],
  campeao: ["Campeão", "chip-batida"],
  fora: ["Fora da copa", ""],
};

// "caiu nas oitavas", "está na semifinal"
const NA_FASE = {
  oitavas: "nas oitavas", quartas: "nas quartas", semi: "na semifinal", final: "na final",
};

const cp = { dados: null };

export async function carregarCopa() {
  if (!estado.simId) return;
  const dados = await pedir(`/simulacoes/${estado.simId}/copa`);
  if (!dados) return;
  cp.dados = dados.copa;
  renderHubCopa();
  renderCopa();
}

const meu = () => estado.rodadaInfo && estado.rodadaInfo.clube_usuario;
const mando = (m) => (m === "casa" ? "em casa" : "fora");

function renderHubCopa() {
  const c = cp.dados;
  const card = $("hub-copa").closest(".hub-card");
  // save só da Taldo: sem card e o hub volta à grade sem ele
  card.hidden = !c;
  $("r-hub").classList.toggle("sem-copa", !c);
  if (!c) return;

  const s = c.seu_clube;
  const fase = s.fase && c.fases.find((f) => f.fase === s.fase);
  let titulo, info;
  if (s.estado === "campeao") {
    titulo = "Campeão!";
    info = "a copa é sua nesta temporada";
  } else if (s.estado === "eliminado") {
    titulo = "Eliminado";
    info = `caiu ${NA_FASE[s.fase]}` +
      (c.campeao ? ` · campeão: ${c.campeao}` : "");
  } else if (s.estado === "fora") {
    titulo = "Fora da copa";
    info = c.campeao
      ? `campeão: ${c.campeao}`
      : "só os 8 melhores de cada liga jogam";
  } else {
    titulo = fase.nome;
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

function colunaFase(f, i) {
  // fase ainda sem confrontos: os lugares vazios mantêm o desenho da chave
  const vagos = 8 >> i;
  const jogos = f.jogos.length
    ? f.jogos.map(cardJogo).join("")
    : Array.from({ length: vagos }, () => cardJogo({})).join("");
  return `<section class="cp-fase">
      <header>
        <h3 class="secao">${f.nome}</h3>
        <small>depois da rodada ${f.depois_da_rodada}</small>
        <small>R$ ${dinheiro(f.premio)} por vitória</small>
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
    texto = "A copa é sua!";
  } else {
    texto = "Os 8 melhores de cada liga na temporada anterior disputam a copa. Termine entre os 8 para entrar na próxima.";
  }
  const campeao = c.campeao
    ? `<p class="cp-campeao">${icone("trofeu")} ${escudo(c.campeao, 22)} <strong>${c.campeao}</strong> é o campeão da copa</p>`
    : "";
  return `<div class="cp-topo">
      <p><span class="chip ${classe}">${rotulo}</span> ${texto}</p>
      ${campeao}
    </div>`;
}

function renderCopa() {
  const c = cp.dados;
  if (!c) {
    $("r-copa").innerHTML = "";
    return;
  }
  $("r-copa").innerHTML = `${topo(c)}
    <p class="cp-regra">Mata-mata em jogo único, com pênaltis no empate. Nas
      oitavas, sempre Liga Taldo x Premier League; joga em casa quem foi
      melhor na sua liga. Gols e cartões da copa não contam na liga, mas o
      cansaço e as lesões, sim.</p>
    <div class="cp-chave">${c.fases.map(colunaFase).join("")}</div>`;
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
  alvo.innerHTML = `<h3 class="secao" style="margin-top: 1.5rem">${icone("trofeu")} Copa · ${copaDaRodada.nome}</h3>
    ${tabela(linhas, [["mandante", "Mandante"], ["placar", "Placar"], ["visitante", "Visitante"]], marcarEu)}`;
}
