// Pré-jogo (v1.1): as duas escalações no campo, antes do apito.
// "Jogar a rodada" abre esta tela; "Ir para o jogo" joga de fato. O XI vem
// de GET /pre-jogo, que roda a mesma escalação do motor: é quem vai entrar.

import { $, esconderTudo, estado, limparAviso, ocupado, pedir } from "./nucleo.js";
import { abrirSecaoRodada, jogarRodada, salvarEscalacaoAgora } from "./rodada.js";
import { jogarAoVivo } from "./aovivo.js";
import { camisa, escudo } from "./identidade.js";
import { icone } from "./icones.js";

const TATICA = { ofensivo: "Ofensivo", equilibrado: "Equilibrado", defensivo: "Defensivo" };

export async function abrirPreJogo() {
  limparAviso();
  $("r-jogar").disabled = true;
  await salvarEscalacaoAgora();   // o pré-jogo lê a escalação gravada
  ocupado(true, "Preparando o pré-jogo…");
  const pj = await pedir(`/simulacoes/${estado.simId}/pre-jogo`);
  ocupado(false);
  $("r-jogar").disabled = false;
  if (!pj) return;
  if (!pj.adversario) {   // folga: não há jogo para mostrar
    await jogarRodada();
    return;
  }
  renderPreJogo(pj);
}

function renderPreJogo(pj) {
  const eu = pj.mandante.clube === pj.clube_usuario ? pj.mandante : pj.visitante;
  const rival = eu === pj.mandante ? pj.visitante : pj.mandante;
  const local = pj.mando === "casa" ? "em casa" : "fora";

  esconderTudo();
  $("prejogo").hidden = false;
  window.scrollTo(0, 0);

  $("pj-titulo").textContent = `Rodada ${pj.rodada} de ${pj.total_rodadas}`;
  $("pj-confronto").innerHTML =
    `${escudo(eu.clube, 28)} <strong>${eu.clube}</strong> <span class="x">x</span> ` +
    `${escudo(rival.clube, 28)} <strong>${rival.clube}</strong> <small>(${local})</small> ` +
    `<span class="chip">Pré-jogo</span>`;

  $("pj-tarja-eu").innerHTML = tarjaTime(eu);
  $("pj-tarja-rival").innerHTML = tarjaTime(rival);
  $("pj-campo").setAttribute("aria-label",
    `Escalações: ${eu.clube} no ${eu.formacao} contra ${rival.clube} no ${rival.formacao}`);
  $("pj-campo").innerHTML =
    MARCAS + metade(eu, "eu") + metade(rival, "rival");

  $("pj-banco-eu-titulo").textContent = `Banco — ${eu.clube}`;
  $("pj-banco-rival-titulo").textContent = `Banco — ${rival.clube}`;
  $("pj-banco-eu").innerHTML = banco(eu);
  $("pj-banco-rival").innerHTML = banco(rival);
}

function tarjaTime(t) {
  return `${escudo(t.clube, 30)}<span class="pj-tarja-nome">${t.clube}</span>` +
    `<span class="pj-tarja-esquema">${t.formacao}</span>` +
    `<span class="pj-tarja-tatica">${TATICA[t.tatica] || t.tatica}</span>`;
}

// uma metade do campo: as linhas da formação, do gol para o meio-campo
function metade(t, lado) {
  const linhas = [0, 1, 2, 3].map((n) => t.titulares.filter((j) => j.linha === n));
  return `<div class="metade metade-${lado}">` +
    linhas.map((js) => `<div class="linha">${js.map((j) => peca(t.clube, j)).join("")}</div>`).join("") +
    `</div>`;
}

function sobrenome(nome) {
  const partes = nome.split(" ");
  return partes[partes.length - 1];
}

function sinais(j) {
  const s = [];
  if (j.craque) s.push(`<span class="pj-ic pj-craque" title="Craque">${icone("estrela", "craque")}</span>`);
  if (j.condicao !== "Normal") {
    s.push(`<span class="pj-ic pj-cansado" title="${j.condicao} (energia ${j.energia})">${icone("raio", j.condicao)}</span>`);
  }
  if (j.pendurado) s.push(`<span class="cartao" title="Pendurado" role="img" aria-label="pendurado"></span>`);
  return s.join("");
}

function peca(clube, j) {
  return `<div class="peca" title="${j.nome} · ${j.vaga || j.funcao || j.posicao} · overall ${j.overall} · energia ${j.energia}">
    <span class="peca-camisa">${camisa(clube, { numero: j.numero, tamanho: 44 })}
      <span class="peca-sinais">${sinais(j)}</span></span>
    <span class="peca-nome">${sobrenome(j.nome)}</span>
    <span class="peca-ovr">${j.overall}</span>
  </div>`;
}

function banco(t) {
  if (!t.banco.length) return `<li class="vazio">Sem reservas disponíveis.</li>`;
  return t.banco.map((j) =>
    `<li><b>${j.numero ?? "–"}</b> <span>${j.nome}</span> <small>${j.funcao || j.posicao} · ${j.overall}</small> ${sinais(j)}</li>`
  ).join("");
}

// marcações do gramado: uma versão deitada (computador) e uma em pé
// (celular); o CSS mostra a certa
const MARCAS = `
  <svg class="marcas marcas-h" viewBox="0 0 120 80" preserveAspectRatio="none" aria-hidden="true">
    <rect x="1" y="1" width="118" height="78"/><line x1="60" y1="1" x2="60" y2="79"/>
    <circle cx="60" cy="40" r="9"/><rect x="1" y="22" width="16" height="36"/>
    <rect x="103" y="22" width="16" height="36"/><rect x="1" y="32" width="5" height="16"/>
    <rect x="114" y="32" width="5" height="16"/>
  </svg>
  <svg class="marcas marcas-v" viewBox="0 0 80 120" preserveAspectRatio="none" aria-hidden="true">
    <rect x="1" y="1" width="78" height="118"/><line x1="1" y1="60" x2="79" y2="60"/>
    <circle cx="40" cy="60" r="9"/><rect x="22" y="1" width="36" height="16"/>
    <rect x="22" y="103" width="36" height="16"/><rect x="32" y="1" width="16" height="5"/>
    <rect x="32" y="114" width="16" height="5"/>
  </svg>`;

// volta à rodada SEM redesenhá-la: os seletores continuam no DOM (só
// escondidos) com a escalação que o técnico montou — mostrarRodadaTela
// os refaria a partir do rodadaInfo de quando a rodada abriu
function voltarParaRodada() {
  esconderTudo();
  $("rodada").hidden = false;
}

$("pj-jogar").addEventListener("click", async () => {
  $("pj-jogar").disabled = true;
  voltarParaRodada();
  await jogarAoVivo();   // envia a escalação desses mesmos seletores
  $("pj-jogar").disabled = false;
});
$("pj-voltar").addEventListener("click", () => {
  voltarParaRodada();
  abrirSecaoRodada("partida");   // direto na escalação, não no menu do clube
});
