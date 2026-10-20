// Contratos: a renovação (aberta pela ficha da Central do Elenco, v1.7).

import { $, estado, pedir } from "./nucleo.js";
import { reais } from "./tabelas.js";
import { campoDinheiro, lerDinheiro } from "./dinheiro.js";
import { carregarMercado, postarMercado } from "./mercado.js";
import { icone } from "./icones.js";

// ---------- contratos ----------

export const MULTA_ROTULO = { sem: "sem multa", "2x": "2× o valor", "3x": "3× o valor", "5x": "5× o valor" };
export const PAPEL_ROTULO = { titular: "Titular", rotacao: "Rotação", promessa: "Promessa", reserva: "Reserva" };

export async function abrirContrato(jogadorId) {
  const c = await pedir(`/simulacoes/${estado.simId}/jogadores/${jogadorId}/contrato`);
  if (!c) return;
  const contra = c.contraproposta;
  const salario = contra ? contra.salario : c.salario_referencia;
  const anosSel = contra ? contra.anos : Math.min(3, c.duracao_max);
  const multaSel = contra ? contra.multa : "3x";
  const papelSel = contra ? contra.papel : c.papel;
  // o papel prometido entra na conversa (v1.7): prometer mais, ele pede menos
  const papeis = c.papeis
    .map((p) => `<option value="${p}"${p === papelSel ? " selected" : ""}>${PAPEL_ROTULO[p]}</option>`).join("");
  const anos = Array.from({ length: c.duracao_max }, (_, i) => i + 1)
    .map((n) => `<option value="${n}"${n === anosSel ? " selected" : ""}>${n}</option>`).join("");
  const multas = c.opcoes_multa
    .map((o) => `<option value="${o.opcao}"${o.opcao === multaSel ? " selected" : ""}>` +
      `${MULTA_ROTULO[o.opcao]}${o.valor ? ` (${reais(o.valor)})` : ""}</option>`).join("");
  const box = $("c-form");
  box.innerHTML = `<article>
    <header><strong>Renovar com ${c.jogador}</strong> · ${c.idade} anos · OVR ${c.overall} ·
      hoje: ${reais(c.salario)}/temp., ${c.contrato_anos} temp., multa ${c.multa_rescisoria ? reais(c.multa_rescisoria) : "—"}</header>
    ${contra ? `<p>${icone("acordo")} Contraproposta na mesa: ${reais(contra.salario)} por ${contra.anos} temp., ${MULTA_ROTULO[contra.multa]}, como ${PAPEL_ROTULO[contra.papel].toLowerCase()}.</p>` : ""}
    ${c.humor === "quer_sair" ? `<p class="negativo">${icone("nao")} ${c.jogador} quer sair do clube e não aceita renovar enquanto não voltar a jogar.</p>` : ""}
    <div class="mercado-filtros">
      <label>Salário/temporada ${campoDinheiro({
        valor: salario, rotulo: "Salário por temporada", atributos: `id="c-salario"`,
        atalhos: [["Ele pede", contra?.salario], ["Mercado paga", c.salario_referencia], ["Ganha hoje", c.salario]],
      })}</label>
      <label>Temporadas <select id="c-anos">${anos}</select></label>
      <label>Multa <select id="c-multa">${multas}</select></label>
      <label>Papel <select id="c-papel">${papeis}</select></label>
      <button class="transf" id="c-enviar">Propor</button>
      <button class="transf secondary outline" id="c-fechar">Fechar</button>
    </div>
    <small class="bloqueio">Mercado paga ${reais(c.salario_referencia)} a esse overall ·
      prometer um papel maior baixa o pedido, um menor o encarece ·
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
    const salario = lerDinheiro($("c-salario"));
    if (!salario) {   // o aviso já está no campo
      enviar.dataset.confirmar = "";
      enviar.textContent = "Propor";
      return;
    }
    renovar(jogadorId, salario, Number($("c-anos").value), $("c-multa").value, $("c-papel").value);
  });
  box.scrollIntoView({ block: "nearest" });
}

export async function renovar(jogadorId, salario, anos, multa, papel) {
  const r = await postarMercado(
    `/simulacoes/${estado.simId}/renovacoes`, { jogador_id: jogadorId, salario, anos, multa, papel }, "Conversando com o jogador…",
    { onde: "r-contrato-msg" }
  );
  if (!r) return;
  const sinal = icone({ aceita: "ok", contraproposta: "acordo", recusada: "nao" }[r.resposta]);
  let msg = `${sinal} ${r.motivo}`;
  if (r.resposta === "contraproposta") msg += ` — pede ${reais(r.salario_pedido)} por temporada`;
  msg += ".";
  if (r.contrato) {
    msg += ` Novo contrato: ${reais(r.contrato.salario)}/temp. por ${r.contrato.contrato_anos} temp., ` +
      `multa ${r.contrato.multa_rescisoria ? reais(r.contrato.multa_rescisoria) : "—"}, ` +
      `como ${PAPEL_ROTULO[r.contrato.papel].toLowerCase()}.`;
    $("c-form").innerHTML = "";
  }
  $("r-contrato-msg").textContent = msg;
  if (r.contrato) await carregarMercado();
  else await abrirContrato(jogadorId);
}
