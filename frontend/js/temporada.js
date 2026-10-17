// Visão da temporada: abas de classificação, rankings e recordes.

import { $, esconderTudo, estado, limparAviso, navegarPara, ocupado, pedir, voltarUm } from "./nucleo.js";
import { carregarLista } from "./saves.js";
import { dinheiro, ligarLinks, tabela } from "./tabelas.js";
import { ligarEvolucao, renderEvolucao } from "./grafico.js";
import { abrirCarreira, renderVirada } from "./carreira.js";
import { renderMeta } from "./diretoria.js";

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
  ["financas", "Finanças"],
  ["artilharia", "Artilharia"], ["assistencias", "Assistências"],
  ["melhores_notas", "Notas"], ["clean_sheets", "Clean Sheets"],
  ["hat_tricks", "Hat-tricks"], ["disciplina", "Disciplina"],
  ["penaltis", "Pênaltis"], ["historico", "Histórico"],
  ["recordes", "Recordes"],
];

// abas da temporada aberta: a "Virada" só existe da temporada 2 em diante
export function abasDaTemporada() {
  return estado.temporada.movimentos_virada?.length
    ? [...ABAS, ["virada", "Virada"]]
    : ABAS;
}

export function renderPainel() {
  const painel = $("painel");
  if (estado.abaAtual === "virada") {
    painel.innerHTML = renderVirada();
    return;
  }
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
    ["classificacao", "financas"].includes(estado.abaAtual) && estado.temporada.clube_usuario
      ? (c) => (c.clube === estado.temporada.clube_usuario ? "eu" : "")
      : undefined;
  if (estado.abaAtual === "financas") {
    painel.innerHTML = tabelaFinancasLiga(estado.temporada.financas || [], marcarEu);
    ligarLinks(painel);
    return;
  }
  painel.innerHTML = tabela(estado.temporada[estado.abaAtual], COLUNAS[estado.abaAtual], marcarEu);
  ligarLinks(painel);
}

// caixa, folha e saldo dos 20 clubes (na ordem da classificação)
export function tabelaFinancasLiga(financas, marcarEu) {
  if (!financas.some((f) => f.caixa_inicial)) {
    return `<p class="vazio">Este save é anterior às finanças (v0.7).</p>`;
  }
  const linhas = financas.map((f) => ({
    ...f,
    ini: dinheiro(f.caixa_inicial),
    rec: dinheiro(f.receitas),
    desp: dinheiro(f.despesas),
    sld: `<span class="${f.saldo < 0 ? "negativo" : ""}">${f.saldo > 0 ? "+" : ""}${dinheiro(f.saldo)}</span>`,
    cx: `<span class="${f.caixa < 0 ? "negativo" : ""}">${dinheiro(f.caixa)}</span>`,
    fol: dinheiro(f.folha),
  }));
  return tabela(linhas, [
    ["posicao", "#"], ["clube", "Clube"], ["ini", "Caixa inicial"], ["rec", "Receitas"],
    ["desp", "Despesas"], ["sld", "Saldo"], ["cx", "Caixa atual"], ["fol", "Folha/temp."],
  ], marcarEu);
}

export function renderAbas() {
  $("abas").innerHTML = abasDaTemporada().map(
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
    (estado.temporada.carreira_id ? `temporada ${estado.temporada.temporada} · ` : "") +
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

  renderMeta("meta-diretoria", estado.temporada);
  renderCarreira(emAndamento, meu);
  renderAbas();
  renderPainel();
}

// ---------- modo carreira (v0.8) ----------

// Temporada concluída com clube dirigido: continua na próxima (ou leva até
// ela, se já foi continuada — só a última temporada da carreira continua).
// O botão "📜 Carreira" aparece em toda temporada de uma carreira.
function renderCarreira(emAndamento, meu) {
  const acao = $("carreira-acao");
  const t = estado.temporada;
  const podeContinuar = !emAndamento && meu;
  acao.hidden = !podeContinuar && !t.carreira_id;
  if (acao.hidden) return;

  const proxima = (t.temporada ?? 1) + 1;
  const continuar = !podeContinuar ? ""
    : t.proxima_temporada_id
      ? `<button id="carreira-ir" class="secondary">Ir para a temporada ${proxima} →</button>`
      : `<button id="carreira-continuar">▶ Próxima temporada (temporada ${proxima})</button>`;
  const verCarreira = t.carreira_id
    ? `<button id="carreira-ver" class="secondary outline">📜 Carreira</button>`
    : "";
  const dica = podeContinuar && !t.proxima_temporada_id
    ? `<small>Elencos, contratos e caixa continuam; pontos e estatísticas começam do zero.</small>`
    : "";
  acao.innerHTML = `<span class="botoes-carreira">${continuar}${verCarreira}</span>${dica}`;

  $("carreira-ir")?.addEventListener("click", () => carregarLista(t.proxima_temporada_id));
  $("carreira-continuar")?.addEventListener("click", continuarCarreira);
  $("carreira-ver")?.addEventListener("click", () =>
    navegarPara(() => abrirCarreira(t.carreira_id))
  );
}

async function continuarCarreira() {
  limparAviso();
  ocupado(true, "Preparando a próxima temporada…");
  const criada = await pedir(`/simulacoes/${estado.simId}/proxima-temporada`, { method: "POST" });
  ocupado(false);
  if (criada) await carregarLista(criada.simulacao_id);
}

$("temporada-voltar").addEventListener("click", voltarUm);
