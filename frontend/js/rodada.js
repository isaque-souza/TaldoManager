// Modo rodada a rodada: antes (escalação) e depois (resultados).

import { $, api, esconderTudo, estado, limparAviso, navegarPara, ocupado, pedir, pilhaVoltar } from "./nucleo.js";
import { ligarLinks, tabela } from "./tabelas.js";
import { COLUNAS, mostrarTemporada } from "./temporada.js";
import { carregarMercado } from "./mercado.js";
import { carregarLista } from "./saves.js";
import { renderSlots, xiEscolhido } from "./escalacao.js";
import { renderDashboard } from "./financas.js";
import { renderMeta } from "./diretoria.js";
import { escudo } from "./identidade.js";
import { icone } from "./icones.js";

// ---------- visão rodada a rodada ----------

export const COLS_ELENCO_RODADA = [
  ["nome", "Jogador"], ["posicao", "Posição"], ["overall", "OVR"],
  ["energia", "Energia"], ["situacao", "Situação"],
];

export async function carregarProximaRodada() {
  await salvarEscalacaoAgora();   // não deixa o recarregamento engolir uma mudança
  const info = await pedir(`/simulacoes/${estado.simId}/rodadas/proxima`);
  if (!info) return;
  estado.rodadaInfo = info;
  estado.rodadaResultado = null;
  estado.faseRodada = "antes";
  mostrarRodadaTela();
}

// ---------- abas da tela "antes da rodada" ----------

export const ABAS_RODADA = [
  ["partida", "camisa", "Partida"], ["mercado", "troca", "Mercado"],
  ["contratos", "contrato", "Contratos"], ["financas", "carteira", "Finanças"],
];
const selosAba = {};   // selo ao lado do rótulo: janela aberta, contratos acabando...

export function renderAbasRodada() {
  $("r-abas").innerHTML = ABAS_RODADA.map(([k, ic, rot]) =>
    `<button data-aba="${k}" class="${k === estado.abaRodada ? "ativa" : ""}">${icone(ic)} ${rot}` +
    `${selosAba[k] ? ` <small>${selosAba[k]}</small>` : ""}</button>`
  ).join("");
  $("r-abas").querySelectorAll("button").forEach((b) =>
    b.addEventListener("click", () => {
      estado.abaRodada = b.dataset.aba;
      renderAbasRodada();
      if (estado.abaRodada === "financas") carregarFinancasRodada();
    })
  );
  document.querySelectorAll("#rodada-antes [data-painel]").forEach((p) => {
    p.hidden = p.dataset.painel !== estado.abaRodada;
  });
}

export function marcarAbasRodada(selos) {
  Object.assign(selosAba, selos);
  renderAbasRodada();
}

export async function carregarFinancasRodada() {
  const meu = estado.rodadaInfo && estado.rodadaInfo.clube_usuario;
  const linha = estado.temporada && estado.temporada.classificacao.find((c) => c.clube === meu);
  if (!linha) return;
  const c = await pedir(`/simulacoes/${estado.simId}/clubes/${linha.id}`);
  if (c) renderDashboard($("r-financas"), c.clube, c.elenco);
}

export function mostrarRodadaTela() {
  esconderTudo();
  $("rodada").hidden = false;
  renderMeta("r-meta", estado.temporada);
  if (estado.faseRodada === "depois") renderRodadaDepois();
  else renderRodadaAntes();
}

export function renderRodadaAntes() {
  const info = estado.rodadaInfo;
  if (info.concluida) {   // temporada já terminou — cai na visão completa
    mostrarTemporada();
    return;
  }
  $("rodada-antes").hidden = false;
  $("rodada-depois").hidden = true;

  $("rodada-titulo").textContent =
    `Rodada ${info.rodada} de ${info.total_rodadas}`;
  if (info.adversario) {
    const loc = info.mando === "casa" ? "em casa" : "fora";
    $("rodada-confronto").innerHTML =
      `<span class="confronto">${escudo(info.clube_usuario, 28)} <strong>${info.clube_usuario}</strong>` +
      ` <span class="x">x</span> ${escudo(info.adversario, 28)} <strong>${info.adversario}</strong>` +
      ` <small>(${loc})</small></span> <span class="chip">Pré-jogo</span>`;
  } else {
    $("rodada-confronto").textContent =
      `${info.clube_usuario} folga nesta rodada`;
  }

  $("r-formacao").innerHTML = info.formacoes
    .map((f) => `<option${f === info.formacao ? " selected" : ""}>${f}</option>`)
    .join("");
  $("r-tatica").value = info.tatica || "equilibrado";
  marcarSalvo("");

  // suspensos e lesionados não entram na escalação
  const disponiveis = info.elenco.filter(
    (j) => !j.suspenso && !j.lesionado
  );

  // preseleção: distribui o XI preferido salvo pelos slots de cada posição
  let preselecao = null;
  if (info.xi_preferido && info.xi_preferido.length) {
    const pref = new Set(info.xi_preferido);
    preselecao = {};
    ["Goleiro", "Defesa", "Meio-Campo", "Atacante"].forEach((pos) => {
      preselecao[pos] = disponiveis
        .filter((j) => j.posicao === pos && pref.has(j.nome))
        .map((j) => j.nome);
    });
  }

  renderSlots(
    $("r-slots"), $("r-formacao").value, disponiveis, $("r-aviso"), preselecao
  );

  const fora = [];
  info.elenco
    .filter((j) => j.suspenso)
    .forEach((j) => fora.push(`🚫 ${j.nome} (susp. ${j.jogos_suspensao}j)`));
  info.elenco
    .filter((j) => j.lesionado)
    .forEach((j) => fora.push(`🚑 ${j.nome} (lesão ${j.rodadas_lesao}r)`));
  $("r-suspensos").innerHTML = fora.length
    ? "Fora desta rodada: " + fora.join(", ")
    : "";
  $("r-suspensos").hidden = fora.length === 0;

  const situacao = (j) => {
    if (j.lesionado) return `🚑 Lesionado (${j.rodadas_lesao}r)`;
    if (j.suspenso) return `🚫 Suspenso (${j.jogos_suspensao}j)`;
    if (j.amarelos_ciclo === 4) return `<span class="chip chip-perto">Pendurado</span>`;
    return j.condicao;
  };
  const elenco = [...info.elenco]
    .sort((a, b) => b.overall - a.overall)
    .map((j) => ({ ...j, situacao: situacao(j) }));
  $("r-elenco").innerHTML = tabela(elenco, COLS_ELENCO_RODADA);

  const marcarEu = (c) =>
    c.mandante === info.clube_usuario || c.visitante === info.clube_usuario
      ? "eu"
      : "";
  $("r-confrontos").innerHTML = tabela(
    info.confrontos,
    [["mandante", "Mandante"], ["visitante", "Visitante"]],
    marcarEu
  );

  $("r-jogar").innerHTML = info.adversario
    ? `${icone("play")} Jogar a rodada ${info.rodada}`
    : `${icone("play")} Avançar a rodada ${info.rodada}`;
  $("r-jogar").disabled = false;

  renderAbasRodada();
  carregarMercado();
  if (estado.abaRodada === "financas") carregarFinancasRodada();
}

export function renderRodadaDepois() {
  const res = estado.rodadaResultado;
  $("rodada-antes").hidden = true;
  $("rodada-depois").hidden = false;

  $("rodada-titulo").textContent = res.concluida
    ? "Temporada encerrada"
    : `Rodada ${res.rodada_jogada} — resultados`;
  $("rodada-confronto").innerHTML = res.concluida
    ? `${res.campeao} é o campeão <span class="chip chip-batida">Fim de temporada</span>`
    : `<span class="chip">Encerrada</span>`;
  $("r-res-titulo").textContent = `Rodada ${res.rodada_jogada}`;

  const meu = res.clube_usuario;
  const linhas = res.resultados.map((r) => ({
    partida_id: r.partida_id,
    mandante: r.mandante,
    placar: `${r.gols_mandante} x ${r.gols_visitante}`,
    visitante: r.visitante,
  }));
  const marcarEu = (r) =>
    r.mandante === meu || r.visitante === meu ? "eu" : "";
  $("r-resultados").innerHTML = tabela(
    linhas,
    [["mandante", "Mandante"], ["placar", "Placar"], ["visitante", "Visitante"]],
    marcarEu
  );
  ligarLinks($("r-resultados"));

  $("r-classificacao").innerHTML = tabela(
    res.classificacao,
    COLUNAS.classificacao,
    (c) => (c.clube === meu ? "eu" : "")
  );
  ligarLinks($("r-classificacao"));

  $("r-proxima").textContent = res.concluida
    ? "🏆 Ver a temporada completa"
    : `Próxima rodada (${res.rodada_atual}) →`;
}

export async function jogarRodada() {
  limparAviso();
  const corpo = decisaoAtual();
  $("r-jogar").disabled = true;
  // o POST já leva a escalação: o autosave pendente vira redundante, e um
  // PATCH em voo precisa terminar antes (senão chega depois da rodada)
  cancelarAutosave();
  await emVoo;
  $("r-mercado-msg").textContent = "";
  $("r-contrato-msg").textContent = "";
  $("c-form").innerHTML = "";
  ocupado(true, `Jogando a rodada ${estado.rodadaInfo.rodada}…`);
  const res = await pedir(`/simulacoes/${estado.simId}/rodadas`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(corpo),
  });
  ocupado(false);
  if (!res) {
    $("r-jogar").disabled = false;
    return;
  }
  estado.temporada = res;
  estado.rodadaResultado = res;
  estado.faseRodada = "depois";
  pilhaVoltar.length = 0;
  mostrarRodadaTela();
}

export async function avancarAposResultado() {
  if (estado.rodadaResultado && estado.rodadaResultado.concluida) {
    await carregarLista(estado.simId);
  } else {
    await carregarProximaRodada();
  }
}

// ---------- autosave da escalação (v0.9) ----------
// Mexeu na formação, na tática ou num slot: 800 ms sem novas mudanças e a
// escalação vai pro servidor (PATCH /decisao) — sem jogar a rodada.

const ESPERA_AUTOSAVE = 800;
let timerAutosave = null;
let simAgendada = null;   // o save da mudança pendente (pode trocar em 800 ms)
let emVoo = Promise.resolve();

function decisaoAtual() {
  return {
    tatica: $("r-tatica").value,
    formacao: $("r-formacao").value,
    xi: [...new Set(xiEscolhido($("r-slots")))],   // dedup, mantém a ordem
  };
}

function marcarSalvo(texto, erro = false) {
  $("r-salvo").textContent = texto;
  $("r-salvo").classList.toggle("erro", erro);
}

function cancelarAutosave() {
  clearTimeout(timerAutosave);
  timerAutosave = null;
}

function agendarAutosave() {
  cancelarAutosave();
  simAgendada = estado.simId;
  marcarSalvo("alterações não salvas…");
  timerAutosave = setTimeout(salvarEscalacaoAgora, ESPERA_AUTOSAVE);
}

// grava já o que estiver pendente (e espera um PATCH em voo terminar)
export async function salvarEscalacaoAgora() {
  if (timerAutosave === null) return emVoo;
  cancelarAutosave();
  const simId = simAgendada;
  const corpo = decisaoAtual();
  marcarSalvo("salvando…");
  emVoo = emVoo.then(async () => {
    // fetch direto em vez de `pedir`: falha de autosave não deve sujar o
    // aviso de erro global — o indicador ao lado da tática já conta
    try {
      const resp = await fetch(`${api()}/simulacoes/${simId}/decisao`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(corpo),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      if (estado.simId === simId) marcarSalvo("✔ salvo");
    } catch {
      if (estado.simId === simId) marcarSalvo("⚠ não salvo — será enviado ao jogar", true);
    }
  });
  return emVoo;
}

// fechando/recarregando a aba com mudança pendente: `keepalive` deixa o
// pedido terminar mesmo depois que a página some
window.addEventListener("pagehide", () => {
  if (timerAutosave === null) return;
  cancelarAutosave();
  fetch(`${api()}/simulacoes/${simAgendada}/decisao`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(decisaoAtual()),
    keepalive: true,
  });
});

$("r-tatica").addEventListener("change", agendarAutosave);
// os <select> dos slots são recriados a cada render; o `change` sobe até o
// contêiner, então um ouvinte só aqui cobre todos
$("r-slots").addEventListener("change", agendarAutosave);

$("r-jogar").addEventListener("click", jogarRodada);
$("r-proxima").addEventListener("click", avancarAposResultado);
$("r-ver-tabela").addEventListener("click", () => navegarPara(mostrarTemporada));
$("r-formacao").addEventListener("change", () => {
  renderSlots(
    $("r-slots"),
    $("r-formacao").value,
    estado.rodadaInfo.elenco.filter((j) => !j.suspenso && !j.lesionado),
    $("r-aviso")
  );
  agendarAutosave();
});
