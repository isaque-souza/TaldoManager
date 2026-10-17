// Página do clube: finanças, jogos e elenco.

import { $, esconderTudo, estado, limparAviso, pedir } from "./nucleo.js";
import { dinheiro, ligarLinks, tabela } from "./tabelas.js";
import { renderDashboard } from "./financas.js";

// ---------- visão clube ----------

export const COLS_JOGOS = [
  ["rodada", "R"], ["adversario", "Adversário"], ["mando", "Local"],
  ["placar", "Placar"], ["resultado", "Res."],
];
export const COLS_ELENCO = [
  ["nome", "Jogador"], ["posicao", "Posição"], ["overall", "OVR"],
  ["partidas", "Jogos"], ["gols", "Gols"], ["assistencias", "Assist."],
  ["nota_media", "Nota"], ["melhor_em_campo", "MVPs"], ["valor", "Valor"],
];

export async function abrirClube(clubeId) {
  limparAviso();
  const c = await pedir(`/simulacoes/${estado.simId}/clubes/${clubeId}`);
  if (!c) return;

  estado.clubeAtualId = Number(clubeId);
  esconderTudo();
  $("clube").hidden = false;

  const cl = c.clube;
  $("clube-nome").textContent = cl.nome;
  $("clube-info").textContent =
    `${cl.posicao_final}º lugar · ${cl.pontos} pts · ${cl.vitorias}V ${cl.empates}E ${cl.derrotas}D · ` +
    `${cl.gols_marcados}-${cl.gols_sofridos} (saldo ${cl.saldo_gols})`;
  renderDashboard($("clube-financas"), cl, c.elenco);

  const jogos = c.jogos.map((j) => ({
    ...j,
    mando: j.mando === "casa" ? "Casa" : "Fora",
    placar: `${j.gols_pro} x ${j.gols_contra}`,
  }));
  $("clube-jogos").innerHTML = tabela(jogos, COLS_JOGOS);
  $("clube-elenco").innerHTML = tabela(
    c.elenco.map((j) => ({ ...j, valor: j.valor_mercado ? dinheiro(j.valor_mercado) : "—" })),
    COLS_ELENCO,
  );
  ligarLinks($("clube-jogos"));
  ligarLinks($("clube-elenco"));
}
