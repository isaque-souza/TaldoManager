// Núcleo: estado compartilhado, navegação (← Voltar) e rede.

import { mostrarTemporada } from "./temporada.js";
import { mostrarRodadaTela } from "./rodada.js";
import { abrirClube } from "./clube.js";
import { abrirPartida } from "./partida.js";
import { abrirJogador } from "./jogador.js";
import { mostrarCarreira } from "./carreira.js";

export function $(id) { return document.getElementById(id); }
export function api() { return $("api").value.replace(/\/$/, ""); }

// estado compartilhado entre as telas (um objeto: módulos não
// podem reatribuir variáveis importadas de outro módulo)
export const estado = {
  temporada: null,   // payload da simulação aberta
  simId: null,
  abaAtual: "classificacao",
  clubeAtualId: null,
  partidaAtualId: null,
  jogadorAtualId: null,
  rodadaInfo: null,   // payload de /rodadas/proxima
  rodadaResultado: null,   // payload de POST /rodadas
  faseRodada: "antes",   // "antes" | "depois"
  abaRodada: "partida",   // aba da tela antes da rodada
  elencoClube: null,   // { elenco, formacoes } do clube escolhido
  carreira: null,   // payload de /carreiras/{id} (tela da carreira)
};
export const pilhaVoltar = [];   // thunks para o botão "← Voltar"

export const SECOES = ["temporada", "rodada", "clube", "partida", "jogador", "carreira"];

export function esconderTudo() {
  SECOES.forEach((id) => ($(id).hidden = true));
}

export function secaoVisivel() {
  return SECOES.find((id) => !$(id).hidden);
}

// thunk que reabre exatamente a tela visível agora
export function thunkAtual() {
  switch (secaoVisivel()) {
    case "clube": return () => abrirClube(estado.clubeAtualId);
    case "partida": return () => abrirPartida(estado.partidaAtualId);
    case "jogador": return () => abrirJogador(estado.jogadorAtualId);
    case "rodada": return () => mostrarRodadaTela();
    case "carreira": return () => mostrarCarreira();
    default: return () => mostrarTemporada();
  }
}

export function navegarPara(fn) {
  pilhaVoltar.push(thunkAtual());
  fn();
}

export function voltarUm() {
  const fn = pilhaVoltar.pop();
  (fn || mostrarTemporada)();
}

// ---------- rede ----------

export function limparAviso() { $("erro").textContent = ""; }

export function ocupado(ligado, texto = "") {
  $("status").setAttribute("aria-busy", ligado ? "true" : "false");
  $("status").textContent = texto;
  $("nova").disabled = ligado;
}

export async function pedir(caminho, opcoes) {
  try {
    const resp = await fetch(api() + caminho, opcoes);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return resp.status === 204 ? true : await resp.json();
  } catch (e) {
    $("erro").textContent =
      `Falha em ${caminho} — ${e.message}. A API está rodando? (uvicorn app.main:app --reload)`;
    return null;
  }
}
