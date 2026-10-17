// Modo rodada a rodada: antes (escalação) e depois (resultados).

import { $, esconderTudo, estado, limparAviso, navegarPara, ocupado, pedir, pilhaVoltar } from "./nucleo.js";
import { ligarLinks, tabela } from "./tabelas.js";
import { COLUNAS, mostrarTemporada } from "./temporada.js";
import { carregarMercado } from "./mercado.js";
import { carregarLista } from "./saves.js";
import { renderSlots, xiEscolhido } from "./escalacao.js";

// ---------- visão rodada a rodada ----------

export const COLS_ELENCO_RODADA = [
  ["nome", "Jogador"], ["posicao", "Posição"], ["overall", "OVR"],
  ["energia", "Energia"], ["situacao", "Situação"],
];

export async function carregarProximaRodada() {
  const info = await pedir(`/simulacoes/${estado.simId}/rodadas/proxima`);
  if (!info) return;
  estado.rodadaInfo = info;
  estado.rodadaResultado = null;
  estado.faseRodada = "antes";
  mostrarRodadaTela();
}

export function mostrarRodadaTela() {
  esconderTudo();
  $("rodada").hidden = false;
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
      `🎮 <strong>${info.clube_usuario}</strong> x <strong>${info.adversario}</strong> (${loc})`;
  } else {
    $("rodada-confronto").textContent =
      `${info.clube_usuario} folga nesta rodada`;
  }

  $("r-formacao").innerHTML = info.formacoes
    .map((f) => `<option${f === info.formacao ? " selected" : ""}>${f}</option>`)
    .join("");
  $("r-tatica").value = info.tatica || "equilibrado";

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
    if (j.amarelos_ciclo === 4) return "⚠️ pendurado";
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

  $("r-jogar").textContent = info.adversario
    ? `▶ Jogar a rodada ${info.rodada}`
    : `▶ Avançar a rodada ${info.rodada}`;
  $("r-jogar").disabled = false;

  carregarMercado();
}

export function renderRodadaDepois() {
  const res = estado.rodadaResultado;
  $("rodada-antes").hidden = true;
  $("rodada-depois").hidden = false;

  $("rodada-titulo").textContent = res.concluida
    ? "Temporada encerrada"
    : `Rodada ${res.rodada_jogada} — resultados`;
  $("rodada-confronto").textContent = res.concluida
    ? `${res.campeao} é o campeão`
    : "";
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
  const corpo = {
    tatica: $("r-tatica").value,
    formacao: $("r-formacao").value,
    xi: [...new Set(xiEscolhido($("r-slots")))],
  };
  $("r-jogar").disabled = true;
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

$("r-jogar").addEventListener("click", jogarRodada);
$("r-proxima").addEventListener("click", avancarAposResultado);
$("r-ver-tabela").addEventListener("click", () => navegarPara(mostrarTemporada));
$("r-formacao").addEventListener("change", () =>
  renderSlots(
    $("r-slots"),
    $("r-formacao").value,
    estado.rodadaInfo.elenco.filter((j) => !j.suspenso && !j.lesionado),
    $("r-aviso")
  )
);
