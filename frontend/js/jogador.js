// Página do jogador: ficha, mercado e game log.

import { $, esconderTudo, estado, limparAviso, pedir, voltarUm } from "./nucleo.js";
import { decimal, ligarLinks, reais, tabela } from "./tabelas.js";
import { minutoFmt } from "./partida.js";
import { cartao, icone, seloIdolo } from "./icones.js";
import { barrasAtributos } from "./atributos.js";
import { camisa } from "./identidade.js";

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
  window.scrollTo(0, 0);   // vindo de uma lista rolada, a página abre no topo

  const j = d.jogador;
  $("jogador-topo").innerHTML = `
    ${j.clube ? camisa(j.clube, { tamanho: 64 }) : `<span class="tr-sem-clube">${icone("assinou")}</span>`}
    <div class="jg-nome">
      <h2>${j.nome}${j.idolo ? ` ${seloIdolo()}` : ""}</h2>
      <p>${j.clube || "Sem clube"} · ${j.funcao || j.posicao} · ${j.idade} anos` +
        `${j.idolo ? " · <strong>ídolo da torcida</strong>" : ""}</p>
    </div>
    <dl class="el-notas jg-notas">
      <div><dt>OVR</dt><dd>${j.overall}</dd></div>
      ${j.potencial ? `<div><dt>POT</dt><dd class="${j.potencial > j.overall ? "sobe" : ""}">${j.potencial}</dd></div>` : ""}
    </dl>`;

  const bloco = (rotulo, valor) => `<div><dt>${rotulo}</dt><dd>${valor}</dd></div>`;
  const jogou = j.partidas > 0;
  const penas = j.penaltis + j.penaltis_perdidos;
  const temporada = [
    bloco("Jogos", j.partidas), bloco("Gols", j.gols), bloco("Assist.", j.assistencias),
    bloco("Nota média", jogou ? decimal(j.nota_media) : "—"),
    bloco("Melhor nota", jogou ? decimal(j.melhor_nota) : "—"),
    bloco("Melhor em campo", `${j.melhor_em_campo}x`),
    bloco("Cartões", `${cartao()} ${j.amarelos} ${cartao("vermelho")} ${j.vermelhos}`),
    bloco("Faltas", j.faltas),
    penas ? bloco("Pênaltis", `${j.penaltis}/${penas}`) : "",
  ].join("");
  // saves anteriores à v0.7 não têm dados de mercado (vêm zerados); a fama
  // (v1.4) vem null nos anteriores a ela
  const casa = j.temporadas_no_clube;
  const contrato = [
    j.valor_mercado ? bloco("Valor", reais(j.valor_mercado)) : "",
    j.valor_mercado ? bloco("Salário/temp.", reais(j.salario)) : "",
    j.valor_mercado ? bloco("Restam", `${j.contrato_anos} temp.`) : "",
    j.multa_rescisoria ? bloco("Multa", reais(j.multa_rescisoria)) : "",
    j.fama != null ? bloco("Fama", `${j.fama}/100`) : "",
    j.fama != null ? bloco("No clube", `${casa} temp.`) : "",
  ].join("");
  $("jogador-blocos").innerHTML = `
    <h3 class="secao">Temporada</h3>
    <dl class="jg-blocos">${temporada}</dl>
    ${contrato ? `<h3 class="secao">Contrato</h3><dl class="jg-blocos">${contrato}</dl>` : ""}`;

  $("jogador-atributos").innerHTML = barrasAtributos(j.atributos);

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
