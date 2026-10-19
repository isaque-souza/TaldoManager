// Ligas (v1.6): todo jogo novo tem a Liga Taldo e a Premier League rodando
// juntas. A visão do save mostra uma liga por vez (a do técnico, ou a
// escolhida aqui).

import { estado, pedir } from "./nucleo.js";

export const NOME_LIGA = { taldo: "Liga Taldo", premier: "Premier League" };

export const nomeLiga = (id) => NOME_LIGA[id] || id;

// abas de liga (só quando o save tem mais de uma)
export function abasLiga(ligas, atual, atributo = "data-liga") {
  if (!ligas || ligas.length < 2) return "";
  return ligas.map((l) => {
    const id = l.id ?? l;
    return `<button type="button" ${atributo}="${id}" class="${id === atual ? "ativa" : ""}">${nomeLiga(id)}</button>`;
  }).join("");
}

// troca a liga mostrada na visão da temporada
export async function verLiga(liga, depois) {
  const dados = await pedir(`/simulacoes/${estado.simId}?liga=${encodeURIComponent(liga)}`);
  if (!dados) return;
  estado.temporada = dados;
  depois();
}

// a mesma lista (confrontos ou resultados) separada por liga: a do técnico
// primeiro, aberta; a outra recolhida
export function porLiga(itens, minha, render) {
  const ligas = [...new Set(itens.map((i) => i.liga || "taldo"))];
  if (ligas.length < 2) return render(itens);
  ligas.sort((a, b) => (a === minha ? -1 : b === minha ? 1 : 0));
  return ligas.map((l) => {
    const corpo = render(itens.filter((i) => (i.liga || "taldo") === l));
    return l === minha
      ? `<h3 class="secao">${nomeLiga(l)}</h3>${corpo}`
      : `<details class="outra-liga"><summary>${nomeLiga(l)}</summary>${corpo}</details>`;
  }).join("");
}

export function ligaDoClube(nome, clubes) {
  return (clubes || []).find((c) => c.nome === nome)?.liga || "taldo";
}

