// Contratos: lista do elenco e renovação.

import { $, estado, pedir } from "./nucleo.js";
import { dinheiro, tabela } from "./tabelas.js";
import { carregarMercado, postarMercado } from "./mercado.js";

// ---------- contratos ----------

export const MULTA_ROTULO = { sem: "sem multa", "2x": "2× o valor", "3x": "3× o valor", "5x": "5× o valor" };

export function renderContratos(elenco) {
  const linhas = [...elenco]
    .sort((a, b) => a.contrato_anos - b.contrato_anos || b.overall - a.overall)
    .map((f) => ({
      ...f,
      contrato: `${f.contrato_anos} temp.${f.contrato_anos <= 1 ? " ⚠️" : ""}`,
      sal: dinheiro(f.salario),
      ref: f.salario_referencia > f.salario
        ? `<span class="negativo" title="ganha menos que o mercado paga">${dinheiro(f.salario_referencia)}</span>`
        : dinheiro(f.salario_referencia),
      multa: f.multa_rescisoria ? dinheiro(f.multa_rescisoria) : "—",
      acao: `<button class="transf secondary" data-contrato="${f.jogador_id}">Renovar</button>`,
    }));
  const box = $("r-contratos");
  box.innerHTML =
    `<p class="vazio">Renove a qualquer momento. O jogador pede um salário com base no de mercado, ` +
    `mais se for titular ou o craque, e conforme a multa: <strong>sem multa</strong> ou multa alta ` +
    `protegem você de propostas, mas ele cobra por isso.</p>` +
    tabela(linhas, [
      ["nome", "Jogador"], ["posicao", "Pos."], ["idade", "Idade"], ["overall", "OVR"],
      ["contrato", "Contrato"], ["sal", "Salário"], ["ref", "Mercado paga"],
      ["multa", "Multa"], ["acao", ""],
    ]);
  box.querySelectorAll("button[data-contrato]").forEach((b) =>
    b.addEventListener("click", () => abrirContrato(Number(b.dataset.contrato)))
  );
}

export async function abrirContrato(jogadorId) {
  const c = await pedir(`/simulacoes/${estado.simId}/jogadores/${jogadorId}/contrato`);
  if (!c) return;
  const contra = c.contraproposta;
  const salario = contra ? contra.salario : c.salario_referencia;
  const anosSel = contra ? contra.anos : Math.min(3, c.duracao_max);
  const multaSel = contra ? contra.multa : "3x";
  const anos = Array.from({ length: c.duracao_max }, (_, i) => i + 1)
    .map((n) => `<option value="${n}"${n === anosSel ? " selected" : ""}>${n}</option>`).join("");
  const multas = c.opcoes_multa
    .map((o) => `<option value="${o.opcao}"${o.opcao === multaSel ? " selected" : ""}>` +
      `${MULTA_ROTULO[o.opcao]}${o.valor ? ` (${dinheiro(o.valor)})` : ""}</option>`).join("");
  const box = $("c-form");
  box.innerHTML = `<article>
    <header><strong>Renovar com ${c.jogador}</strong> · ${c.idade} anos · OVR ${c.overall} ·
      hoje: ${dinheiro(c.salario)}/temp., ${c.contrato_anos} temp., multa ${c.multa_rescisoria ? dinheiro(c.multa_rescisoria) : "—"}</header>
    ${contra ? `<p>🤝 Contraproposta na mesa: ${dinheiro(contra.salario)} por ${contra.anos} temp., ${MULTA_ROTULO[contra.multa]}.</p>` : ""}
    <div class="mercado-filtros">
      <label>Salário/temporada <input type="number" id="c-salario" min="1000" step="1000" value="${salario}"></label>
      <label>Temporadas <select id="c-anos">${anos}</select></label>
      <label>Multa <select id="c-multa">${multas}</select></label>
      <button class="transf" id="c-enviar">Propor</button>
      <button class="transf secondary outline" id="c-fechar">Fechar</button>
    </div>
    <small class="bloqueio">Mercado paga ${dinheiro(c.salario_referencia)} a esse overall ·
      ${c.tentativas_restantes} tentativa${c.tentativas_restantes === 1 ? "" : "s"} nesta rodada</small>
  </article>`;
  $("c-fechar").addEventListener("click", () => { box.innerHTML = ""; });
  const enviar = $("c-enviar");
  enviar.addEventListener("click", () => {
    if (enviar.dataset.confirmar !== "1") {   // dois cliques, como no mercado
      enviar.dataset.confirmar = "1";
      enviar.textContent = "Confirmar?";
      return;
    }
    renovar(jogadorId, Number($("c-salario").value), Number($("c-anos").value), $("c-multa").value);
  });
  box.scrollIntoView({ block: "nearest" });
}

export async function renovar(jogadorId, salario, anos, multa) {
  const r = await postarMercado(
    `/simulacoes/${estado.simId}/renovacoes`, { jogador_id: jogadorId, salario, anos, multa }, "Conversando com o jogador…"
  );
  if (!r) return;
  const icone = { aceita: "✅", contraproposta: "🤝", recusada: "❌" }[r.resposta];
  let msg = `${icone} ${r.motivo}`;
  if (r.resposta === "contraproposta") msg += ` — pede ${dinheiro(r.salario_pedido)} por temporada`;
  msg += ".";
  if (r.contrato) {
    msg += ` Novo contrato: ${dinheiro(r.contrato.salario)}/temp. por ${r.contrato.contrato_anos} temp., ` +
      `multa ${r.contrato.multa_rescisoria ? dinheiro(r.contrato.multa_rescisoria) : "—"}.`;
    $("c-form").innerHTML = "";
  }
  $("r-contrato-msg").textContent = msg;
  if (r.contrato) await carregarMercado();
  else await abrirContrato(jogadorId);
}
