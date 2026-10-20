// Calendário (v2.0): a data do save na faixa da rodada, "Avançar 1 dia" e
// "Continuar" (até o próximo evento — por enquanto, o dia do jogo). Os dias
// passam na tela um a um, como um relógio, antes de a rodada recarregar.

import { $, estado, ocupado, pedir } from "./nucleo.js";
import { icone } from "./icones.js";

const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
const SEMANA = ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"];
const PERIODO = {
  pre_temporada: "Pré-temporada", pausa: "Pausa do meio da temporada",
  temporada: "Temporada", dia_de_jogo: "Dia de jogo", concluida: "Temporada encerrada",
};
const ANIMACAO_MS = 1200;   // o tempo total dos dias correndo

// "2026-08-08" -> Date no fuso local (sem o "dia anterior" do UTC)
const paraData = (iso) => {
  const [a, m, d] = iso.split("-").map(Number);
  return new Date(a, m - 1, d);
};

export function dataCurta(iso) {
  const d = paraData(iso);
  return `${d.getDate()} ${MESES[d.getMonth()]}`;
}

function dataLonga(d) {
  return `${SEMANA[d.getDay()]}, ${d.getDate()} ${MESES[d.getMonth()]} ${d.getFullYear()}`;
}

const diasAte = (n) => (n === 1 ? "amanhã" : `em ${n} dias`);

export function textoCalendario(cal, quando = paraData(cal.data)) {
  const jogo = cal.periodo === "dia_de_jogo" ? "jogo hoje"
    : cal.dias_ate_o_jogo != null ? `jogo ${diasAte(cal.dias_ate_o_jogo)}` : "";
  return `${icone("calendario")} <b>${dataLonga(quando)}</b>` +
    ` <small>${cal.temporada} · ${PERIODO[cal.periodo] ?? ""}${jogo ? ` · ${jogo}` : ""}</small>`;
}

export const ehDiaDeJogo = (cal) => !cal || cal.periodo === "dia_de_jogo";

// o rótulo do botão principal fora do dia do jogo
export const rotuloContinuar = (cal) =>
  `${icone("avancar")} Continuar <small>(${cal.dias_ate_o_jogo === 1 ? "1 dia" : `${cal.dias_ate_o_jogo} dias`} até o jogo)</small>`;

// os dias correndo na faixa, de `de` até `ate` (Dates); o período só muda
// no último dia (o de antes vale no caminho)
async function animar(de, ate, cal, antes) {
  const dias = Math.round((ate - de) / 86_400_000);
  if (dias <= 0) return;
  const passo = Math.min(80, ANIMACAO_MS / dias);
  const el = $("rodada-data");
  for (let i = 1; i <= dias; i++) {
    const d = new Date(de.getFullYear(), de.getMonth(), de.getDate() + i);
    const faltam = cal.dias_ate_o_jogo + dias - i;
    el.innerHTML = textoCalendario(
      i < dias ? { ...cal, periodo: antes.periodo, dias_ate_o_jogo: faltam } : cal, d,
    );
    await new Promise((r) => setTimeout(r, passo));
  }
}

async function andar(caminho, texto, recarregar) {
  const antes = estado.rodadaInfo?.calendario;
  ocupado(true, texto);
  let cal;
  try {
    cal = await pedir(`/simulacoes/${estado.simId}/calendario/${caminho}`, { method: "POST" });
  } finally {
    ocupado(false);
  }
  if (!cal) return;
  if (antes) await animar(paraData(antes.data), paraData(cal.data), cal, antes);
  await recarregar();
}

export const avancarDia = (recarregar) => andar("dia", "Avançando um dia…", recarregar);
export const continuar = (recarregar) => andar("continuar", "O tempo passa…", recarregar);
