// Pré-jogo (v1.1): as duas escalações no campo, antes do apito.
// "Jogar a rodada" abre esta tela; "Ir para o jogo" joga de fato. O XI vem
// de GET /pre-jogo, que roda a mesma escalação do motor: é quem vai entrar.
// v2.3: com o contexto do jogo — forma recente, desfalques, estádio e
// público previsto (tudo lido do save).

import { $, esconderTudo, estado, limparAviso, ocupado, pedir } from "./nucleo.js";
import { abrirSecaoRodada, jogarRodada, salvarEscalacaoAgora } from "./rodada.js";
import { jogarAoVivo } from "./aovivo.js";
import { camisa, escudo } from "./identidade.js";
import { icone } from "./icones.js";

const TATICA = { ofensivo: "Ofensivo", equilibrado: "Equilibrado", defensivo: "Defensivo" };
const RESULTADO = { V: "Vitória", E: "Empate", D: "Derrota" };

const chip = (classe, texto) => `<span class="chip${classe ? ` chip-${classe}` : ""}">${texto}</span>`;
const milhar = (n) => n.toLocaleString("pt-BR");
const pct = (n) => `${Math.round(n * 100)}%`;

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

  $("pj-titulo").textContent = pj.copa
    ? `Copa · ${pj.copa.nome}`
    : `Rodada ${pj.rodada} de ${pj.total_rodadas}`;
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

  const ctxEu = pj.contexto_mandante && pj.contexto_mandante.clube === eu.clube
    ? pj.contexto_mandante : pj.contexto_visitante;
  const ctxRival = ctxEu === pj.contexto_mandante ? pj.contexto_visitante : pj.contexto_mandante;
  $("pj-estadio").innerHTML = cartaoEstadio(pj.estadio, pj.mando);
  $("pj-estadio").hidden = !pj.estadio;
  $("pj-contexto").hidden = !pj.estadio;
  $("pj-chega-eu-titulo").textContent = `Como chega — ${eu.clube}`;
  $("pj-chega-rival-titulo").textContent = `Como chega — ${rival.clube}`;
  $("pj-chega-eu").innerHTML = comoChega(ctxEu);
  $("pj-chega-rival").innerHTML = comoChega(ctxRival);

  $("pj-banco-eu-titulo").textContent = `Banco — ${eu.clube}`;
  $("pj-banco-rival-titulo").textContent = `Banco — ${rival.clube}`;
  $("pj-banco-eu").innerHTML = banco(eu);
  $("pj-banco-rival").innerHTML = banco(rival);
}

// ---------- contexto do jogo (v2.3) ----------

function cartaoEstadio(e, mando) {
  if (!e) return "";
  const onde = mando === "casa" ? "Em casa" : `Casa do ${e.clube}`;
  const selos = [
    e.classico ? chip("longe", "Clássico") : "",
    e.lotado ? chip("batida", "Lotado") : "",
  ].join(" ");
  return `<span class="hub-rotulo">${icone("torcida")} Estádio · ${onde}</span>
    <p class="pg-numero">${milhar(e.publico_previsto)} <small>torcedores previstos</small></p>
    <div class="pj-ocupacao" role="img" aria-label="${pct(e.ocupacao)} de ocupação">
      <span style="width:${Math.min(100, e.ocupacao * 100)}%"></span></div>
    <p class="pg-detalhe">${pct(e.ocupacao)} de ${milhar(e.capacidade)} lugares · ingresso ${e.ingresso.toLowerCase()}</p>
    ${selos.trim() ? `<p class="pg-linha">${selos}</p>` : ""}`;
}

function comoChega(c) {
  if (!c) return "";
  const tabela = c.posicao
    ? `<p class="pg-linha"><b>${c.posicao}º</b> na liga · ${c.pontos} ${c.pontos === 1 ? "ponto" : "pontos"}</p>`
    : "";
  return `${tabela}
    <p class="pg-linha"><b>Últimos jogos</b></p>
    ${forma(c.forma)}
    <p class="pg-linha"><b>Desfalques</b></p>
    ${desfalques(c.desfalques)}`;
}

function forma(jogos) {
  if (!jogos.length) return `<p class="pg-detalhe">Ainda não jogou nesta temporada.</p>`;
  return `<ol class="pj-forma" aria-label="Do mais antigo para o mais recente">${jogos.map((j) => {
    const onde = j.competicao === "copa" ? `Copa · ${j.fase}` : `Rodada ${j.rodada}`;
    const pen = j.penaltis
      ? ` (pên. ${j.penaltis.pro}–${j.penaltis.contra}${j.penaltis.classificou ? ", classificou" : ", eliminado"})` : "";
    const texto = `${onde}: ${RESULTADO[j.resultado]} ${j.gols_pro}–${j.gols_contra} ` +
      `${j.mando === "casa" ? "em casa, contra o" : "fora, contra o"} ${j.adversario}${pen}`;
    return `<li title="${texto}" aria-label="${texto}"><span class="pj-res pj-res-${j.resultado}" aria-hidden="true">${j.resultado}</span>
      <small aria-hidden="true">${j.gols_pro}–${j.gols_contra}${j.competicao === "copa" ? " · copa" : ""}</small></li>`;
  }).join("")}</ol>`;
}

function desfalques(lista) {
  if (!lista.length) return `<p class="pg-detalhe">Ninguém fora: elenco completo.</p>`;
  return `<ul class="pj-desfalques">${lista.map((d) => {
    const motivo = d.motivo === "lesao"
      ? `${icone("lesao")} lesionado · ${d.jogos} ${d.jogos === 1 ? "rodada" : "rodadas"}`
      : `<span class="cartao vermelho" aria-hidden="true"></span> suspenso · ${d.jogos} ${d.jogos === 1 ? "jogo" : "jogos"}`;
    return `<li><span>${d.nome}</span> <small>${d.funcao || d.posicao} · ${d.overall}</small>
      <span class="pj-motivo pj-motivo-${d.motivo}">${motivo}</span></li>`;
  }).join("")}</ul>`;
}

function tarjaTime(t) {
  return `${escudo(t.clube, 30)}<span class="pj-tarja-nome">${t.clube}</span>` +
    `<span class="pj-tarja-esquema">${t.formacao}</span>` +
    `<span class="pj-tarja-tatica">${TATICA[t.tatica] || t.tatica}</span>`;
}

// uma metade do campo: cada titular no seu lugar do desenho da formação
// (v1.3). O CSS transforma --x (largura) e --y (profundidade) na posição, no
// campo deitado do computador e no em pé do celular
function metade(t, lado) {
  return `<div class="metade metade-${lado}">${t.titulares.map((j) => peca(t.clube, j)).join("")}</div>`;
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
  const lugar = j.x != null ? ` style="--x:${j.x};--y:${j.y}"` : "";
  return `<div class="peca"${lugar} title="${j.nome} · ${j.rotulo || j.vaga || j.funcao || j.posicao} · overall ${j.overall} · energia ${j.energia}">
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
