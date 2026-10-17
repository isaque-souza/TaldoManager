// Mercado de transferências: propostas de compra e ofertas de venda.

import { $, api, estado, limparAviso, ocupado, pedir } from "./nucleo.js";
import { dinheiro, tabela } from "./tabelas.js";
import { carregarProximaRodada, marcarAbasRodada } from "./rodada.js";
import { renderContratos } from "./contratos.js";
import { icone } from "./icones.js";

// ---------- mercado de transferências ----------

export const mercadoFiltro = { posicao: "", valor_max: "" };
export const MERCADO_LIMITE = 40;   // linhas da lista de compra

export async function carregarMercado() {
  const q = new URLSearchParams();
  if (mercadoFiltro.posicao) q.set("posicao", mercadoFiltro.posicao);
  if (mercadoFiltro.valor_max) q.set("valor_max", mercadoFiltro.valor_max);
  const m = await pedir(`/simulacoes/${estado.simId}/mercado?${q}`);
  if (m) renderMercado(m);
}

export const bloqueado = (motivo) =>
  `<span class="bloqueio" title="${motivo}">🔒 ${motivo}</span>`;

// compra: campo de proposta (+ aceitar a contraproposta, se houver)
export function acaoCompra(f) {
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

export function acaoVenda(f) {
  if (f.bloqueio) return bloqueado(f.bloqueio);
  return `<button class="transf secondary" data-acao="ofertas" data-id="${f.jogador_id}">` +
    `Ver ${f.ofertas} oferta${f.ofertas === 1 ? "" : "s"}</button>`;
}

export function linhaMercado(f) {
  return {
    ...f,
    clube_fmt: f.rival ? `⚔️ ${f.clube}` : f.clube,
    valor: dinheiro(f.valor_mercado),
    sal: dinheiro(f.salario),
    multa: f.multa_rescisoria ? dinheiro(f.multa_rescisoria) : "—",
    pot: f.potencial > f.overall ? `${f.potencial} ↑` : f.potencial,
  };
}

export function renderMercado(m) {
  const prox = m.janelas.find((r) => r > m.rodada);
  const status = m.janela_aberta
    ? "🟢 Janela aberta"
    : `🔒 Janela fechada — ${prox ? `reabre antes da rodada ${prox}` : "só na próxima temporada"}`;
  const rivais = m.rivais.length ? ` · ⚔️ rival: ${m.rivais.join(", ")}` : "";
  let html =
    `<p>${status} · caixa <strong class="${m.caixa < 0 ? "negativo" : ""}">${dinheiro(m.caixa)}</strong> · ` +
    `elenco ${m.elenco.length} (mín. ${m.elenco_min}, máx. ${m.elenco_max})${rivais}</p>`;

  if (m.janela_aberta) {
    const pos = ["", "Goleiro", "Defesa", "Meio-Campo", "Atacante"];
    const tetos = [["", "qualquer"], ["1000000", "até 1 mi"], ["5000000", "até 5 mi"],
                   ["10000000", "até 10 mi"], ["20000000", "até 20 mi"]];
    html += `<p class="vazio">Faça uma proposta: o clube aceita, pede mais (contraproposta) ou recusa.
      Até ${m.max_propostas} propostas por jogador em cada janela. Cobrindo a <strong>multa rescisória</strong>,
      o clube não pode recusar. Do rival ⚔️, tudo sai mais caro.</p>`;
    html += `<div class="mercado-filtros">
      <label>Posição <select id="m-posicao">${pos.map((p) =>
        `<option value="${p}"${p === mercadoFiltro.posicao ? " selected" : ""}>${p || "todas"}</option>`).join("")}</select></label>
      <label>Valor <select id="m-valor">${tetos.map(([v, r]) =>
        `<option value="${v}"${v === mercadoFiltro.valor_max ? " selected" : ""}>${r}</option>`).join("")}</select></label>
    </div>`;

    const lista = m.disponiveis.slice(0, MERCADO_LIMITE)
      .map((f) => ({ ...linhaMercado(f), acao: acaoCompra(f) }));
    html += tabela(lista, [
      ["nome", "Jogador"], ["clube_fmt", "Clube"], ["posicao", "Pos."], ["idade", "Idade"],
      ["overall", "OVR"], ["pot", "Pot."], ["valor", "Valor"], ["multa", "Multa"],
      ["sal", "Salário"], ["acao", "Proposta"],
    ]);
    if (m.disponiveis.length > MERCADO_LIMITE) {
      html += `<p class="vazio">Mostrando os ${MERCADO_LIMITE} melhores de ${m.disponiveis.length} — use os filtros.</p>`;
    }

    html += `<h5>Vender do seu elenco</h5><div id="m-ofertas"></div>`;
    html += tabela(m.elenco.map((f) => ({ ...linhaMercado(f), acao: acaoVenda(f) })), [
      ["nome", "Jogador"], ["posicao", "Pos."], ["idade", "Idade"], ["overall", "OVR"],
      ["valor", "Valor"], ["multa", "Multa"], ["sal", "Salário"], ["acao", ""],
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

  renderContratos(m.elenco);
  const acabando = m.elenco.filter((f) => f.contrato_anos <= 1).length;
  marcarAbasRodada({
    mercado: m.janela_aberta
      ? `<span class="luz-aberta" role="img" aria-label="janela aberta"></span>`
      : icone("cadeado", "janela fechada"),
    contratos: acabando ? `<span class="chip chip-perto">${acabando}</span>` : "",
  });

  const box = $("r-mercado");
  box.innerHTML = html;
  if (!m.janela_aberta) return;
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
// "ver ofertas" só lê, então vai direto
export function cliqueMercado(botao) {
  const acao = botao.dataset.acao;
  if (acao === "ofertas") return mostrarOfertas(Number(botao.dataset.id));
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
}

// POST com o motivo do 400 visível (o `pedir` genérico só mostra o status)
export async function postarMercado(caminho, corpo, ocupadoTexto) {
  limparAviso();
  ocupado(true, ocupadoTexto);
  try {
    const resp = await fetch(api() + caminho, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(corpo),
    });
    const dados = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      $("erro").textContent = `Mercado: ${dados.detail || `HTTP ${resp.status}`}`;
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
  const icone = { aceita: "✅", multa: "💥", contraproposta: "🤝", recusada: "❌" }[r.resposta];
  let msg = `${icone} ${r.motivo}`;
  if (r.resposta === "contraproposta") msg += ` — pede ${dinheiro(r.valor_pedido)}`;
  msg += ".";
  if (t) msg += ` ${t.jogador} chegou do ${t.de_clube} por ${dinheiro(t.valor)}.`;
  $("r-mercado-msg").textContent = msg;
  if (t) await carregarProximaRodada();   // elenco e escalação mudaram
  else await carregarMercado();
}

export async function mostrarOfertas(jogadorId) {
  const d = await pedir(`/simulacoes/${estado.simId}/jogadores/${jogadorId}/ofertas`);
  if (!d) return;
  const linhas = d.ofertas.map((o) => ({
    clube_fmt: o.rival ? `⚔️ ${o.clube} (rival — a torcida não vai gostar)` : o.clube,
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
  $("r-mercado-msg").textContent =
    `✅ ${t.jogador} vendido ao ${t.para_clube} por ${dinheiro(t.valor)}.`;
  await carregarProximaRodada();   // elenco e escalação mudaram
}
