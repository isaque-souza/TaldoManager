// Meta da diretoria (v1.0): o card 🎯 das telas da rodada e da temporada.

import { $ } from "./nucleo.js";
import { novoJogo } from "./inicio.js";

const ROTULOS = {
  andamento: { batida: "✅ no caminho", perto: "⚠️ em risco", longe: "❌ longe da meta" },
  fim: { batida: "✅ meta batida", perto: "⚠️ ficou perto", longe: "❌ ficou longe" },
};

// preenche o elemento `id` com a meta da visão `t` (esconde sem meta)
export function renderMeta(id, t) {
  const el = $(id);
  const meta = t && t.meta;
  el.hidden = !meta;
  if (!meta) return;

  const linha = t.classificacao.find((c) => c.clube === t.clube_usuario);
  const comecou = linha && linha.jogos > 0;
  const fim = t.estado !== "em_andamento";
  const cabeca =
    `🎯 Meta da diretoria: <strong>${meta.descricao}</strong> ` +
    `<small>(você tem o ${meta.ranking_forca}º elenco mais forte)</small>`;

  // antes da 1ª rodada a tabela é só ordem alfabética: sem situação
  const ameacado = t.cargo && t.cargo.estado === "ameacado";
  el.className = "meta" + (comecou ? ` meta-${meta.situacao}` : ameacado ? " meta-perto" : "");
  if (!comecou) {
    el.innerHTML = cabeca + avisoCargo(t.cargo);
    return;
  }
  const onde = fim ? `terminou em ${meta.posicao_atual}º` : `agora em ${meta.posicao_atual}º`;
  const rotulo = ROTULOS[fim ? "fim" : "andamento"][meta.situacao];
  el.innerHTML = `${cabeca} · ${onde} — <strong>${rotulo}</strong>` + avisoCargo(t.cargo);
}

// cargo ameaçado: uma temporada longe da meta (a demissão tem bloco próprio)
function avisoCargo(cargo) {
  if (!cargo || cargo.estado !== "ameacado") return "";
  return `<br><strong>⚠️ Cargo ameaçado:</strong> ${cargo.motivo}`;
}

// ---------- fim de carreira (demitido) ----------

export function renderFimDeCarreira(t) {
  const el = $("fim-carreira");
  const fim = t.fim_de_carreira;
  el.hidden = !fim;
  if (!fim) return;

  const plural = (n, um, varios) => `${n} ${n === 1 ? um : varios}`;
  const metas = fim.metas_avaliadas
    ? `<li>🎯 ${fim.metas_batidas} de ${plural(fim.metas_avaliadas, "meta batida", "metas batidas")}</li>`
    : "";
  el.innerHTML = `
    <header><strong>❌ Demitido — fim de carreira</strong></header>
    <p>A diretoria do <strong>${fim.clube}</strong> encerrou o seu trabalho. ${fim.motivo}</p>
    <ul class="balanco">
      <li>📅 ${plural(fim.temporadas, "temporada", "temporadas")}</li>
      <li>🏆 ${plural(fim.titulos, "título", "títulos")}</li>
      ${metas}
      <li>⭐ melhor posição: ${fim.melhor_posicao}º</li>
    </ul>
    <footer><button id="fim-novo-jogo">✚ Novo jogo</button></footer>`;
  $("fim-novo-jogo").addEventListener("click", novoJogo);
}
