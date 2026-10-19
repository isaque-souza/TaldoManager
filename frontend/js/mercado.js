// Mercado de transferências: propostas de compra (em duas etapas, v1.7: o
// valor com o clube e depois o contrato com o jogador) e ofertas de venda.
// As telas ficam na Central de Transferências (transferencias.js) e na
// Central do Elenco (elenco.js); aqui ficam as ações — também as dos
// empréstimos (pedir um jogador emprestado e exercer a opção de compra).

import { $, api, estado, limparAviso, ocupado, pedir } from "./nucleo.js";
import { dinheiro, tabela } from "./tabelas.js";
import { abrirSecaoRodada, carregarProximaRodada, marcarHubMercado } from "./rodada.js";
import { renderElenco } from "./elenco.js";
import { renderTransferencias } from "./transferencias.js";
import { MULTA_ROTULO, PAPEL_ROTULO } from "./contratos.js";
import { icone } from "./icones.js";
import { carregarCaixa } from "./caixa.js";

// ---------- mercado de transferências ----------

// a resposta do clube ao lado do mercado, com o caminho para a mensagem
// completa do diretor de futebol (o que faltou, quantas tentativas sobram)
export function avisoMercado(html, ruim = false, onde = "r-mercado-msg") {
  const el = $(onde);
  el.innerHTML = `${html} <button class="link-caixa" type="button">${icone("email")} Ver na caixa de entrada</button>`;
  el.classList.toggle("ruim", ruim);
  el.querySelector(".link-caixa").addEventListener("click", () => abrirSecaoRodada("caixa"));
}

export async function carregarMercado() {
  // os filtros da busca rodam no navegador (v1.7): o mercado vem inteiro
  const [m, obs] = await Promise.all([
    pedir(`/simulacoes/${estado.simId}/mercado`),
    pedir(`/simulacoes/${estado.simId}/observados`),
  ]);
  if (m) renderMercado(m, obs);
}

export const bloqueado = (motivo) =>
  `<span class="bloqueio" title="${motivo}">${icone("cadeado")} ${motivo}</span>`;

// a negociação desta janela (v1.7): acordo aberto leva ao contrato
function acaoNegociacao(f) {
  const n = f.negociacao;
  if (!n) return null;
  if (n.status === "aberta") {
    return `<button class="transf" data-acao="negociacao" data-neg="${n.negociacao_id}">` +
      `${icone("contrato")} Acertar contrato</button>`;
  }
  if (n.status === "desistiu") return bloqueado("Desistiu de vir nesta janela");
  return null;
}

// compra: campo de proposta (+ aceitar a contraproposta, se houver)
export function acaoCompra(f) {
  const negociando = acaoNegociacao(f);
  if (negociando) return negociando;
  if (f.bloqueio) return bloqueado(f.bloqueio);
  const aceitar = f.contraproposta
    ? `<button class="transf" data-acao="propor" data-id="${f.jogador_id}" data-valor="${f.contraproposta}">` +
      `Aceitar ${dinheiro(f.contraproposta)}</button> `
    : "";
  if (!f.propostas_restantes) {
    return aceitar || bloqueado("Negociações encerradas nesta janela");
  }
  const sugestao = f.contraproposta || f.valor_mercado;
  return `<span class="proposta">${aceitar}` +
    `<input type="number" min="10000" step="10000" value="${sugestao}" data-proposta="${f.jogador_id}">` +
    `<button class="transf" data-acao="propor" data-id="${f.jogador_id}">Propor</button>` +
    `<small class="bloqueio">${f.propostas_restantes} restante${f.propostas_restantes === 1 ? "" : "s"}</small></span>`;
}

// livre (v1.6): sem negociação com clube — assina pagando as luvas
export function acaoLivre(f) {
  const negociando = acaoNegociacao(f);
  if (negociando) return negociando;
  if (f.bloqueio) return bloqueado(f.bloqueio);
  return `<button class="transf" data-acao="livre" data-nome="${f.nome}">` +
    `Negociar (luvas ${dinheiro(f.luvas)})</button>`;
}

// ---------- empréstimos (v1.7) ----------

export const DURACAO_EMP = { turno: "até a virada do turno", temporada: "até o fim da temporada" };

// o pedido de empréstimo na ficha de compra: duração, parte do salário, taxa
// (sugerida pelo servidor, sem os fatores escondidos) e a opção de compra
export function acaoEmprestimo(f) {
  const p = f.pedir_emprestado;
  if (!p) return "";
  const titulo = `<h4 class="secao">${icone("acordo")} Empréstimo</h4>`;
  if (p.bloqueio) return `<div class="tr-emprestimo">${titulo}${bloqueado(p.bloqueio)}</div>`;
  const c = p.contraproposta;
  const aceitar = c
    ? `<button class="transf" data-acao="emprestar" data-id="${f.jogador_id}" data-valor="${c.taxa}"
        data-duracao="${c.duracao}" data-parte="${c.parte_salario}" data-opcao="${c.opcao ? 1 : 0}">
        Aceitar ${dinheiro(c.taxa)}</button>`
    : "";
  if (!p.propostas_restantes) {
    return `<div class="tr-emprestimo">${titulo}${aceitar || bloqueado("Conversas encerradas nesta janela")}</div>`;
  }
  const d0 = c ? c.duracao : p.duracoes[0].duracao;
  const p0 = c ? c.parte_salario : 75;
  const taxas = Object.fromEntries(p.duracoes.map((d) => [d.duracao, d.taxas]));
  const taxa = c ? c.taxa : taxas[d0][String(p0)];
  return `<div class="tr-emprestimo" data-taxas='${JSON.stringify(taxas)}'>
    ${titulo}
    <div class="mercado-filtros">
      <label>Duração <select data-emp="duracao">${p.duracoes.map((d) =>
        `<option value="${d.duracao}"${d.duracao === d0 ? " selected" : ""}>${{ turno: "Meia temporada", temporada: "Temporada toda" }[d.duracao]} (até R${d.volta - 1})</option>`
      ).join("")}</select></label>
      <label>Você paga <select data-emp="parte">${[50, 75, 100].map((v) =>
        `<option value="${v}"${v === p0 ? " selected" : ""}>${v}% do salário</option>`).join("")}</select></label>
      <label>Taxa <input type="number" min="10000" step="10000" value="${taxa}" data-emp="taxa"></label>
      <label class="tr-opcao"><input type="checkbox" data-emp="opcao"${c?.opcao ? " checked" : ""}>
        Opção de compra por ${dinheiro(p.opcao_compra)}</label>
    </div>
    <span class="proposta">${aceitar}
      <button class="transf" data-acao="emprestar" data-id="${f.jogador_id}">Pedir emprestado</button>
      <small class="bloqueio">${p.propostas_restantes} pedido${p.propostas_restantes === 1 ? "" : "s"} restante${p.propostas_restantes === 1 ? "" : "s"} ·
        bancar mais do salário baixa a taxa · o contrato continua com o clube dele</small></span>
  </div>`;
}

// emprestado por outro clube (na Central do Elenco): até quando e a opção
export function blocoEmprestado(f, rodada) {
  const e = f.emprestimo;
  if (!e) return "";
  const faltam = e.volta - rodada;
  return `<div class="el-emprestado">
    <p>${icone("acordo")} <b>Emprestado pelo ${e.de_clube}</b> · fica até a rodada ${e.volta - 1}
      (mais ${faltam} rodada${faltam === 1 ? "" : "s"}) · você paga ${e.parte_salario}% do salário.
      O contrato é com o ${e.de_clube}: não renova, não vai à lista nem é dispensado.</p>
    ${e.opcao_compra
      ? `<button class="transf" data-acao="opcao" data-emprestimo="${e.emprestimo_id}">
          ${icone("contrato")} Exercer a opção de compra (${dinheiro(e.opcao_compra)})</button>
        <small class="bloqueio">Vale em qualquer rodada; depois falta o contrato com ele.</small>`
      : `<small class="bloqueio">Sem opção de compra.</small>`}
  </div>`;
}

// emprestar um jogador do técnico (na Central do Elenco): os clubes
// interessados em cada duração desta janela, com os termos deles
export function blocoEmprestar(f) {
  const e = f.emprestar;
  if (!e) return "";
  const titulo = `<h4 class="secao">${icone("acordo")} Emprestar</h4>`;
  if (e.bloqueio) {
    return `<div class="el-emprestar">${titulo}<small class="bloqueio">${icone("cadeado")} ${e.bloqueio}</small></div>`;
  }
  const duracoes = e.duracoes.map((d) => {
    const quem = d.propostas.length
      ? d.propostas.map((p) => `<li>
          <span><b>${p.clube}</b><br><small>taxa ${dinheiro(p.taxa)} · banca ${p.parte_salario}% do salário</small>
            ${p.seria_titular ? `<span class="chip chip-perto" title="Jogando, ele evolui">Seria titular</span>` : ""}</span>
          <button class="transf secondary" data-acao="ceder" data-id="${f.jogador_id}"
            data-clube="${p.clube}" data-duracao="${d.duracao}">Emprestar</button></li>`).join("")
      : `<li><small class="bloqueio">Nenhum clube interessado.</small></li>`;
    return `<p class="el-emprestar-dur">${DURACAO_EMP[d.duracao]} (volta na rodada ${d.volta})</p><ul>${quem}</ul>`;
  }).join("");
  return `<div class="el-emprestar">${titulo}${duracoes}
    <small class="bloqueio">O contrato segue com você; o clube de lá paga a parte dele do salário.</small></div>`;
}

async function cederEmprestado(jogadorId, clube, duracao) {
  const r = await postarMercado(
    `/simulacoes/${estado.simId}/emprestimos/ceder`, { jogador_id: jogadorId, clube, duracao },
    "Emprestando…", { onde: "r-contrato-msg" },
  );
  if (!r) return;
  const e = r.emprestimo;
  avisoMercado(`${icone("acordo")} ${e.jogador} foi emprestado ao ${e.para_clube}, ${DURACAO_EMP[e.duracao]}:
    entram ${dinheiro(e.taxa)} e eles pagam ${e.parte_salario}% do salário.`, false, "r-contrato-msg");
  carregarCaixa();
  return carregarProximaRodada();   // elenco e escalação mudaram
}

// a taxa sugerida acompanha a duração e a parte do salário escolhidas
function ligarEmprestimo(container) {
  container.querySelectorAll(".tr-emprestimo[data-taxas]").forEach((box) => {
    const taxas = JSON.parse(box.dataset.taxas);
    const campo = (k) => box.querySelector(`[data-emp="${k}"]`);
    const sugerir = () => { campo("taxa").value = taxas[campo("duracao").value][campo("parte").value]; };
    campo("duracao").addEventListener("change", sugerir);
    campo("parte").addEventListener("change", sugerir);
  });
}

async function pedirEmprestimo(jogadorId, corpo) {
  const r = await postarMercado(
    `/simulacoes/${estado.simId}/emprestimos`, { jogador_id: jogadorId, ...corpo }, "Pedindo o empréstimo…"
  );
  if (!r) return carregarMercado();
  const sinal = icone({ aceita: "ok", contraproposta: "acordo", recusada: "nao" }[r.resposta]);
  let msg = `${sinal} ${r.motivo}`;
  if (r.resposta === "contraproposta") msg += ` — pede ${dinheiro(r.taxa_pedida)} de taxa`;
  msg += ".";
  if (r.emprestimo) msg += ` ${r.emprestimo.jogador} já está no elenco, ${DURACAO_EMP[r.emprestimo.duracao]}.`;
  avisoMercado(msg, r.resposta === "recusada");
  carregarCaixa();
  if (r.emprestimo) return carregarProximaRodada();   // elenco e escalação mudaram
  await carregarMercado();
}

async function exercerOpcao(emprestimoId, onde) {
  const r = await postarMercado(
    `/simulacoes/${estado.simId}/emprestimos/${emprestimoId}/opcao`, {}, "Exercendo a opção…", { onde }
  );
  if (!r) return;
  // o contrato fica na Central de Transferências
  abrirSecaoRodada("mercado");
  avisoMercado(`${icone("acordo")} Opção exercida: ${dinheiro(r.valor)} ao ${r.clube}. Agora acerte o contrato com ${r.jogador}.`);
  await carregarMercado();
  await abrirNegociacao(r.negociacao_id);
}

export const STATUS_NEG = {
  aberta: ["chip-perto", "Falta o contrato"], fechada: ["chip-batida", "Contratado"],
  desistiu: ["chip-longe", "Desistiu"], expirada: ["", "Expirou"],
};

// o mercado alimenta a Central do Elenco, a Central de Transferências (v1.7)
// e os cards do hub
export function renderMercado(m, observados) {
  renderElenco(m);
  renderTransferencias(m, observados);
  marcarHubMercado({
    janelaAberta: m.janela_aberta,
    total: m.elenco.length,
    acabando: m.elenco.filter((f) => f.contrato_anos <= 1).length,
    aVenda: m.elenco.filter((f) => f.a_venda).length,
    ofertas: m.ofertas_recebidas.filter((o) => o.status === "aberta").length,
  });
}

export function ligarBotoesMercado(container) {
  container.querySelectorAll("button.transf").forEach((b) =>
    b.addEventListener("click", () => cliqueMercado(b))
  );
  ligarEmprestimo(container);
}

// propor, aceitar, recusar e contrapropor pedem dois cliques (sem
// alert/confirm, que travam a página); "acertar contrato" só abre
export function cliqueMercado(botao) {
  const acao = botao.dataset.acao;
  if (acao === "negociacao") return abrirNegociacao(Number(botao.dataset.neg));
  if (botao.dataset.confirmar !== "1") {
    botao.dataset.confirmar = "1";
    botao.dataset.rotulo = botao.textContent;
    botao.textContent = "Confirmar?";
    return;
  }
  const id = Number(botao.dataset.id);
  if (acao === "propor") {
    const campo = document.querySelector(`input[data-proposta="${id}"]`);
    const valor = Number(botao.dataset.valor || (campo && campo.value));
    return propor(id, valor);
  }
  if (acao === "livre") return contratarLivre(botao.dataset.nome);
  if (acao === "emprestar") {
    // aceitar a contraproposta repete os termos dela; senão, os do formulário
    const box = botao.closest(".tr-emprestimo");
    const campo = (k) => box.querySelector(`[data-emp="${k}"]`);
    const corpo = botao.dataset.valor
      ? { duracao: botao.dataset.duracao, parte_salario: Number(botao.dataset.parte),
          taxa: Number(botao.dataset.valor), opcao: botao.dataset.opcao === "1" }
      : { duracao: campo("duracao").value, parte_salario: Number(campo("parte").value),
          taxa: Number(campo("taxa").value), opcao: campo("opcao").checked };
    return pedirEmprestimo(id, corpo);
  }
  if (acao === "ceder") return cederEmprestado(id, botao.dataset.clube, botao.dataset.duracao);
  if (acao === "opcao") {
    const onde = botao.closest('[data-painel="elenco"]') ? "r-contrato-msg" : "r-mercado-msg";
    return exercerOpcao(Number(botao.dataset.emprestimo), onde);
  }
  // ofertas da CPU (v1.7): o aviso sai no painel onde o botão está
  const oferta = Number(botao.dataset.oferta);
  const onde = botao.closest('[data-painel="elenco"]') ? "r-contrato-msg" : "r-mercado-msg";
  if (acao === "aceitar") return aceitarOferta(oferta, onde);
  if (acao === "recusar") return recusarOferta(oferta, onde);
  if (acao === "contrapropor") {
    const campo = botao.closest(".proposta").querySelector("input[data-contra]");
    return contraproporOferta(oferta, Number(campo.value), onde);
  }
}

// POST com o motivo do 400 visível (o `pedir` genérico só mostra o status);
// `onde` é o parágrafo do aviso (o do mercado ou o da Central do Elenco)
export async function postarMercado(caminho, corpo, ocupadoTexto, { metodo = "POST", onde = "r-mercado-msg" } = {}) {
  limparAviso();
  ocupado(true, ocupadoTexto);
  try {
    const resp = await fetch(api() + caminho, {
      method: metodo,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(corpo),
    });
    const dados = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      // ao lado do mercado (não só no topo da página): o motivo é o que faltou
      avisoMercado(`${icone("nao")} Não deu: ${dados.detail || `HTTP ${resp.status}`}.`, true, onde);
      carregarCaixa();
      return null;
    }
    return dados;
  } catch (e) {
    $("erro").textContent = `Falha no mercado — ${e.message}`;
    return null;
  } finally {
    ocupado(false);
  }
}

export async function propor(jogadorId, valor) {
  const r = await postarMercado(
    `/simulacoes/${estado.simId}/propostas`, { jogador_id: jogadorId, valor }, "Enviando a proposta…"
  );
  if (!r) return carregarMercado();
  const t = r.transferencia;
  const sinal = icone({ aceita: "ok", multa: "multa", contraproposta: "acordo", recusada: "nao" }[r.resposta]);
  let msg = `${sinal} ${r.motivo}`;
  if (r.resposta === "contraproposta") msg += ` — pede ${dinheiro(r.valor_pedido)}`;
  msg += ".";
  if (r.negociacao_id) msg += " Agora acerte o contrato com o jogador.";
  avisoMercado(msg, r.resposta === "recusada");
  carregarCaixa();
  await carregarMercado();
  if (r.negociacao_id) await abrirNegociacao(r.negociacao_id);
}

// ---------- etapa 2 (v1.7): o contrato com o jogador ----------

export async function abrirNegociacao(negId) {
  const d = await pedir(`/simulacoes/${estado.simId}/negociacoes/${negId}`);
  if (!d) return;
  const box = $("m-negociacao");
  if (d.status !== "aberta") { box.innerHTML = ""; delete box.dataset.neg; return; }
  box.dataset.neg = negId;   // a Central fecha o formulário quando ela acabar
  const contra = d.contraproposta;
  // sugestão: a contraproposta, ou o ponto de partida do servidor
  const salario = contra ? contra.salario : d.salario_sugerido;
  const anosSel = contra ? contra.anos : Math.min(3, d.duracao_max);
  const multaSel = contra ? contra.multa : "3x";
  const papelSel = contra ? contra.papel : d.papel_esperado;
  const anos = Array.from({ length: d.duracao_max }, (_, i) => i + 1)
    .map((n) => `<option value="${n}"${n === anosSel ? " selected" : ""}>${n}</option>`).join("");
  const multas = d.opcoes_multa.map((o) => `<option value="${o.opcao}"${o.opcao === multaSel ? " selected" : ""}>` +
    `${MULTA_ROTULO[o.opcao]}${o.valor ? ` (${dinheiro(o.valor)})` : ""}</option>`).join("");
  const papeis = d.papeis.map((p) => `<option value="${p}"${p === papelSel ? " selected" : ""}>${PAPEL_ROTULO[p]}</option>`).join("");
  const origem = d.opcao_compra
    ? `opção de compra: ${dinheiro(d.valor)} ao ${d.clube}`
    : d.clube
      ? `acordo com o ${d.clube} por ${dinheiro(d.valor)}`
      : `sem clube · luvas de ${dinheiro(d.valor)}`;
  const dicas = [
    d.salario_atual != null ? `hoje ganha ${dinheiro(d.salario_atual)} e não aceita menos` : null,
    `o mercado paga ${dinheiro(d.salario_referencia)} a esse overall`,
    `ele espera ser ${PAPEL_ROTULO[d.papel_esperado].toLowerCase()} aqui: prometer mais baixa o pedido`,
    d.clube ? "trocar de clube tem preço" : null,
    d.clube_mais_fraco ? "e descer para um clube mais fraco, mais ainda" : null,
  ].filter(Boolean).join(" · ");
  box.innerHTML = `<article>
    <header><strong>Contrato com ${d.jogador}</strong> · ${d.funcao}, ${d.idade} anos, OVR ${d.overall} · ${origem}</header>
    ${contra ? `<p>${icone("acordo")} Ele pede ${dinheiro(contra.salario)} por ${contra.anos} temp., ${MULTA_ROTULO[contra.multa]}, como ${PAPEL_ROTULO[contra.papel].toLowerCase()}.</p>` : ""}
    <div class="mercado-filtros">
      <label>Salário/temporada <input type="number" id="n-salario" min="1000" step="1000" value="${salario}"></label>
      <label>Temporadas <select id="n-anos">${anos}</select></label>
      <label>Multa <select id="n-multa">${multas}</select></label>
      <label>Papel <select id="n-papel">${papeis}</select></label>
      <button class="transf" id="n-enviar">Propor contrato</button>
      <button class="transf secondary outline" id="n-fechar">Fechar</button>
    </div>
    <small class="bloqueio">${dicas} · ${d.tentativas_restantes} tentativa${d.tentativas_restantes === 1 ? "" : "s"};
      na última recusa ele desiste · jogar a rodada sem contrato desfaz o acordo</small>
  </article>`;
  $("n-fechar").addEventListener("click", () => { box.innerHTML = ""; delete box.dataset.neg; });
  const enviar = $("n-enviar");
  enviar.addEventListener("click", () => {
    if (enviar.dataset.confirmar !== "1") {   // dois cliques, como no resto do mercado
      enviar.dataset.confirmar = "1";
      enviar.textContent = "Confirmar?";
      return;
    }
    proporContrato(negId, {
      salario: Number($("n-salario").value), anos: Number($("n-anos").value),
      multa: $("n-multa").value, papel: $("n-papel").value,
    });
  });
  box.scrollIntoView({ block: "nearest" });
}

export async function proporContrato(negId, contrato) {
  const r = await postarMercado(
    `/simulacoes/${estado.simId}/negociacoes/${negId}/contrato`, contrato, "Conversando com o jogador…"
  );
  if (!r) return abrirNegociacao(negId);
  const sinal = icone({ aceita: "ok", contraproposta: "acordo", recusada: "nao" }[r.resposta]);
  let msg = `${sinal} ${r.motivo}`;
  if (r.resposta === "contraproposta") msg += ` — pede ${dinheiro(r.salario_pedido)} por temporada`;
  msg += ".";
  if (r.status === "desistiu") msg += " Ele desistiu: o acordo caiu.";
  if (r.contrato) {
    msg += ` Assinou por ${dinheiro(r.contrato.salario)}/temp. e ${r.contrato.contrato_anos} temp., ` +
      `como ${PAPEL_ROTULO[r.contrato.papel].toLowerCase()}.`;
  }
  avisoMercado(msg, r.resposta === "recusada");
  carregarCaixa();
  if (r.status === "fechada") return carregarProximaRodada();   // elenco e escalação mudaram
  await carregarMercado();
  if (r.status === "aberta") await abrirNegociacao(negId);
}

// ---------- ofertas da CPU (v1.7) ----------

// as ações de uma oferta aberta: aceitar, recusar ou pedir mais (uma vez)
export function acoesOferta(o) {
  const sugestao = Math.round((o.valor * 1.1) / 10000) * 10000;
  return `<span class="proposta">` +
    `<button class="transf" data-acao="aceitar" data-oferta="${o.oferta_id}">Aceitar</button>` +
    `<button class="transf secondary outline" data-acao="recusar" data-oferta="${o.oferta_id}">Recusar</button>` +
    `<input type="number" min="10000" step="10000" value="${sugestao}" data-contra="${o.oferta_id}" ` +
    `aria-label="Contraproposta por ${o.jogador}">` +
    `<button class="transf secondary" data-acao="contrapropor" data-oferta="${o.oferta_id}">Pedir</button></span>`;
}

// o que muda se aceitar: rival e ídolo levam parte da torcida (v1.4)
export function detalheOferta(o) {
  const encolhe = o.revolta_torcida
    ? ` · a torcida encolhe ${Math.abs(o.revolta_torcida).toLocaleString("pt-BR")}%` : "";
  return [
    o.espontanea ? "sem estar à venda" : "",
    o.seria_titular == null ? "" : o.seria_titular ? "lá seria titular" : "lá seria banco",
  ].filter(Boolean).join(" · ") + encolhe;
}

async function depoisDaVenda(t, onde, extra = "") {
  avisoMercado(`${icone("ok")} ${t.jogador} vendido ao ${t.para_clube} por ${dinheiro(t.valor)}.${extra}`,
    false, onde);
  carregarCaixa();
  await carregarProximaRodada();   // elenco e escalação mudaram
}

export async function aceitarOferta(ofertaId, onde) {
  const t = await postarMercado(
    `/simulacoes/${estado.simId}/ofertas/${ofertaId}/aceitar`, {}, "Fechando a venda…", { onde }
  );
  if (!t) return carregarMercado();
  await depoisDaVenda(t, onde);
}

export async function recusarOferta(ofertaId, onde) {
  const r = await postarMercado(
    `/simulacoes/${estado.simId}/ofertas/${ofertaId}/recusar`, {}, "Recusando…", { onde }
  );
  if (r) {
    const el = $(onde);
    el.classList.remove("ruim");
    el.innerHTML = `${icone("nao")} Recusamos a oferta do ${r.clube} por ${r.jogador}.`;
  }
  await carregarMercado();
}

export async function contraproporOferta(ofertaId, valor, onde) {
  const r = await postarMercado(
    `/simulacoes/${estado.simId}/ofertas/${ofertaId}/contraproposta`, { valor }, "Pedindo mais…", { onde }
  );
  if (!r) return carregarMercado();
  if (r.resposta === "aceita") return depoisDaVenda(r.transferencia, onde, " O clube topou o pedido.");
  avisoMercado(`${icone("nao")} O clube achou ${dinheiro(valor)} demais e retirou a oferta.`, true, onde);
  await carregarMercado();
}

export async function contratarLivre(nome) {
  const r = await postarMercado(
    `/simulacoes/${estado.simId}/livres/contratar`, { nome }, "Chamando o jogador…"
  );
  if (!r) return carregarMercado();
  // sem clube não há etapa 1 (v1.7): vai direto ao contrato
  avisoMercado(`${icone("acordo")} ${r.jogador} topou conversar: acerte o contrato (as luvas são ${dinheiro(r.valor)}).`);
  await carregarMercado();
  await abrirNegociacao(r.negociacao_id);
}
