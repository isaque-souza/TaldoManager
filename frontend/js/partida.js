// Página da partida: estatísticas, linha do tempo e escalações.

import { $, esconderTudo, estado, limparAviso, pedir } from "./nucleo.js";
import { ligarLinks, tabela } from "./tabelas.js";

// ---------- visão partida ----------

export const ICONE_EVENTO = {
  gol: "⚽", penalti: "⚽ (P)", penalti_perdido: "❌ (P)",
  penalti_defendido: "🧤 (P)", chute_fora: "💨",
  cartao_amarelo: "🟨", expulsao: "🟥", substituicao: "🔄", lesao: "🚑",
};

// minuto 93 -> "90+3"
export const minutoFmt = (m) => (m > 90 ? `90+${m - 90}` : `${m}`);

export const COLS_ESCALACAO = [
  ["nome", "Jogador"], ["posicao", "Pos."], ["entrou", "Entrou"],
  ["saiu", "Saiu"], ["gols", "G"], ["assistencias", "A"], ["nota", "Nota"],
];

export function linhaEvento(e) {
  const icone = ICONE_EVENTO[e.tipo] || "•";
  const quem =
    e.jogador_id != null
      ? `<a class="jogador" data-jogador="${e.jogador_id}">${e.jogador}</a>`
      : e.jogador || "";
  const detalhe = e.detalhe ? ` <small>(${e.detalhe})</small>` : "";
  return `<li><strong>${minutoFmt(e.minuto)}&#39;</strong> ${icone} ${quem} <small class="vazio">${e.clube || ""}</small>${detalhe}</li>`;
}

export function prepararEscalacao(lista) {
  return lista.map((a) => ({
    id: a.jogador_id,
    nome: a.jogador,
    posicao: a.posicao,
    entrou: a.titular ? "Titular" : `${minutoFmt(a.entrou_min)}'`,
    saiu: a.saiu_min != null ? `${minutoFmt(a.saiu_min)}'` : "—",
    gols: a.gols,
    assistencias: a.assistencias,
    nota: a.nota,
  }));
}

export async function abrirPartida(partidaId) {
  limparAviso();
  const d = await pedir(`/simulacoes/${estado.simId}/partidas/${partidaId}`);
  if (!d) return;

  estado.partidaAtualId = Number(partidaId);
  esconderTudo();
  $("partida").hidden = false;

  const p = d.partida;
  $("partida-placar").textContent =
    `${p.mandante.nome} ${p.gols_mandante} x ${p.gols_visitante} ${p.visitante.nome}`;
  $("partida-info").textContent = `Rodada ${p.rodada}`;

  const stat = (rot, a, b) =>
    `<article><header><strong>${rot}</strong></header>${a} &nbsp;—&nbsp; ${b}</article>`;
  $("partida-stats").innerHTML =
    stat("Posse de bola", `${p.posse_mandante}%`, `${p.posse_visitante}%`) +
    stat("Finalizações", p.finalizacoes_mandante, p.finalizacoes_visitante) +
    stat("Chutes no gol", p.finalizacoes_gol_mandante, p.finalizacoes_gol_visitante) +
    stat("Escanteios", p.escanteios_mandante, p.escanteios_visitante);

  // chute pra fora conta nas finalizações, mas polui a timeline
  const lances = d.eventos.filter((e) => e.tipo !== "chute_fora");
  $("partida-timeline").innerHTML = lances.length
    ? `<ul class="timeline">${lances.map(linhaEvento).join("")}</ul>`
    : `<p class="vazio">Sem lances registrados.</p>`;
  ligarLinks($("partida-timeline"));

  $("esc-mandante-titulo").textContent = p.mandante.nome;
  $("esc-visitante-titulo").textContent = p.visitante.nome;
  $("esc-mandante").innerHTML =
    tabela(prepararEscalacao(d.escalacao_mandante), COLS_ESCALACAO);
  $("esc-visitante").innerHTML =
    tabela(prepararEscalacao(d.escalacao_visitante), COLS_ESCALACAO);
  ligarLinks($("esc-mandante"));
  ligarLinks($("esc-visitante"));
}
