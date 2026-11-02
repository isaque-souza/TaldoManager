// Galeria de formações (v2.4): as formações num mini campinho cada, em
// grupos pela linha de defesa (4, 3 ou 5 atrás), com o peso de cada uma no
// motor. Escolher uma é o mesmo que mudar o <select id="r-formacao">: a
// mudança dispara o "change" de lá, que grava e confere (rodada.js).

import { $, estado } from "./nucleo.js";

const GRUPOS = [
  ["4", "Linha de 4"],
  ["3", "Linha de 3"],
  ["5", "Linha de 5"],
];

// "4-2-3-1" → "4": o número de defensores que dá nome à formação
const linha = (f) => f.split("-")[0];

// a porcentagem do peso: +6% / −5% (0 não aparece)
function peso(valor) {
  const p = Math.round((valor - 1) * 100);
  if (!p) return "0";
  return `${p > 0 ? "+" : "−"}${Math.abs(p)}%`;
}

function campinho(vagas) {
  const ponto = ({ x, y, funcao }) => {
    const cx = (5 + x * 0.5).toFixed(1);
    const cy = (74 - y * 0.66).toFixed(1);
    return `<circle cx="${cx}" cy="${cy}" r="3.1" class="fg-${funcao === "Goleiro" ? "gol" : "linha"}"/>`;
  };
  return `<svg viewBox="0 0 60 78" aria-hidden="true" focusable="false">
    <rect x=".5" y=".5" width="59" height="77" rx="2" class="cp-gramado"/>
    <g class="cp-linhas"><line x1=".5" y1="39" x2="59.5" y2="39"/><circle cx="30" cy="39" r="6"/>
      <rect x="17" y=".5" width="26" height="10"/><rect x="17" y="67.5" width="26" height="10"/></g>
    ${ponto({ x: 50, y: 3, funcao: "Goleiro" })}${vagas.map(ponto).join("")}
  </svg>`;
}

function cartao(f, atual) {
  const ata = peso(f.ataque);
  const def = peso(f.defesa);
  const titulo = `${f.formacao}: ataque ${ata}, defesa ${def} (no motor, perto da tática)`;
  return `<button type="button" class="fg-cartao${f.formacao === atual ? " escolhida" : ""}"
      data-formacao="${f.formacao}" aria-pressed="${f.formacao === atual}" title="${titulo}">
    ${campinho(f.vagas)}
    <b>${f.formacao}</b>
    <span class="fg-peso"><span class="${f.ataque > 1 ? "mais" : f.ataque < 1 ? "menos" : ""}">ATA ${ata}</span>
      <span class="${f.defesa > 1 ? "mais" : f.defesa < 1 ? "menos" : ""}">DEF ${def}</span></span>
  </button>`;
}

export function renderGaleria() {
  const info = estado.rodadaInfo && estado.rodadaInfo.formacoes_info;
  const box = $("ed-galeria");
  if (!info || !info.length) {
    box.innerHTML = "";
    $("ed-ver-formacoes").hidden = true;
    return;
  }
  $("ed-ver-formacoes").hidden = false;
  const atual = $("r-formacao").value;
  box.innerHTML = GRUPOS.map(([n, rotulo]) => {
    const doGrupo = info.filter((f) => linha(f.formacao) === n);
    return doGrupo.length
      ? `<section class="fg-grupo"><h4>${rotulo} <small>${doGrupo.length}</small></h4>
          <div class="fg-grade">${doGrupo.map((f) => cartao(f, atual)).join("")}</div></section>`
      : "";
  }).join("") + `<p class="fg-nota">ATA e DEF: quanto a formação muda o ataque e a defesa no motor,
    na metade da escala da tática. A 4-3-3 é a neutra.</p>`;
  box.querySelectorAll("[data-formacao]").forEach((b) =>
    b.addEventListener("click", () => escolher(b.dataset.formacao))
  );
}

// as opções do <select>, nos mesmos grupos da galeria
export function opcoesFormacao(formacoes, atual) {
  return GRUPOS.map(([n, rotulo]) => {
    const doGrupo = formacoes.filter((f) => linha(f) === n);
    return doGrupo.length
      ? `<optgroup label="${rotulo}">${doGrupo
        .map((f) => `<option${f === atual ? " selected" : ""}>${f}</option>`).join("")}</optgroup>`
      : "";
  }).join("");
}

function escolher(formacao) {
  const sel = $("r-formacao");
  if (sel.value === formacao) return;
  sel.value = formacao;
  sel.dispatchEvent(new Event("change"));
  marcarEscolhida();
}

export function marcarEscolhida() {
  const atual = $("r-formacao").value;
  $("ed-galeria").querySelectorAll("[data-formacao]").forEach((b) => {
    const sim = b.dataset.formacao === atual;
    b.classList.toggle("escolhida", sim);
    b.setAttribute("aria-pressed", String(sim));
  });
}

function alternar() {
  const box = $("ed-galeria");
  const abrir = box.hidden;
  if (abrir) renderGaleria();
  box.hidden = !abrir;
  $("ed-ver-formacoes").setAttribute("aria-expanded", String(abrir));
  $("ed-ver-formacoes").textContent = abrir ? "Fechar formações" : "Ver as formações";
}

$("ed-ver-formacoes").addEventListener("click", alternar);
$("r-formacao").addEventListener("change", marcarEscolhida);
