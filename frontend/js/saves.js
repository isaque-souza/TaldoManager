// Simulações salvas: lista, abrir e apagar.

import { $, esconderTudo, estado, limparAviso, pedir, pilhaVoltar } from "./nucleo.js";
import { mostrarTemporada } from "./temporada.js";
import { carregarProximaRodada } from "./rodada.js";

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

export async function carregarLista(selecionar) {
  const sims = await pedir("/simulacoes");
  if (!sims) return;

  $("lista").innerHTML = sims.length
    ? sims.map((s) => `<option value="${s.id}">${rotuloSim(s)}</option>`).join("")
    : `<option value="">— nenhuma simulação salva —</option>`;
  $("apagar").disabled = sims.length === 0;

  if (sims.length) {
    const alvo = selecionar ?? sims[0].id;
    $("lista").value = alvo;
    await abrirSimulacao(alvo);
  } else {
    esconderTudo();
  }
}

export async function abrirSimulacao(id) {
  limparAviso();
  const dados = await pedir(`/simulacoes/${id}`);
  if (!dados) return;
  estado.temporada = dados;
  estado.simId = Number(id);
  estado.abaAtual = "classificacao";
  pilhaVoltar.length = 0;
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
