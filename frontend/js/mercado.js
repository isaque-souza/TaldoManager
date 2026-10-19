// Mercado de transferências: propostas de compra (em duas etapas, v1.7: o
// valor com o clube e depois o contrato com o jogador) e ofertas de venda.

import { $, api, estado, limparAviso, ocupado, pedir } from "./nucleo.js";
import { dinheiro, tabela } from "./tabelas.js";
import { abrirSecaoRodada, carregarProximaRodada, marcarHubMercado } from "./rodada.js";
import { renderElenco } from "./elenco.js";
import { MULTA_ROTULO, PAPEL_ROTULO } from "./contratos.js";
import { icone, seloIdolo } from "./icones.js";
import { carregarCaixa } from "./caixa.js";
import { destaques, linhaAtributos } from "./atributos.js";
import { posicaoDe, sigla } from "./posicoes.js";

// ---------- mercado de transferências ----------

// a resposta do clube ao lado do mercado, com o caminho para a mensagem
// completa do diretor de futebol (o que faltou, quantas tentativas sobram)
export function avisoMercado(html, ruim = false, onde = "r-mercado-msg") {
  const el = $(onde);
  el.innerHTML = `${html} <button class="link-caixa" type="button">${icone("email")} Ver na caixa de entrada</button>`;
  el.classList.toggle("ruim", ruim);
  el.querySelector(".link-caixa").addEventListener("click", () => abrirSecaoRodada("caixa"));
}

// origem: "clubes" (de outros clubes) ou "livres" (sem clube, v1.6)
export const mercadoFiltro = { posicao: "", valor_max: "", origem: "clubes" };
export const MERCADO_LIMITE = 40;   // linhas da lista de compra

export async function carregarMercado() {
  const q = new URLSearchParams();
  if (mercadoFiltro.posicao) q.set("posicao", mercadoFiltro.posicao);
  if (mercadoFiltro.valor_max) q.set("valor_max", mercadoFiltro.valor_max);
  const m = await pedir(`/simulacoes/${estado.simId}/mercado?${q}`);
  if (m) renderMercado(m);
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

// livre (v1.6): sem negociação — assina pagando as luvas
function acaoLivre(f) {
  const negociando = acaoNegociacao(f);
  if (negociando) return negociando;
  if (f.bloqueio) return bloqueado(f.bloqueio);
  return `<button class="transf" data-acao="livre" data-nome="${f.nome}">` +
    `Negociar (luvas ${dinheiro(f.luvas)})</button>`;
}

const STATUS_NEG = {
  aberta: ["chip-perto", "Falta o contrato"], fechada: ["chip-batida", "Contratado"],
  desistiu: ["chip-longe", "Desistiu"], expirada: ["", "Expirou"],
};

// as negociações da janela (v1.7), no topo do mercado
function blocoNegociacoes(m) {
  if (!m.negociacoes.length) return "";
  const linhas = m.negociacoes.map((n) => ({
    jogador: n.jogador,
    de: n.clube || "sem clube",
    valor_fmt: n.clube ? dinheiro(n.valor) : `${dinheiro(n.valor)} (luvas)`,
    status_fmt: `<span class="chip ${STATUS_NEG[n.status][0]}">${STATUS_NEG[n.status][1]}</span>`,
    acao: n.status === "aberta"
      ? `<button class="transf" data-acao="negociacao" data-neg="${n.negociacao_id}">Acertar contrato</button> ` +
        `<small class="bloqueio">${n.tentativas_restantes} tentativa${n.tentativas_restantes === 1 ? "" : "s"}</small>`
      : "",
  }));
  return `<h5>Negociações desta janela</h5>` + tabela(linhas, [
    ["jogador", "Jogador"], ["de", "De"], ["valor_fmt", "Valor acertado"],
    ["status_fmt", "Situação"], ["acao", ""],
  ]);
}

export function acaoVenda(f) {
  if (f.bloqueio) return bloqueado(f.bloqueio);
  return `<button class="transf secondary" data-acao="ofertas" data-id="${f.jogador_id}">` +
    `Ver ${f.ofertas} oferta${f.ofertas === 1 ? "" : "s"}</button>`;
}

export function linhaMercado(f) {
  return {
    ...f,
    nome: f.idolo ? `${f.nome}&nbsp;${seloIdolo()}` : f.nome,
    posicao: sigla(posicaoDe(f)),
    // os dois melhores atributos; todos na dica (v1.3)
    atributos_fmt: `<span title="${linhaAtributos(f.atributos)}">${destaques(f.atributos)}</span>`,
    clube_fmt: f.rival ? `${icone("rival", "rival")} ${f.clube}` : f.clube,
    valor: dinheiro(f.valor_mercado),
    sal: dinheiro(f.salario),
    multa: f.multa_rescisoria ? dinheiro(f.multa_rescisoria) : "—",
    pot: f.potencial > f.overall ? `${f.potencial} ↑` : f.potencial,
  };
}

export function renderMercado(m) {
  const prox = m.janelas.find((r) => r > m.rodada);
  const status = m.janela_aberta
    ? `<span class="luz-aberta"></span> Janela aberta`
    : `${icone("cadeado")} Janela fechada — ${prox ? `reabre antes da rodada ${prox}` : "só na próxima temporada"}`;
  const rivais = m.rivais.length ? ` · ${icone("rival")} rival: ${m.rivais.join(", ")}` : "";
  let html =
    `<p>${status} · caixa <strong class="${m.caixa < 0 ? "negativo" : ""}">${dinheiro(m.caixa)}</strong> · ` +
    `elenco ${m.elenco.length} (mín. ${m.elenco_min}, máx. ${m.elenco_max})${rivais}</p>`;

  html += `<div id="m-negociacao"></div>`;
  if (m.janela_aberta) html += blocoNegociacoes(m);

  if (m.janela_aberta) {
    const pos = ["", "Goleiro", "Defesa", "Meio-Campo", "Atacante"];
    const tetos = [["", "qualquer"], ["1000000", "até 1 mi"], ["5000000", "até 5 mi"],
                   ["10000000", "até 10 mi"], ["20000000", "até 20 mi"]];
    const livres = mercadoFiltro.origem === "livres";
    html += livres
      ? `<p class="vazio">Jogadores <strong>sem clube</strong>: não há transferência nem negociação. O clube paga
      só as <strong>luvas</strong> (um bônus de assinatura) e o salário, com contrato de 2 temporadas.</p>`
      : `<p class="vazio">Contratar tem duas etapas. <strong>1.</strong> Proposta ao clube: ele aceita, pede mais
      (contraproposta) ou recusa — até ${m.max_propostas} propostas por jogador em cada janela; cobrindo a
      <strong>multa rescisória</strong>, o clube não pode recusar, e do rival (${icone("rival")}) tudo sai mais caro.
      <strong>2.</strong> Contrato com o jogador (salário, anos, multa e papel), antes de jogar a rodada.</p>`;
    const origens = [["clubes", "de outros clubes"], ["livres", `sem clube (${m.livres.length})`]];
    html += `<div class="mercado-filtros">
      <label>Jogadores <select id="m-origem">${origens.map(([v, r]) =>
        `<option value="${v}"${v === mercadoFiltro.origem ? " selected" : ""}>${r}</option>`).join("")}</select></label>
      <label>Posição <select id="m-posicao">${pos.map((p) =>
        `<option value="${p}"${p === mercadoFiltro.posicao ? " selected" : ""}>${p || "todas"}</option>`).join("")}</select></label>
      <label>Valor <select id="m-valor">${tetos.map(([v, r]) =>
        `<option value="${v}"${v === mercadoFiltro.valor_max ? " selected" : ""}>${r}</option>`).join("")}</select></label>
    </div>`;

    const fonte = livres ? m.livres : m.disponiveis;
    const lista = fonte.slice(0, MERCADO_LIMITE).map((f) => livres
      ? { ...linhaMercado(f), luvas_fmt: dinheiro(f.luvas), acao: acaoLivre(f) }
      : { ...linhaMercado(f), acao: acaoCompra(f) });
    html += livres
      ? tabela(lista, [
        ["nome", "Jogador"], ["posicao", "Pos."], ["idade", "Idade"], ["overall", "OVR"],
        ["atributos_fmt", "Destaques"], ["pot", "Pot."], ["valor", "Valor"], ["luvas_fmt", "Luvas"],
        ["sal", "Salário"], ["acao", ""],
      ])
      : tabela(lista, [
        ["nome", "Jogador"], ["clube_fmt", "Clube"], ["posicao", "Pos."], ["idade", "Idade"],
        ["overall", "OVR"], ["atributos_fmt", "Destaques"], ["pot", "Pot."], ["valor", "Valor"], ["multa", "Multa"],
        ["sal", "Salário"], ["acao", "Proposta"],
      ]);
    if (fonte.length > MERCADO_LIMITE) {
      html += `<p class="vazio">Mostrando os ${MERCADO_LIMITE} melhores de ${fonte.length} — use os filtros.</p>`;
    }

    html += `<h5>Vender do seu elenco</h5><div id="m-ofertas"></div>`;
    html += tabela(m.elenco.map((f) => ({ ...linhaMercado(f), acao: acaoVenda(f) })), [
      ["nome", "Jogador"], ["posicao", "Pos."], ["idade", "Idade"], ["overall", "OVR"],
      ["atributos_fmt", "Destaques"], ["valor", "Valor"], ["multa", "Multa"], ["sal", "Salário"], ["acao", ""],
    ]);
  }

  if (m.transferencias.length) {
    html += `<h5>Transferências desta temporada</h5>`;
    html += tabela(m.transferencias.map((t) => ({
      ...t, valor_fmt: dinheiro(t.valor),
      rodada_fmt: t.rodada === 1 ? "pré-temporada" : `antes da R${t.rodada}`,
    })), [
      ["rodada_fmt", "Quando"], ["jogador", "Jogador"], ["posicao", "Pos."],
      ["de_clube", "De"], ["para_clube", "Para"], ["valor_fmt", "Valor"],
    ]);
  }

  renderElenco(m);
  marcarHubMercado({
    janelaAberta: m.janela_aberta,
    total: m.elenco.length,
    acabando: m.elenco.filter((f) => f.contrato_anos <= 1).length,
    aVenda: m.elenco.filter((f) => f.a_venda).length,
  });

  const box = $("r-mercado");
  box.innerHTML = html;
  if (!m.janela_aberta) return;
  $("m-origem").addEventListener("change", (e) => { mercadoFiltro.origem = e.target.value; carregarMercado(); });
  $("m-posicao").addEventListener("change", (e) => { mercadoFiltro.posicao = e.target.value; carregarMercado(); });
  $("m-valor").addEventListener("change", (e) => { mercadoFiltro.valor_max = e.target.value; carregarMercado(); });
  ligarBotoesMercado(box);
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
  if (d.status !== "aberta") { box.innerHTML = ""; return; }
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
  $("n-fechar").addEventListener("click", () => { box.innerHTML = ""; });
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
    `/simulacoes/${estado.simId}/vendas`, { jogador_id: jogadorId, clube }, "Fechando a venda…"
  );
  if (!t) return carregarMercado();
  avisoMercado(`${icone("ok")} ${t.jogador} vendido ao ${t.para_clube} por ${dinheiro(t.valor)}.`);
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
