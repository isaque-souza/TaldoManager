// Meta da diretoria (v1.0): o card 🎯 das telas da rodada e da temporada.

import { $ } from "./nucleo.js";

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
  el.className = "meta" + (comecou ? ` meta-${meta.situacao}` : "");
  if (!comecou) {
    el.innerHTML = cabeca;
    return;
  }
  const onde = fim ? `terminou em ${meta.posicao_atual}º` : `agora em ${meta.posicao_atual}º`;
  const rotulo = ROTULOS[fim ? "fim" : "andamento"][meta.situacao];
  el.innerHTML = `${cabeca} · ${onde} — <strong>${rotulo}</strong>`;
}
