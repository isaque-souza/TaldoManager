// Campo de dinheiro (v1.8): proposta, contraproposta, taxa e salário.
//
// Antes era um <input type="number"> cru ("134730000"). Agora o campo
// mostra "R$ 134,73 mi", aceita o que a pessoa digitaria ("2,5 mi",
// "800 mil", "800k", "1.500.000"), tem −/+ e atalhos (valor de mercado,
// o que ele pede...). O número de verdade fica em data-valor: quem envia
// lê com lerDinheiro(campo), nunca com Number(campo.value).
//
// Os eventos são delegados no document: as telas redesenham o HTML à
// vontade e o campo continua funcionando, sem ligar nada a cada render.

import { reais } from "./tabelas.js";

// "2,5 mi" -> 2500000 · "800 mil" -> 800000 · "1.500.000" -> 1500000
// texto que não é dinheiro -> null
export function parseDinheiro(texto) {
  const t = String(texto).toLowerCase().replace(/r\$|\s/g, "");
  const m = t.match(/^([\d.,]+)(k|mil|m|mi|milh(?:ão|ao|ões|oes))?$/);
  if (!m) return null;
  let num = m[1];
  const mult = !m[2] ? 1 : m[2] === "k" || m[2] === "mil" ? 1e3 : 1e6;
  if (num.includes(",")) {
    // vírgula é o decimal; pontos são milhar
    num = num.replace(/\./g, "").replace(",", ".");
  } else if ((num.match(/\./g) || []).length > 1 || /\.\d{3}$/.test(num)) {
    num = num.replace(/\./g, "");   // "1.500.000" ou "1.500"
  }   // senão o ponto é decimal: "2.5mi"
  const v = Number(num) * mult;
  return Number.isFinite(v) && v > 0 ? Math.round(v) : null;
}

// para editar: "134,73 mi" · "850 mil" · "950" (sem o R$, mais precisão
// que o dinheiro() das tabelas, que arredonda para 1 casa)
function textoEditavel(v) {
  const fmt = (n, casas) => n.toLocaleString("pt-BR", { maximumFractionDigits: casas });
  if (v >= 1e6) return `${fmt(v / 1e6, 2)} mi`;
  if (v >= 1e3) return `${fmt(v / 1e3, 1)} mil`;
  return fmt(v, 0);
}

const mostrar = (v) => `R$ ${textoEditavel(v)}`;

// o campo pronto. `atributos` passa os data-* que a tela já usava para achar
// o campo; `atalhos` são [rótulo, valor] (valores vazios ficam de fora)
export function campoDinheiro({ valor, rotulo, minimo = 1000, atributos = "", atalhos = [] }) {
  const botoes = atalhos
    .filter(([, v]) => v > 0)
    .map(([r, v]) => `<button type="button" class="dinheiro-atalho" data-atalho="${v}"` +
      ` title="${mostrar(v)}">${r}</button>`)
    .join("");
  return `<span class="dinheiro">
    <span class="dinheiro-linha">
      <input type="text" inputmode="decimal" autocomplete="off" class="campo-dinheiro"
        value="${mostrar(valor)}" data-valor="${valor}" data-minimo="${minimo}"
        aria-label="${rotulo}" ${atributos}>
      <button type="button" class="dinheiro-passo" data-passo="-1" aria-label="Diminuir ${rotulo}">−</button>
      <button type="button" class="dinheiro-passo" data-passo="1" aria-label="Aumentar ${rotulo}">+</button>
    </span>
    ${botoes ? `<span class="dinheiro-atalhos">${botoes}</span>` : ""}
    <small class="dinheiro-erro" role="alert" hidden></small>
  </span>`;
}

// o valor do campo, ou null (e o aviso no campo) se o texto não é dinheiro
export function lerDinheiro(campo) {
  if (!campo) return null;
  if (document.activeElement === campo) confirmar(campo);
  return campo.getAttribute("aria-invalid") === "true" ? null : Number(campo.dataset.valor);
}

// a tela mudando o valor (ex.: a taxa sugerida do empréstimo)
export function definirDinheiro(campo, v) {
  campo.dataset.valor = v;
  campo.value = document.activeElement === campo ? textoEditavel(v) : mostrar(v);
  marcarErro(campo, "");
}

function marcarErro(campo, msg) {
  const erro = campo.closest(".dinheiro")?.querySelector(".dinheiro-erro");
  if (msg) campo.setAttribute("aria-invalid", "true");
  else campo.removeAttribute("aria-invalid");
  if (erro) {
    erro.textContent = msg;
    erro.hidden = !msg;
  }
}

// lê o texto digitado; válido vira o novo valor, inválido marca o campo
function confirmar(campo) {
  const v = parseDinheiro(campo.value);
  const minimo = Number(campo.dataset.minimo);
  if (v === null) {
    marcarErro(campo, "Valor inválido: escreva, por exemplo, 2,5 mi ou 800 mil");
    return;
  }
  if (v < minimo) {
    marcarErro(campo, `O mínimo é ${reais(minimo)}`);
    return;
  }
  campo.dataset.valor = v;
  marcarErro(campo, "");
}

// ±5%, arredondado para um valor "redondo" na escala do número
// (134,7 mi anda de 1 mi; 765 mil, de mil)
function passo(campo, direcao) {
  confirmar(campo);
  const atual = Number(campo.dataset.valor);
  const grao = 10 ** Math.max(3, Math.floor(Math.log10(atual)) - 2);
  let novo = Math.round((atual * (1 + 0.05 * direcao)) / grao) * grao;
  if (novo === atual) novo = atual + grao * direcao;
  definirDinheiro(campo, Math.max(novo, Number(campo.dataset.minimo)));
}

// ---------- eventos delegados ----------

const ehCampo = (el) => el instanceof HTMLInputElement && el.classList.contains("campo-dinheiro");

document.addEventListener("focusin", (e) => {
  if (!ehCampo(e.target)) return;
  const campo = e.target;
  // para editar, sem o "R$" (a não ser que o texto já esteja inválido)
  if (campo.getAttribute("aria-invalid") !== "true") campo.value = textoEditavel(Number(campo.dataset.valor));
  campo.select();
});

document.addEventListener("focusout", (e) => {
  if (!ehCampo(e.target)) return;
  const campo = e.target;
  confirmar(campo);
  if (campo.getAttribute("aria-invalid") !== "true") campo.value = mostrar(Number(campo.dataset.valor));
});

document.addEventListener("keydown", (e) => {
  if (!ehCampo(e.target)) return;
  if (e.key === "ArrowUp" || e.key === "ArrowDown") {
    e.preventDefault();
    passo(e.target, e.key === "ArrowUp" ? 1 : -1);
  } else if (e.key === "Enter") {
    confirmar(e.target);
  }
});

document.addEventListener("click", (e) => {
  const b = e.target.closest(".dinheiro-passo, .dinheiro-atalho");
  if (!b) return;
  const campo = b.closest(".dinheiro").querySelector(".campo-dinheiro");
  if (b.classList.contains("dinheiro-passo")) passo(campo, Number(b.dataset.passo));
  else definirDinheiro(campo, Number(b.dataset.atalho));
});
