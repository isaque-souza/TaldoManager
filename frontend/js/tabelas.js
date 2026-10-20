// Helpers de tabela: células, links e a tabela genérica.

import { navegarPara } from "./nucleo.js";
import { abrirClube } from "./clube.js";
import { abrirPartida } from "./partida.js";
import { abrirJogador } from "./jogador.js";
import { comEscudo } from "./identidade.js";
import { seloIdolo } from "./icones.js";

// ---------- helpers de tabela ----------

export const ehNumero = (v) => typeof v === "number";

// número com vírgula (v1.8): notas e médias vêm do servidor como 6.47
export const decimal = (v, casas = 2) =>
  v.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });

const COLUNAS_NOTA = ["nota", "nota_media", "melhor_nota", "pior_nota"];

export function celula(valor, item, coluna) {
  if (Array.isArray(valor)) {
    return `<span class="forma">${valor
      .map((r) => `<span class="${r}">${r}</span>`)
      .join(" ")}</span>`;
  }
  if (coluna === "clube" && item && item.id != null) {
    return comEscudo(valor, `<a class="clube" data-clube="${item.id}">${valor}</a>`);
  }
  // colunas que são nome de clube ganham o escudo
  if (["clube", "mandante", "visitante"].includes(coluna) && typeof valor === "string" && valor) {
    return comEscudo(valor);
  }
  if (coluna === "nome" && item && item.id != null) {
    return `<a class="jogador" data-jogador="${item.id}">${valor}</a>${item.idolo ? `&nbsp;${seloIdolo()}` : ""}`;
  }
  if (coluna === "placar" && item && item.partida_id != null) {
    return `<a class="partida" data-partida="${item.partida_id}">${valor}</a>`;
  }
  // notas sempre com duas casas (um 10 vira 10,00, como os 7,81 ao lado)
  if (typeof valor === "number" && (!Number.isInteger(valor) || COLUNAS_NOTA.includes(coluna))) {
    return decimal(valor);
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

// fora das tabelas o dinheiro leva o "R$" (v1.8): nas tabelas o título da
// coluna já diz que é dinheiro. -2200000 -> "-R$ 2,2 mi"
export function reais(v) {
  const s = dinheiro(v);
  return s.startsWith("-") ? `-R$ ${s.slice(1)}` : `R$ ${s}`;
}

// um bloco do resumo das centrais (v1.8): rótulo, valor grande e detalhe
export const blocoResumo = (rotulo, valor, detalhe, classe = "") =>
  `<div class="tile"><span class="tile-rotulo">${rotulo}</span>` +
  `<span class="tile-valor ${classe}">${valor}</span><span class="tile-detalhe">${detalhe}</span></div>`;
