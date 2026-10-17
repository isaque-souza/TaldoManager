// Visão da temporada: abas de classificação, rankings e recordes.

import { $, esconderTudo, estado, voltarUm } from "./nucleo.js";
import { ligarLinks, tabela } from "./tabelas.js";
import { ligarEvolucao, renderEvolucao } from "./grafico.js";

// ---------- visão temporada ----------

export const COLUNAS = {
  classificacao: [
    ["posicao", "#"], ["clube", "Clube"], ["pontos", "P"], ["jogos", "J"],
    ["vitorias", "V"], ["empates", "E"], ["derrotas", "D"],
    ["gols_marcados", "GP"], ["gols_sofridos", "GC"], ["saldo_gols", "SG"],
    ["forma", "Forma"],
  ],
  artilharia: [
    ["nome", "Jogador"], ["clube", "Clube"], ["gols", "Gols"],
    ["assistencias", "Assist."], ["nota_media", "Nota"],
  ],
  assistencias: [
    ["nome", "Jogador"], ["clube", "Clube"], ["assistencias", "Assist."],
    ["gols", "Gols"], ["nota_media", "Nota"],
  ],
  melhores_notas: [
    ["nome", "Jogador"], ["clube", "Clube"], ["posicao", "Posição"],
    ["nota_media", "Média"], ["melhor_nota", "Melhor nota"], ["partidas", "Jogos"],
  ],
  clean_sheets: [
    ["nome", "Goleiro"], ["clube", "Clube"], ["clean_sheets", "CS"],
    ["nota_media", "Nota"],
  ],
  hat_tricks: [
    ["nome", "Jogador"], ["clube", "Clube"], ["hat_tricks", "Hat-tricks"],
    ["gols", "Gols"],
  ],
  disciplina: [
    ["nome", "Jogador"], ["clube", "Clube"], ["vermelhos", "🟥"],
    ["amarelos", "🟨"], ["faltas", "Faltas"], ["partidas", "Jogos"],
  ],
  penaltis: [
    ["nome", "Jogador"], ["clube", "Clube"], ["penaltis", "Convertidos"],
    ["penaltis_perdidos", "Perdidos"], ["gols", "Gols"],
  ],
};

export const ABAS = [
  ["classificacao", "Classificação"], ["evolucao", "Evolução"],
  ["artilharia", "Artilharia"], ["assistencias", "Assistências"],
  ["melhores_notas", "Notas"], ["clean_sheets", "Clean Sheets"],
  ["hat_tricks", "Hat-tricks"], ["disciplina", "Disciplina"],
  ["penaltis", "Pênaltis"], ["historico", "Histórico"],
  ["recordes", "Recordes"],
];

export function renderPainel() {
  const painel = $("painel");
  if (estado.abaAtual === "historico") {
    painel.innerHTML = `<figure><table><tbody>${estado.temporada.historico
      .map((l) => `<tr><td>${l}</td></tr>`)
      .join("")}</tbody></table></figure>`;
    return;
  }
  if (estado.abaAtual === "recordes") {
    const r = estado.temporada.recordes;
    painel.innerHTML = `<ul>
      <li><strong>Maior goleada:</strong> ${r.maior_goleada.partida} (${r.maior_goleada.valor} de diferença)</li>
      <li><strong>Mais gols numa partida:</strong> ${r.mais_gols_jogo.partida} (${r.mais_gols_jogo.valor} gols)</li>
    </ul>`;
    return;
  }
  if (estado.abaAtual === "evolucao") {
    painel.innerHTML = renderEvolucao();
    ligarEvolucao(painel);
    return;
  }
  const marcarEu =
    estado.abaAtual === "classificacao" && estado.temporada.clube_usuario
      ? (c) => (c.clube === estado.temporada.clube_usuario ? "eu" : "")
      : undefined;
  painel.innerHTML = tabela(estado.temporada[estado.abaAtual], COLUNAS[estado.abaAtual], marcarEu);
  ligarLinks(painel);
}

export function renderAbas() {
  $("abas").innerHTML = ABAS.map(
    ([k, rot]) =>
      `<button data-aba="${k}" class="${k === estado.abaAtual ? "ativa" : ""}">${rot}</button>`
  ).join("");
  $("abas").querySelectorAll("button").forEach((b) =>
    b.addEventListener("click", () => {
      estado.abaAtual = b.dataset.aba;
      renderAbas();
      renderPainel();
    })
  );
}

export function mostrarTemporada() {
  esconderTudo();
  $("temporada").hidden = false;

  const emAndamento = estado.temporada.estado === "em_andamento";
  $("temporada-voltar").hidden = !emAndamento;

  const campeao = estado.temporada.classificacao[0];
  $("campeao").textContent = emAndamento
    ? `${campeao.clube} (líder)`
    : estado.temporada.campeao;
  $("campeao-info").textContent =
    (emAndamento ? `rodada ${estado.temporada.rodada_atual} de ${estado.temporada.rodadas} · ` : "") +
    `${campeao.pontos} pts · ${campeao.vitorias}V ${campeao.empates}E ${campeao.derrotas}D · saldo ${campeao.saldo_gols}`;

  const mvp = estado.temporada.mvp;
  $("mvp").textContent = mvp ? mvp.nome : "—";
  $("mvp-info").textContent = mvp
    ? `${mvp.clube} · ${mvp.posicao} · nota média ${mvp.nota_media} · ${mvp.melhor_em_campo}x melhor em campo`
    : "";

  const meu = estado.temporada.clube_usuario;
  const resumo = $("meu-resumo");
  resumo.hidden = !meu;
  if (meu) {
    const c = estado.temporada.classificacao.find((x) => x.clube === meu);
    const form = estado.temporada.formacao ? `, ${estado.temporada.formacao}` : "";
    const verbo = emAndamento ? "está em" : "terminou em";
    resumo.innerHTML =
      `🎮 Você dirige <strong>${meu}</strong> (${estado.temporada.tatica}${form}) — ` +
      `${verbo} <strong>${c.posicao}º</strong> com ${c.pontos} pts, ` +
      `${c.gols_marcados} gols pró e ${c.gols_sofridos} sofridos.`;
  }

  renderAbas();
  renderPainel();
}

$("temporada-voltar").addEventListener("click", voltarUm);
