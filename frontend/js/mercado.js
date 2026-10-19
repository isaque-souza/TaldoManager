// Mercado de transferências: propostas de compra (em duas etapas, v1.7: o
// valor com o clube e depois o contrato com o jogador) e ofertas de venda.
// As telas ficam na Central de Transferências (transferencias.js) e na
// Central do Elenco (elenco.js); aqui ficam as ações.

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
  });
}

export function ligarBotoesMercado(container) {
  container.querySelectorAll("button.transf").forEach((b) =>
    b.addEventListener("click", () => cliqueMercado(b))
  );
}

// propor e vender pedem dois cliques (sem alert/confirm, que travam a página);
// "ver ofertas" e "acertar contrato" só abrem, então vão direto
export function cliqueMercado(botao) {
  const acao = botao.dataset.acao;
  if (acao === "ofertas") return mostrarOfertas(Number(botao.dataset.id));
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
  if (acao === "vender") return vender(id, botao.dataset.clube);
  if (acao === "livre") return contratarLivre(botao.dataset.nome);
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
  const origem = d.clube
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

export async function mostrarOfertas(jogadorId) {
  const d = await pedir(`/simulacoes/${estado.simId}/jogadores/${jogadorId}/ofertas`);
  if (!d) return;
  // a torcida encolhe se for para o rival ou se ele for ídolo (v1.4)
  const encolhe = (o) => `a torcida vai encolher ${Math.abs(o.revolta_torcida).toLocaleString("pt-BR")}%`;
  const linhas = d.ofertas.map((o) => ({
    clube_fmt: o.rival
      ? `${icone("rival", "rival")} ${o.clube} (rival — ${encolhe(o)})`
      : o.revolta_torcida ? `${o.clube} (ídolo — ${encolhe(o)})` : o.clube,
    valor_fmt: dinheiro(o.valor),
    papel: o.seria_titular ? "seria titular" : "seria banco",
    acao: `<button class="transf" data-acao="vender" data-id="${jogadorId}" data-clube="${o.clube}">Aceitar</button>`,
  }));
  const box = $("m-ofertas");
  box.innerHTML =
    `<article><header><strong>Ofertas por ${d.jogador}</strong> · valor de mercado ${dinheiro(d.valor_mercado)}</header>` +
    tabela(linhas, [["clube_fmt", "Clube"], ["valor_fmt", "Oferta"], ["papel", "Lá ele"], ["acao", ""]]) +
    `</article>`;
  ligarBotoesMercado(box);
  box.scrollIntoView({ block: "nearest" });
}

export async function vender(jogadorId, clube) {
  const t = await postarMercado(
    `/simulacoes/${estado.simId}/vendas`, { jogador_id: jogadorId, clube }, "Fechando a venda…",
    { onde: "r-contrato-msg" }
  );
  if (!t) return carregarMercado();
  avisoMercado(`${icone("ok")} ${t.jogador} vendido ao ${t.para_clube} por ${dinheiro(t.valor)}.`,
    false, "r-contrato-msg");
  carregarCaixa();
  await carregarProximaRodada();   // elenco e escalação mudaram
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
