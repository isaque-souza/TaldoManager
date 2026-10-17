// Montar a escalação (formação + XI) e criar uma temporada nova.

import { $, estado, limparAviso, ocupado, pedir } from "./nucleo.js";
import { carregarLista } from "./saves.js";

// ---------- montar a escalação ----------


export async function aoTrocarClube() {
  const nome = $("meu-clube").value;
  $("tatica").disabled = !nome;
  $("escalacao").hidden = !nome;
  if (!nome) { estado.elencoClube = null; return; }

  const dados = await pedir(`/clubes/${encodeURIComponent(nome)}`);
  if (!dados) return;
  estado.elencoClube = dados;
  $("escalacao-clube").textContent = nome;
  $("formacao").innerHTML = dados.formacoes
    .map((f) => `<option${f === "4-3-3" ? " selected" : ""}>${f}</option>`)
    .join("");
  renderSlotsPreTemporada();
}

export function slotsDaFormacao(formacaoValue) {
  const [nd, nm, na] = formacaoValue.split("-").map(Number);
  return [["Goleiro", 1], ["Defesa", nd], ["Meio-Campo", nm], ["Atacante", na]];
}

export function escolhasAtuais(slotsEl) {
  const por = {};
  slotsEl.querySelectorAll("select").forEach((s) => {
    (por[s.dataset.pos] ||= []).push(s.value);
  });
  return por;
}

export function xiEscolhido(slotsEl) {
  return [...slotsEl.querySelectorAll("select")]
    .map((s) => s.value)
    .filter(Boolean);
}

export function marcarDuplicados(slotsEl, avisoEl) {
  const vals = xiEscolhido(slotsEl);
  const dups = new Set(vals.filter((v, i) => vals.indexOf(v) !== i));
  slotsEl.querySelectorAll("select").forEach((s) =>
    s.classList.toggle("dup", !!s.value && dups.has(s.value))
  );
  if (avisoEl) {
    avisoEl.textContent = dups.size
      ? "jogador repetido — só a 1ª ocorrência conta"
      : "";
  }
}

// roster: [{nome, posicao, overall, condicao?}]  — o rótulo mostra a
// condição quando ela vem (tela de rodada a rodada)
export function renderSlots(slotsEl, formacaoValue, roster, avisoEl, preselecao) {
  const atuais = preselecao || escolhasAtuais(slotsEl);
  slotsEl.innerHTML = slotsDaFormacao(formacaoValue)
    .map(([pos, n]) => {
      const jogadores = roster
        .filter((j) => j.posicao === pos)
        .sort((a, b) => b.overall - a.overall);
      const selects = Array.from({ length: n }, (_, i) => {
        const sel = (atuais[pos] || [])[i] || "";
        const opts =
          `<option value="">— automático —</option>` +
          jogadores
            .map((j) => {
              const cond =
                j.condicao && j.condicao !== "Normal" ? ` · ${j.condicao}` : "";
              return `<option value="${j.nome}"${j.nome === sel ? " selected" : ""}>${j.nome} (${j.overall})${cond}</option>`;
            })
            .join("");
        return `<select data-pos="${pos}">${opts}</select>`;
      }).join("");
      return `<div class="grupo">${pos} ×${n}</div>${selects}`;
    })
    .join("");
  slotsEl
    .querySelectorAll("select")
    .forEach((s) =>
      s.addEventListener("change", () => marcarDuplicados(slotsEl, avisoEl))
    );
  marcarDuplicados(slotsEl, avisoEl);
}

export function renderSlotsPreTemporada() {
  if (!estado.elencoClube) return;
  renderSlots(
    $("slots"), $("formacao").value, estado.elencoClube.elenco, $("escalacao-aviso")
  );
}

$("meu-clube").addEventListener("change", aoTrocarClube);
$("formacao").addEventListener("change", renderSlotsPreTemporada);

export async function novaTemporada() {
  limparAviso();
  const corpo = {};
  const seed = $("seed").value.trim();
  if (seed) corpo.seed = Number(seed);
  const meuClube = $("meu-clube").value;
  if (meuClube) {
    corpo.clube = meuClube;
    corpo.tatica = $("tatica").value;
    corpo.formacao = $("formacao").value;
    const xi = [...new Set(xiEscolhido($("slots")))];   // dedup, mantém a ordem
    if (xi.length) corpo.xi = xi;
  }

  const rodadaARodada = $("modo").value === "rodada_a_rodada";
  if (rodadaARodada) {
    if (!meuClube) {
      $("erro").textContent =
        "Rodada a rodada precisa de um clube — escolha o seu clube acima.";
      return;
    }
    corpo.modo = "rodada_a_rodada";
  }

  ocupado(
    true,
    rodadaARodada
      ? "Preparando a temporada…"
      : "Simulando temporada (38 rodadas, 380 partidas)…"
  );
  const criada = await pedir("/simulacoes", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(corpo),
  });
  ocupado(false);
  if (!criada) return;
  await carregarLista(criada.id);
}
