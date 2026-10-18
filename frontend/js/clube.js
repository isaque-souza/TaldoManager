// Página do clube: finanças, jogos e elenco.

import { $, esconderTudo, estado, limparAviso, pedir } from "./nucleo.js";
import { dinheiro, ligarLinks, tabela } from "./tabelas.js";
import { renderDashboard } from "./financas.js";
import { camisa, escudo } from "./identidade.js";
import { seloIdolo } from "./icones.js";

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
  $("clube-nome").innerHTML =
    `<span class="titulo-clube">${escudo(cl.nome, 44)}${camisa(cl.nome, { tamanho: 44 })}${cl.nome}</span>`;
  $("clube-info").textContent =
    `${cl.posicao_final}º lugar · ${cl.pontos} pts · ${cl.vitorias}V ${cl.empates}E ${cl.derrotas}D · ` +
    `${cl.gols_marcados}-${cl.gols_sofridos} (saldo ${cl.saldo_gols})`;
  // ídolos da torcida (v1.4)
  const idolos = c.elenco.filter((j) => j.idolo);
  $("clube-idolos").innerHTML = idolos.length
    ? `${seloIdolo()} Ídolos da torcida: ` +
      idolos.map((j) => `<a class="jogador" data-jogador="${j.id}">${j.nome}</a>`).join(", ")
    : "";
  ligarLinks($("clube-idolos"));
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
