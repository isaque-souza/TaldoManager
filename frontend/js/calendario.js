// Calendário (v2.0): a data do save na faixa da rodada, "Avançar 1 dia" e
// "Continuar". Continuar passa os dias um a um, como o relógio do Football
// Manager: o botão vira "Pausar" e o tempo para sozinho no dia do jogo ou
// quando chega mensagem na caixa de entrada.

import { $, estado, ocupado, pedir } from "./nucleo.js";
import { icone } from "./icones.js";

const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
const SEMANA = ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"];
const PERIODO = {
  pre_temporada: "Pré-temporada", pausa: "Pausa do meio da temporada",
  temporada: "Temporada", dia_de_jogo: "Dia de jogo", concluida: "Temporada encerrada",
};
const ANIMACAO_MS = 1200;   // o tempo total dos dias correndo
const DIA_MS = 600;         // Continuar: um dia a cada 0,6 s, dá tempo de pausar

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
  const qual = cal.copa ? "jogo da copa" : "jogo";
  const jogo = cal.periodo === "dia_de_jogo" ? `${qual} hoje`
    : cal.dias_ate_o_jogo != null ? `${qual} ${diasAte(cal.dias_ate_o_jogo)}` : "";
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

// ---------- Continuar: os dias passando, com pausa ----------

const relogio = { rodando: false, parar: false };

export const relogioRodando = () => relogio.rodando;
export const pausar = () => { relogio.parar = true; };

function avisoDaPausa(chegou) {
  const el = $("r-pausa");
  el.innerHTML = chegou
    ? `${icone("email")} Tempo pausado: chegou mensagem. <button class="link-caixa" type="button">Ler agora</button>`
    : `${icone("pausa")} Tempo pausado.`;
  el.hidden = false;
  el.querySelector(".link-caixa")?.addEventListener("click", () =>
    document.querySelector('#r-hub [data-abrir="caixa"]').click()
  );
}

// `recarregar`: a rodada de novo, quando o tempo para. Sair da tela da
// rodada (ou trocar de save) também para o relógio.
export async function passarDias(recarregar) {
  if (relogio.rodando) return;
  Object.assign(relogio, { rodando: true, parar: false });
  const simId = estado.simId;
  const botao = $("r-jogar");
  botao.innerHTML = `${icone("pausa")} Pausar`;
  $("r-dia").disabled = true;
  $("r-pausa").hidden = true;
  let chegou = false, pausado = false, noJogo = false;
  try {
    for (;;) {
      const cal = await pedir(`/simulacoes/${estado.simId}/calendario/dia`, { method: "POST" });
      if (!cal || estado.simId !== simId) return;
      estado.rodadaInfo.calendario = cal;
      $("rodada-data").innerHTML = textoCalendario(cal);
      noJogo = ehDiaDeJogo(cal);
      chegou = cal.chegou_mensagem;
      if (noJogo || chegou) break;
      botao.innerHTML = `${icone("pausa")} Pausar <small>(${cal.dias_ate_o_jogo === 1 ? "1 dia" : `${cal.dias_ate_o_jogo} dias`} até o jogo)</small>`;
      await new Promise((r) => setTimeout(r, DIA_MS));
      if (relogio.parar || !botao.offsetParent) { pausado = true; break; }
    }
  } finally {
    relogio.rodando = false;
    $("r-dia").disabled = false;
  }
  if (estado.simId !== simId) return;
  await recarregar();
  if (chegou || (pausado && !noJogo)) avisoDaPausa(chegou);
}
