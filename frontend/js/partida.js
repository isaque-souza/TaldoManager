// Página da partida: estatísticas, linha do tempo e escalações.

import { $, esconderTudo, estado, limparAviso, pedir } from "./nucleo.js";
import { ligarLinks, tabela } from "./tabelas.js";
import { comEscudo, escudo } from "./identidade.js";
import { cartao, icone } from "./icones.js";

// ---------- visão partida ----------

export const ICONE_EVENTO = {
  gol: icone("gol", "gol"), penalti: `${icone("gol", "gol de pênalti")} (P)`,
  penalti_perdido: `${icone("nao", "pênalti perdido")} (P)`,
  penalti_defendido: `${icone("luva", "pênalti defendido")} (P)`,
  chute_fora: icone("fora", "chute para fora"),
  cartao_amarelo: cartao(), expulsao: cartao("vermelho"),
  substituicao: icone("troca", "substituição"), lesao: icone("lesao", "lesão"),
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
  $("partida-placar").innerHTML =
    `<span class="placar">${escudo(p.mandante.nome, 36)} ${p.mandante.nome}` +
    ` <b>${p.gols_mandante} x ${p.gols_visitante}</b> ${p.visitante.nome} ${escudo(p.visitante.nome, 36)}</span>`;
  // público (v1.5); partidas de antes do estádio não têm
  $("partida-info").textContent = p.publico
    ? `Rodada ${p.rodada} · público ${p.publico.toLocaleString("pt-BR")}`
    : `Rodada ${p.rodada}`;

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

  $("esc-mandante-titulo").innerHTML = comEscudo(p.mandante.nome, p.mandante.nome, 22);
  $("esc-visitante-titulo").innerHTML = comEscudo(p.visitante.nome, p.visitante.nome, 22);
  $("esc-mandante").innerHTML =
    tabela(prepararEscalacao(d.escalacao_mandante), COLS_ESCALACAO);
  $("esc-visitante").innerHTML =
    tabela(prepararEscalacao(d.escalacao_visitante), COLS_ESCALACAO);
  ligarLinks($("esc-mandante"));
  ligarLinks($("esc-visitante"));
}
