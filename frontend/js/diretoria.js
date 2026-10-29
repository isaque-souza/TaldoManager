// Meta da diretoria (v1.0): o card da meta nas telas da rodada e da temporada.

import { $ } from "./nucleo.js";
import { novoJogo } from "./inicio.js";
import { icone } from "./icones.js";

export const ROTULOS = {
  andamento: { batida: "No caminho", perto: "Em risco", longe: "Longe da meta" },
  fim: { batida: "Meta batida", perto: "Ficou perto", longe: "Ficou longe" },
};

const chip = (classe, texto) => `<span class="chip chip-${classe}">${texto}</span>`;

// preenche o elemento `id` com a meta da visão `t` (esconde sem meta)
export function renderMeta(id, t) {
  const el = $(id);
  const meta = t && t.meta;
  el.hidden = !meta;
  if (!meta) return;
  // a faixa da rodada esconde o detalhe da força: fica na dica
  el.title = `Você tem o ${meta.ranking_forca}º elenco mais forte`;

  const linha = t.classificacao.find((c) => c.clube === t.clube_usuario);
  const comecou = linha && linha.jogos > 0;
  const fim = t.estado !== "em_andamento";
  const cabeca =
    `${icone("alvo")} <span class="meta-rotulo">Meta da diretoria</span> ` +
    `<strong>${meta.descricao}</strong> ` +
    `<small>você tem o ${meta.ranking_forca}º elenco mais forte</small>`;

  // antes da 1ª rodada a tabela é só ordem alfabética: sem situação
  const ameacado = t.cargo && t.cargo.estado === "ameacado";
  el.className = "meta" + (comecou ? ` meta-${meta.situacao}` : ameacado ? " meta-perto" : "");
  if (!comecou) {
    el.innerHTML = cabeca + avisoCargo(t.cargo);
    return;
  }
  const onde = fim ? `terminou em ${meta.posicao_atual}º` : `agora em ${meta.posicao_atual}º`;
  const rotulo = ROTULOS[fim ? "fim" : "andamento"][meta.situacao];
  el.innerHTML = `${cabeca} <span class="meta-onde">${onde}</span> ` +
    chip(meta.situacao, rotulo) + avisoCargo(t.cargo);
}

// cargo ameaçado: uma temporada longe da meta (a demissão tem bloco próprio)
function avisoCargo(cargo) {
  if (!cargo || cargo.estado !== "ameacado") return "";
  return `<span class="meta-aviso">${chip("perto", "Cargo ameaçado")} ${cargo.motivo}</span>`;
}

// ---------- fim de carreira (demitido) ----------

export function renderFimDeCarreira(t) {
  const el = $("fim-carreira");
  const fim = t.fim_de_carreira;
  el.hidden = !fim;
  if (!fim) return;

  const item = (valor, rotulo) => `<li><b>${valor}</b><span>${rotulo}</span></li>`;
  const plural = (n, um, varios) => (n === 1 ? um : varios);
  const metas = fim.metas_avaliadas
    ? item(`${fim.metas_batidas}/${fim.metas_avaliadas}`, "metas batidas")
    : "";
  el.innerHTML = `
    <header>${chip("longe", "Demitido")} <strong>Fim de carreira</strong></header>
    <p>A diretoria do <strong>${fim.clube}</strong> encerrou o seu trabalho. ${fim.motivo}</p>
    <ul class="balanco">
      ${item(fim.temporadas, plural(fim.temporadas, "temporada", "temporadas"))}
      ${item(fim.titulos, plural(fim.titulos, "título", "títulos"))}
      ${metas}
      ${item(`${fim.melhor_posicao}º`, "melhor posição")}
    </ul>
    <footer><button id="fim-novo-jogo">${icone("mais")} Novo jogo</button></footer>`;
  $("fim-novo-jogo").addEventListener("click", novoJogo);
}
