// Página do jogador: ficha, mercado e game log.

import { $, esconderTudo, estado, limparAviso, pedir, voltarUm } from "./nucleo.js";
import { dinheiro, ligarLinks, tabela } from "./tabelas.js";
import { minutoFmt } from "./partida.js";

// ---------- visão jogador ----------

export const COLS_GAMELOG = [
  ["rodada", "R"], ["adversario", "Adversário"], ["mando", "Local"],
  ["placar", "Placar"], ["resultado", "Res."], ["atuacao", "Atuação"],
  ["gols", "G"], ["assistencias", "A"], ["nota", "Nota"],
];

export async function abrirJogador(jogadorId) {
  limparAviso();
  const d = await pedir(`/simulacoes/${estado.simId}/jogadores/${jogadorId}`);
  if (!d) return;

  estado.jogadorAtualId = Number(jogadorId);
  esconderTudo();
  $("jogador").hidden = false;

  const j = d.jogador;
  $("jogador-nome").textContent = j.nome;
  const penas = j.penaltis + j.penaltis_perdidos
    ? ` · pênaltis ${j.penaltis}/${j.penaltis + j.penaltis_perdidos}`
    : "";
  $("jogador-info").textContent =
    `${j.clube} · ${j.posicao} · OVR ${j.overall} · ${j.idade} anos · ` +
    `${j.partidas}J ${j.gols}G ${j.assistencias}A · nota média ${j.nota_media} · ` +
    `melhor ${j.melhor_nota} · ${j.melhor_em_campo}x melhor em campo · ` +
    `🟨 ${j.amarelos} 🟥 ${j.vermelhos} · ${j.faltas} faltas${penas}`;
  // saves anteriores à v0.7 não têm dados de mercado (vêm zerados)
  $("jogador-mercado").textContent = j.valor_mercado
    ? `💰 Valor ${dinheiro(j.valor_mercado)} · salário ${dinheiro(j.salario)}/temporada · ` +
      `potencial ${j.potencial} · contrato: ${j.contrato_anos} ` +
      `temporada${j.contrato_anos === 1 ? "" : "s"}`
    : "";

  const linhas = d.jogos.map((g) => ({
    partida_id: g.partida_id,
    rodada: g.rodada,
    adversario: g.adversario,
    mando: g.mando === "casa" ? "Casa" : "Fora",
    placar: `${g.gols_pro} x ${g.gols_contra}`,
    resultado: g.resultado,
    atuacao: g.titular ? "Titular" : `entrou ${minutoFmt(g.entrou_min)}'`,
    gols: g.gols,
    assistencias: g.assistencias,
    nota: g.nota,
  }));
  $("jogador-log").innerHTML = linhas.length
    ? tabela(linhas, COLS_GAMELOG)
    : `<p class="vazio">Não entrou em campo nesta temporada.</p>`;
  ligarLinks($("jogador-log"));
}

document
  .querySelectorAll("[data-voltar]")
  .forEach((b) => b.addEventListener("click", voltarUm));
