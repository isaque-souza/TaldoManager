// Simulações salvas: lista, abrir e apagar.

import { $, esconderTudo, estado, limparAviso, pedir, pilhaVoltar } from "./nucleo.js";
import { abasDaTemporada, mostrarTemporada } from "./temporada.js";
import { carregarProximaRodada } from "./rodada.js";

// ---------- continuar de onde parou (autosave, v0.9) ----------
// O progresso mora no servidor; aqui fica só "qual save e qual aba eu
// estava vendo". Se o navegador apagar isso, nada se perde: abre o save
// jogado por último, que é o primeiro da lista.

const CHAVE_SESSAO = "taldo:sessao";

function lerSessao() {
  try {
    return JSON.parse(localStorage.getItem(CHAVE_SESSAO)) || {};
  } catch {
    return {};   // aba anônima, storage bloqueado ou JSON estragado
  }
}

export function lembrarSessao() {
  if (estado.simId === null) return;
  try {
    localStorage.setItem(CHAVE_SESSAO, JSON.stringify({
      simId: estado.simId,
      abaAtual: estado.abaAtual,
      abaRodada: estado.abaRodada,
    }));
  } catch {
    // sem storage o jogo segue igual, só não lembra a aba
  }
}

window.addEventListener("pagehide", lembrarSessao);

export async function continuarDeOndeParou() {
  const sessao = lerSessao();
  await carregarLista(sessao.simId, sessao);
}

// ---------- simulações salvas ----------

export function rotuloSim(s) {
  const data = new Date(s.criada_em).toLocaleString("pt-BR");
  const eu = s.clube_usuario ? ` · 🎮 ${s.clube_usuario} (${s.tatica})` : "";
  const cabeca =
    s.estado === "em_andamento"
      ? `⏳ rodada ${s.rodada_atual}/${s.rodadas}`
      : `🏆 ${s.campeao}`;
  const temporada = s.carreira_id ? ` · 📅 temporada ${s.temporada}` : "";
  return `#${s.id}${temporada} · ${cabeca} · seed ${s.seed ?? "aleatório"}${eu} · ${data}`;
}

export async function carregarClubes() {
  const clubes = await pedir("/clubes");
  if (!clubes) return;
  $("meu-clube").insertAdjacentHTML(
    "beforeend",
    clubes.map((c) => `<option value="${c.nome}">${c.nome}</option>`).join("")
  );
}

export async function carregarLista(selecionar, abas) {
  const sims = await pedir("/simulacoes");
  if (!sims) return;

  $("lista").innerHTML = sims.length
    ? sims.map((s) => `<option value="${s.id}">${rotuloSim(s)}</option>`).join("")
    : `<option value="">— nenhuma simulação salva —</option>`;
  $("apagar").disabled = sims.length === 0;

  if (sims.length) {
    // o pedido pode ter sido apagado (ou ser de outro banco): cai no
    // primeiro da lista, o jogado por último
    const existe = sims.some((s) => s.id === Number(selecionar));
    const alvo = existe ? Number(selecionar) : sims[0].id;
    $("lista").value = alvo;
    await abrirSimulacao(alvo, existe ? abas : undefined);
  } else {
    esconderTudo();
  }
}

export async function abrirSimulacao(id, abas = {}) {
  limparAviso();
  const dados = await pedir(`/simulacoes/${id}`);
  if (!dados) return;
  estado.temporada = dados;
  estado.simId = Number(id);
  // aba lembrada só se ainda existe neste save (ex.: "Virada" só na carreira)
  const validas = abasDaTemporada().map(([k]) => k);
  estado.abaAtual = validas.includes(abas.abaAtual) ? abas.abaAtual : "classificacao";
  if (abas.abaRodada) estado.abaRodada = abas.abaRodada;
  pilhaVoltar.length = 0;
  lembrarSessao();
  if (dados.estado === "em_andamento") {
    await carregarProximaRodada();
  } else {
    mostrarTemporada();
  }
}

export async function apagarSelecionada() {
  const id = $("lista").value;
  if (!id) return;
  limparAviso();
  const ok = await pedir(`/simulacoes/${id}`, { method: "DELETE" });
  if (ok) await carregarLista();
}
