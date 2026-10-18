// Escalação no campo e planos de jogo (v1.2), como no EA FC: o técnico
// guarda planos com nome (formação, tática e XI) e um deles é o padrão,
// carregado a cada rodada nova. Antes do apito dá para trocar de plano ou
// mexer só naquele jogo; "Salvar no plano" guarda a mudança no molde.
//
// O campo mostra o time como o motor vai escalar (GET /rodadas/proxima →
// `escalacao`): trocar um titular por um reserva da mesma posição grava na
// hora e o campo é refeito pelo servidor. Quem está exausto pode ser
// poupado mesmo escolhido, e o aviso diz quem entrou no lugar.

import { $, estado, pedir } from "./nucleo.js";
import { camisa } from "./identidade.js";
import { icone } from "./icones.js";
import { carregarProximaRodada, salvarEscalacaoAgora, salvarJa } from "./rodada.js";

const LINHA_POS = ["Goleiro", "Defesa", "Meio-Campo", "Atacante"];
const SIGLA = { Goleiro: "GOL", Defesa: "DEF", "Meio-Campo": "MEI", Atacante: "ATA" };
const TATICA = { ofensivo: "Ofensivo", equilibrado: "Equilibrado", defensivo: "Defensivo" };

// o que está no campo e no banco agora, e o que está selecionado
const ed = { titulares: [], banco: [], sel: null, planos: null, editando: null, apagar: null };

export function xiDoEditor() {
  return ed.titulares.map((j) => j.nome);
}

export function planoEmUso() {
  return ed.planos && ed.planos.planos.find((p) => p.id === ed.planos.em_uso);
}

// ---------- o campo ----------

export function renderEditor() {
  const esc = estado.rodadaInfo.escalacao;
  if (!esc) return;
  ed.titulares = esc.titulares.map((j) => ({ ...j }));
  ed.banco = esc.banco.map((j) => ({ ...j }));
  ed.sel = null;
  desenhar();
}

function sobrenome(nome) {
  const partes = nome.split(" ");
  return partes[partes.length - 1];
}

function energia(v) {
  return `<span class="ed-energia ${v <= 30 ? "baixa" : v <= 60 ? "media" : ""}" title="Energia ${v}"><i style="width:${v}%"></i></span>`;
}

// quem combina com a seleção atual (mesma posição da vaga)
function posicaoDa(sel) {
  if (!sel) return null;
  if (sel.lado === "campo") return LINHA_POS[ed.titulares.find((j) => j.nome === sel.nome).linha];
  return ed.banco.find((j) => j.nome === sel.nome).posicao;
}

function desenhar() {
  const clube = estado.rodadaInfo.clube_usuario;
  const pos = posicaoDa(ed.sel);

  const peca = (j) => {
    const vaga = LINHA_POS[j.linha];
    const sel = ed.sel && ed.sel.lado === "campo" && ed.sel.nome === j.nome;
    const alvo = pos && !sel && vaga === pos;
    const sinais = [
      j.craque ? `<span class="pj-ic pj-craque" title="Craque">${icone("estrela", "craque")}</span>` : "",
      j.condicao !== "Normal" ? `<span class="pj-ic pj-cansado" title="${j.condicao} (energia ${j.energia})">${icone("raio", j.condicao)}</span>` : "",
      j.pendurado ? `<span class="cartao" title="Pendurado" role="img" aria-label="pendurado"></span>` : "",
    ].join("");
    const improvisado = j.posicao !== vaga ? ` <small title="Improvisado: é ${j.posicao}">imp.</small>` : "";
    return `<button class="ed-jog ${sel ? "sel" : ""} ${alvo ? "alvo" : ""} ${j.condicao === "Exausto" ? "exausto" : ""}"
        data-lado="campo" data-nome="${j.nome}" draggable="true"
        title="${j.nome} · ${j.posicao} · overall ${j.overall} · energia ${j.energia}">
      <span class="peca-camisa">${camisa(clube, { numero: j.numero, tamanho: 40 })}<span class="peca-sinais">${sinais}</span></span>
      <span class="ed-nome">${sobrenome(j.nome)}${improvisado}</span>
      <span class="ed-info"><b>${j.overall}</b>${energia(j.energia)}</span>
    </button>`;
  };

  const linhas = [3, 2, 1, 0].map((n) =>
    `<div class="ed-linha">${ed.titulares.filter((j) => j.linha === n).map(peca).join("")}</div>`
  ).join("");
  $("ed-campo").innerHTML = `
    <svg class="ed-marcas" viewBox="0 0 68 100" preserveAspectRatio="none" aria-hidden="true">
      <rect x="1" y="1" width="66" height="98"/><line x1="1" y1="50" x2="67" y2="50"/>
      <circle cx="34" cy="50" r="8"/><rect x="16" y="1" width="36" height="15"/>
      <rect x="16" y="84" width="36" height="15"/><rect x="26" y="1" width="16" height="5"/>
      <rect x="26" y="94" width="16" height="5"/>
    </svg>${linhas}`;

  const fora = estado.rodadaInfo.elenco.filter((j) => j.suspenso || j.lesionado);
  const reserva = (j) => {
    const sel = ed.sel && ed.sel.lado === "banco" && ed.sel.nome === j.nome;
    const alvo = pos && !sel && j.posicao === pos;
    return `<li><button class="ed-reserva ${sel ? "sel" : ""} ${alvo ? "alvo" : ""}"
        data-lado="banco" data-nome="${j.nome}" draggable="true">
      <b class="ed-num">${j.numero ?? "–"}</b>
      <span class="ed-reserva-nome">${j.nome}</span>
      <small class="ed-pos">${SIGLA[j.posicao]}</small>
      <b class="ed-ovr">${j.overall}</b>
      ${energia(j.energia)}
    </button></li>`;
  };
  $("ed-banco").innerHTML =
    (ed.banco.length ? ed.banco.map(reserva).join("") : `<li class="vazio">Sem reservas disponíveis.</li>`) +
    fora.map((j) => `<li><span class="ed-reserva fora">
      <b class="ed-num">${icone(j.lesionado ? "lesao" : "proibido")}</b>
      <span class="ed-reserva-nome">${j.nome}</span>
      <small class="ed-pos">${SIGLA[j.posicao]}</small>
      <small>${j.lesionado ? `lesão ${j.rodadas_lesao}r` : `susp. ${j.jogos_suspensao}j`}</small>
    </span></li>`).join("");

  ligar();
}

function ligar() {
  document.querySelectorAll("#ed-campo [data-nome], #ed-banco [data-nome]").forEach((el) => {
    el.addEventListener("click", () => tocar(el.dataset.lado, el.dataset.nome));
    el.addEventListener("dragstart", (e) => {
      ed.sel = { lado: el.dataset.lado, nome: el.dataset.nome };
      e.dataTransfer.effectAllowed = "move";
      e.dataTransfer.setData("text/plain", el.dataset.nome);
      requestAnimationFrame(desenhar);   // acende os alvos
    });
    el.addEventListener("dragover", (e) => {
      if (el.classList.contains("alvo")) e.preventDefault();
    });
    el.addEventListener("drop", (e) => {
      e.preventDefault();
      tocar(el.dataset.lado, el.dataset.nome);
    });
  });
}

// toque: seleciona; segundo toque num alvo da mesma posição troca
function tocar(lado, nome) {
  const sel = ed.sel;
  if (sel && sel.lado === lado && sel.nome === nome) { ed.sel = null; desenhar(); return; }
  if (sel && posicaoCompativel(sel, lado, nome)) {
    trocar(sel, { lado, nome });
    return;
  }
  ed.sel = { lado, nome };
  desenhar();
}

function posicaoCompativel(sel, lado, nome) {
  const pos = posicaoDa(sel);
  if (lado === "campo") return LINHA_POS[ed.titulares.find((j) => j.nome === nome).linha] === pos;
  return sel.lado === "campo" && ed.banco.find((j) => j.nome === nome).posicao === pos;
}

async function trocar(a, b) {
  const ia = (x) => (x.lado === "campo" ? ed.titulares : ed.banco).findIndex((j) => j.nome === x.nome);
  if (a.lado === "campo" && b.lado === "campo") {   // só a ordem na linha
    const [i, k] = [ia(a), ia(b)];
    [ed.titulares[i], ed.titulares[k]] = [{ ...ed.titulares[k], linha: ed.titulares[i].linha }, { ...ed.titulares[i], linha: ed.titulares[k].linha }];
    ed.sel = null;
    desenhar();
    return;
  }
  const campo = a.lado === "campo" ? a : b;
  const banco = a.lado === "campo" ? b : a;
  const i = ia(campo);
  const k = ia(banco);
  const sai = ed.titulares[i];
  const entra = ed.banco[k];
  ed.titulares[i] = { ...entra, linha: sai.linha };
  ed.banco[k] = { ...sai };
  ed.sel = null;
  desenhar();
  await gravarEConferir([entra.nome]);
}

// grava a escalação e refaz o campo com o que o motor vai mesmo escalar
export async function gravarEConferir(escolhidos = []) {
  await salvarJa();
  const info = await pedir(`/simulacoes/${estado.simId}/rodadas/proxima`);
  if (!info) return;
  Object.assign(estado.rodadaInfo, {
    escalacao: info.escalacao, xi_preferido: info.xi_preferido,
    tatica: info.tatica, formacao: info.formacao,
  });
  renderEditor();
  const poupados = escolhidos.filter((n) => !ed.titulares.some((j) => j.nome === n));
  avisar(poupados.length
    ? `${poupados.join(", ")} está exausto e o motor vai poupá-lo: entra o melhor reserva da posição.`
    : "");
  await carregarPlanos();
}

function avisar(texto) {
  $("ed-aviso").textContent = texto;
  $("ed-aviso").hidden = !texto;
}

// ---------- planos de jogo ----------

export async function carregarPlanos() {
  const v = await pedir(`/simulacoes/${estado.simId}/planos`);
  if (!v) return;
  ed.planos = v;
  renderPlanos();
}

function renderPlanos() {
  const v = ed.planos;
  const atual = planoEmUso();
  const chip = (p) => `<button class="pl-chip ${p.id === v.em_uso ? "ativo" : ""}" data-usar="${p.id}"
      aria-pressed="${p.id === v.em_uso}" title="${p.formacao} · ${TATICA[p.tatica]}${p.padrao ? " · padrão" : ""}">
      ${p.padrao ? `<span class="pl-estrela" aria-label="padrão">${icone("estrela")}</span>` : ""}${p.nome}
      <small>${p.formacao}</small></button>`;

  let status;
  if (ed.editando) {
    status = `<form class="pl-form" id="pl-form">
      <input id="pl-nome" maxlength="30" placeholder="Nome do plano" value="${ed.editando.nome}" aria-label="Nome do plano" required>
      <button type="submit">${ed.editando.id ? "Renomear" : "Criar plano"}</button>
      <button type="button" class="secondary outline" id="pl-cancelar">Cancelar</button>
      <span id="pl-msg" class="pl-msg" role="status"></span>
    </form>`;
  } else {
    const estadoPlano = !atual
      ? `<span class="pl-estado">Escalação avulsa (nenhum plano carregado)</span>`
      : v.modificado
        ? `<span class="pl-estado"><span class="chip chip-perto">Mexido só neste jogo</span> a partir de <b>${atual.nome}</b></span>
           <button class="pl-acao" data-acao="salvar">${icone("ok")} Salvar no plano</button>
           <button class="pl-acao secondary outline" data-acao="desfazer">Voltar ao plano</button>`
        : `<span class="pl-estado">Plano carregado: <b>${atual.nome}</b>${atual.padrao ? " (padrão)" : ""}</span>`;
    const confirmando = ed.apagar && atual && ed.apagar === atual.id;
    status = `${estadoPlano}
      <span class="pl-acoes">
        <button class="pl-acao secondary outline" data-acao="novo">${icone("mais")} Novo plano</button>
        ${atual && !atual.padrao ? `<button class="pl-acao secondary outline" data-acao="padrao">${icone("estrela")} Tornar padrão</button>` : ""}
        ${atual ? `<button class="pl-acao secondary outline" data-acao="renomear">Renomear</button>` : ""}
        ${atual && v.planos.length > 1 ? `<button class="pl-acao secondary outline ${confirmando ? "perigo" : ""}" data-acao="apagar">${icone("lixo")} ${confirmando ? "Confirmar exclusão" : "Excluir"}</button>` : ""}
      </span>
      <span id="pl-msg" class="pl-msg" role="status"></span>`;
  }

  $("pl-planos").innerHTML = `
    <div class="pl-topo"><span class="pl-rotulo">${icone("prancheta")} Planos de jogo</span>
      <div class="pl-chips" role="group" aria-label="Planos de jogo">${v.planos.map(chip).join("")}</div></div>
    <div class="pl-status">${status}</div>`;

  $("pl-planos").querySelectorAll("[data-usar]").forEach((b) =>
    b.addEventListener("click", () => usar(Number(b.dataset.usar)))
  );
  $("pl-planos").querySelectorAll("[data-acao]").forEach((b) =>
    b.addEventListener("click", () => acao(b.dataset.acao))
  );
  if (ed.editando) {
    $("pl-nome").focus();
    $("pl-form").addEventListener("submit", (e) => { e.preventDefault(); confirmarNome(); });
    $("pl-cancelar").addEventListener("click", () => { ed.editando = null; renderPlanos(); });
  }
}

function msg(texto, erro = false) {
  const el = $("pl-msg");
  if (!el) return;
  el.textContent = texto;
  el.classList.toggle("erro", erro);
}

// fetch próprio: os erros de validação (400/409) viram mensagem ao lado
async function mandar(caminho, metodo, corpo) {
  try {
    const resp = await fetch(caminho, {
      method: metodo,
      headers: { "Content-Type": "application/json" },
      body: corpo ? JSON.stringify(corpo) : undefined,
    });
    const dados = await resp.json();
    if (!resp.ok) { msg(typeof dados.detail === "string" ? dados.detail : `HTTP ${resp.status}`, true); return null; }
    return dados;
  } catch (e) {
    msg(`Sem resposta do servidor (${e.message})`, true);
    return null;
  }
}

const base = () => `/simulacoes/${estado.simId}/planos`;

// carregar um plano refaz a tela da rodada (formação, tática e campo)
async function usar(id) {
  ed.apagar = null;
  await salvarEscalacaoAgora();
  const v = await mandar(`${base()}/${id}/usar`, "POST");
  if (!v) return;
  ed.planos = v;
  await carregarProximaRodada();
}

async function acao(qual) {
  const atual = planoEmUso();
  if (qual !== "apagar") ed.apagar = null;
  if (qual === "novo") { ed.editando = { id: null, nome: "" }; renderPlanos(); return; }
  if (qual === "renomear") { ed.editando = { id: atual.id, nome: atual.nome }; renderPlanos(); return; }
  if (qual === "desfazer") { await usar(atual.id); return; }
  if (qual === "padrao") {
    const v = await mandar(`${base()}/${atual.id}`, "PATCH", { padrao: true });
    if (v) { ed.planos = v; renderPlanos(); msg(`${atual.nome} vem carregado a cada rodada.`); }
    return;
  }
  if (qual === "salvar") {
    await salvarEscalacaoAgora();
    const v = await mandar(`${base()}/${atual.id}`, "PATCH", {
      formacao: $("r-formacao").value, tatica: $("r-tatica").value, xi: xiDoEditor(),
    });
    if (v) { ed.planos = v; renderPlanos(); msg(`${atual.nome} atualizado.`); }
    return;
  }
  if (qual === "apagar") {
    if (ed.apagar !== atual.id) { ed.apagar = atual.id; renderPlanos(); return; }   // 2º clique confirma
    ed.apagar = null;
    const v = await mandar(`${base()}/${atual.id}`, "DELETE");
    if (v) { ed.planos = v; renderPlanos(); msg(`${atual.nome} excluído.`); }
  }
}

async function confirmarNome() {
  const nome = $("pl-nome").value.trim();
  if (!nome) return;
  const { id } = ed.editando;
  let v;
  if (id) {
    v = await mandar(`${base()}/${id}`, "PATCH", { nome });
  } else {
    await salvarEscalacaoAgora();   // o plano novo nasce da escalação na tela
    v = await mandar(base(), "POST", {
      nome, formacao: $("r-formacao").value, tatica: $("r-tatica").value, xi: xiDoEditor(),
    });
  }
  if (!v) return;
  ed.editando = null;
  ed.planos = v;
  renderPlanos();
  msg(id ? "Plano renomeado." : `${nome} criado e carregado.`);
}
