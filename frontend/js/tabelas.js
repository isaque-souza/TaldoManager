// Helpers de tabela: células, links e a tabela genérica.

import { navegarPara } from "./nucleo.js";
import { abrirClube } from "./clube.js";
import { abrirPartida } from "./partida.js";
import { abrirJogador } from "./jogador.js";

// ---------- helpers de tabela ----------

export const ehNumero = (v) => typeof v === "number";

export function celula(valor, item, coluna) {
  if (Array.isArray(valor)) {
    return `<span class="forma">${valor
      .map((r) => `<span class="${r}">${r}</span>`)
      .join(" ")}</span>`;
  }
  if (coluna === "clube" && item && item.id != null) {
    return `<a class="clube" data-clube="${item.id}">${valor}</a>`;
  }
  if (coluna === "nome" && item && item.id != null) {
    return `<a class="jogador" data-jogador="${item.id}">${valor}</a>`;
  }
  if (coluna === "placar" && item && item.partida_id != null) {
    return `<a class="partida" data-partida="${item.partida_id}">${valor}</a>`;
  }
  return valor ?? "";
}

export function tabela(lista, colunas, classeDaLinha) {
  if (!lista || lista.length === 0) {
    return `<p class="vazio">Nenhum registro.</p>`;
  }
  const head = colunas
    .map(([k, rot]) => `<th class="${ehNumero(lista[0][k]) ? "num" : ""}">${rot}</th>`)
    .join("");
  const linhas = lista
    .map((item) => {
      const cls = classeDaLinha ? classeDaLinha(item) : "";
      const tds = colunas
        .map(
          ([k]) =>
            `<td class="${ehNumero(item[k]) ? "num" : ""}">${celula(item[k], item, k)}</td>`
        )
        .join("");
      return `<tr class="${cls}">${tds}</tr>`;
    })
    .join("");
  return `<figure><table><thead><tr>${head}</tr></thead><tbody>${linhas}</tbody></table></figure>`;
}

// liga os links de navegação (clube / jogador / partida) dentro de um container
export function ligarLinks(container) {
  container.querySelectorAll("a.clube").forEach((a) =>
    a.addEventListener("click", () =>
      navegarPara(() => abrirClube(a.dataset.clube))
    )
  );
  container.querySelectorAll("a.jogador").forEach((a) =>
    a.addEventListener("click", () =>
      navegarPara(() => abrirJogador(a.dataset.jogador))
    )
  );
  container.querySelectorAll("a.partida").forEach((a) =>
    a.addEventListener("click", () =>
      navegarPara(() => abrirPartida(a.dataset.partida))
    )
  );
}

// 31540000 -> "31,5 mi" · 850000 -> "850 mil" · -2200000 -> "-2,2 mi"
export function dinheiro(v) {
  if (v === 0) return "0";
  const sinal = v < 0 ? "-" : "";
  const a = Math.abs(v);
  if (a >= 1_000_000) {
    return `${sinal}${(a / 1_000_000).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} mi`;
  }
  return `${sinal}${Math.round(a / 1_000)} mil`;
}
