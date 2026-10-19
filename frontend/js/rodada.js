// Modo rodada a rodada: antes (escalação) e depois (resultados).

import { $, api, esconderTudo, estado, limparAviso, navegarPara, ocupado, pedir, pilhaVoltar } from "./nucleo.js";
import { dinheiro, ligarLinks, tabela } from "./tabelas.js";
import { COLUNAS, mostrarTemporada } from "./temporada.js";
import { carregarMercado } from "./mercado.js";
import { carregarLista } from "./saves.js";
import { carregarPlanos, gravarEConferir, planoEmUso, posicionamentoDoEditor, renderEditor, xiDoEditor } from "./editor.js";
import { renderDashboard } from "./financas.js";
import { renderMeta } from "./diretoria.js";
import { escudo } from "./identidade.js";
import { icone } from "./icones.js";
import { abrirPreJogo } from "./prejogo.js";
import { jogarAoVivo } from "./aovivo.js";
import { posicaoDe } from "./posicoes.js";
import { carregarCaixa } from "./caixa.js";
import { carregarMarketing } from "./marketing.js";
import { carregarEstadio } from "./estadio.js";
import { carregarCopa, renderCopaDaRodada } from "./copa.js";
import { porLiga } from "./ligas.js";

// ---------- visão rodada a rodada ----------

export const COLS_ELENCO_RODADA = [
  ["nome", "Jogador"], ["posicao", "Posição"], ["overall", "OVR"],
  ["energia", "Energia"], ["situacao", "Situação"],
];

export async function carregarProximaRodada() {
  await salvarEscalacaoAgora();   // não deixa o recarregamento engolir uma mudança
  const info = await pedir(`/simulacoes/${estado.simId}/rodadas/proxima`);
  if (!info) return;
  estado.rodadaInfo = info;
  estado.rodadaResultado = null;
  estado.faseRodada = "antes";
  mostrarRodadaTela();
}

// ---------- hub do clube (tela "antes da rodada") ----------
// A página inicial do clube é um menu de cards; cada card abre uma seção
// (partida, mercado, elenco, marketing, estádio, finanças) e "← Menu do clube" volta.

// "hub" ou a seção aberta
export function abrirSecaoRodada(secao) {
  estado.abaRodada = secao;
  renderSecaoRodada();
  if (secao === "financas") carregarFinancasRodada();
  window.scrollTo(0, 0);
}

export function renderSecaoRodada() {
  const noHub = estado.abaRodada === "hub";
  if (noHub && estado.rodadaInfo) resumoEscalacao();
  $("r-hub").hidden = !noHub;
  $("r-hub-voltar").hidden = noHub;
  document.querySelectorAll("#rodada-antes [data-painel]").forEach((p) => {
    p.hidden = p.dataset.painel !== estado.abaRodada;
  });
}

// resumo do mercado/elenco nos cards (vem de carregarMercado)
export function marcarHubMercado({ janelaAberta, total, acabando, aVenda }) {
  $("hub-mercado").textContent = janelaAberta ? "Janela aberta" : "Janela fechada";
  $("hub-mercado-info").innerHTML = janelaAberta
    ? `<span class="luz-aberta" aria-hidden="true"></span> compre e venda jogadores`
    : `${icone("cadeado")} só veja o elenco e as transferências`;
  $("hub-elenco").textContent = acabando
    ? `${acabando} ${acabando === 1 ? "contrato acaba" : "contratos acabam"}`
    : `${total} jogadores`;
  const venda = aVenda ? ` · ${aVenda} à venda` : "";
  $("hub-elenco-info").textContent = acabando
    ? `no fim da temporada: renove ou perca de graça${venda}`
    : `nenhum contrato no último ano${venda}`;
  $("hub-elenco").closest(".hub-card").classList.toggle("hub-alerta", acabando > 0);
}

// lê dos seletores (não do rodadaInfo): o técnico pode ter mexido e voltado
function resumoEscalacao() {
  const fora = estado.rodadaInfo.elenco.filter((j) => j.suspenso || j.lesionado).length;
  const tatica = $("r-tatica");
  $("hub-escalacao").textContent = $("r-formacao").value;
  const plano = planoEmUso();
  $("hub-escalacao-info").textContent =
    (plano ? `${plano.nome} · ` : "") +
    tatica.options[tatica.selectedIndex].text + (fora ? ` · ${fora} fora da rodada` : "");
}

function renderHub(info) {
  const t = estado.temporada;
  const loc = info.mando === "casa" ? "em casa" : "fora";
  $("hub-jogo").innerHTML = info.adversario
    ? `<div class="hub-confronto">
         <span>${escudo(info.clube_usuario, 44)}<b>${info.clube_usuario}</b></span>
         <i>x</i>
         <span>${escudo(info.adversario, 44)}<b>${info.adversario}</b></span>
       </div>
       <small>Rodada ${info.rodada} de ${info.total_rodadas} · ${loc}</small>`
    : `<p class="hub-folga">${info.clube_usuario} folga nesta rodada</p>
       <small>Rodada ${info.rodada} de ${info.total_rodadas}</small>`;

  resumoEscalacao();

  const linha = t && t.classificacao.find((c) => c.clube === info.clube_usuario);
  const comecou = linha && linha.jogos > 0;
  $("hub-tabela").textContent = comecou ? `${linha.posicao}º lugar` : "Pré-temporada";
  $("hub-tabela-info").textContent = comecou
    ? `${linha.pontos} pts em ${linha.jogos} ${linha.jogos === 1 ? "jogo" : "jogos"} · saldo ${linha.saldo_gols > 0 ? "+" : ""}${linha.saldo_gols}`
    : "a liga ainda não começou";

  const fin = t && (t.financas || []).find((f) => f.clube === info.clube_usuario);
  $("hub-financas").textContent = fin ? `R$ ${dinheiro(fin.caixa)}` : "—";
  $("hub-financas-info").textContent = fin
    ? `em caixa · folha de R$ ${dinheiro(fin.folha)}/temporada`
    : "receitas, despesas e folha";
}

export async function carregarFinancasRodada() {
  const meu = estado.rodadaInfo && estado.rodadaInfo.clube_usuario;
  const linha = estado.temporada && estado.temporada.classificacao.find((c) => c.clube === meu);
  if (!linha) return;
  const c = await pedir(`/simulacoes/${estado.simId}/clubes/${linha.id}`);
  if (c) renderDashboard($("r-financas"), c.clube, c.elenco);
}

export function mostrarRodadaTela() {
  esconderTudo();
  $("rodada").hidden = false;
  renderMeta("r-meta", estado.temporada);
  if (estado.faseRodada === "depois") renderRodadaDepois();
  else renderRodadaAntes();
}

export function renderRodadaAntes() {
  const info = estado.rodadaInfo;
  if (info.concluida) {   // temporada já terminou — cai na visão completa
    mostrarTemporada();
    return;
  }
  $("rodada-antes").hidden = false;
  $("rodada-depois").hidden = true;

  $("rodada-titulo").textContent =
    `Rodada ${info.rodada} de ${info.total_rodadas}`;
  if (info.adversario) {
    const loc = info.mando === "casa" ? "em casa" : "fora";
    $("rodada-confronto").innerHTML =
      `<span class="confronto">${escudo(info.clube_usuario, 28)} <strong>${info.clube_usuario}</strong>` +
      ` <span class="x">x</span> ${escudo(info.adversario, 28)} <strong>${info.adversario}</strong>` +
      ` <small>(${loc})</small></span> <span class="chip">Pré-jogo</span>`;
  } else {
    $("rodada-confronto").textContent =
      `${info.clube_usuario} folga nesta rodada`;
  }

  $("r-formacao").innerHTML = info.formacoes
    .map((f) => `<option${f === info.formacao ? " selected" : ""}>${f}</option>`)
    .join("");
  $("r-tatica").value = info.tatica || "equilibrado";
  marcarSalvo("");

  renderEditor();
  carregarPlanos().then(resumoEscalacao);   // o card do hub diz o plano

  // com a partida rolando o servidor recusa mudanças na escalação (409):
  // a tela trava junto, em vez de deixar mexer e desfazer calada
  const travado = !!info.transmissao_ativa;
  $("ed-travado").hidden = !travado;
  document.querySelectorAll("#pl-planos, .ed-controles, .editor").forEach((el) => {
    el.inert = travado;
    el.classList.toggle("travado", travado);
  });

  const situacao = (j) => {
    if (j.lesionado) return `<span class="chip chip-longe">Lesionado ${j.rodadas_lesao}r</span>`;
    if (j.suspenso) return `<span class="chip chip-longe">Suspenso ${j.jogos_suspensao}j</span>`;
    if (j.amarelos_ciclo === 4) return `<span class="chip chip-perto">Pendurado</span>`;
    return j.condicao;
  };
  const elenco = [...info.elenco]
    .sort((a, b) => b.overall - a.overall)
    .map((j) => ({ ...j, posicao: posicaoDe(j), situacao: situacao(j) }));
  $("r-elenco").innerHTML = tabela(elenco, COLS_ELENCO_RODADA);

  const marcarEu = (c) =>
    c.mandante === info.clube_usuario || c.visitante === info.clube_usuario
      ? "eu"
      : "";
  // as duas ligas jogam a mesma rodada (v1.6): a do técnico primeiro
  const ligaDe = (lista, meu) =>
    lista.find((c) => c.mandante === meu || c.visitante === meu)?.liga;
  $("r-confrontos").innerHTML = porLiga(
    info.confrontos, ligaDe(info.confrontos, info.clube_usuario),
    (lista) => tabela(lista, [["mandante", "Mandante"], ["visitante", "Visitante"]], marcarEu)
  );

  $("r-jogar").innerHTML = info.transmissao_ativa
    ? `${icone("play")} Voltar para a partida`
    : info.adversario
      ? `${icone("play")} Jogar a rodada ${info.rodada}`
      : `${icone("play")} Avançar a rodada ${info.rodada}`;
  $("r-jogar").disabled = false;

  renderHub(info);
  renderSecaoRodada();
  carregarMercado();
  carregarCaixa();
  carregarMarketing();
  carregarEstadio();
  carregarCopa();
  if (estado.abaRodada === "financas") carregarFinancasRodada();
}

export function renderRodadaDepois() {
  const res = estado.rodadaResultado;
  $("rodada-antes").hidden = true;
  $("rodada-depois").hidden = false;

  $("rodada-titulo").textContent = res.concluida
    ? "Temporada encerrada"
    : `Rodada ${res.rodada_jogada} — resultados`;
  $("rodada-confronto").innerHTML = res.concluida
    ? `${res.campeao} é o campeão <span class="chip chip-batida">Fim de temporada</span>`
    : `<span class="chip">Encerrada</span>`;
  $("r-res-titulo").textContent = `Rodada ${res.rodada_jogada}`;

  const meu = res.clube_usuario;
  const linhas = res.resultados.map((r) => ({
    partida_id: r.partida_id,
    mandante: r.mandante,
    placar: `${r.gols_mandante} x ${r.gols_visitante}`,
    visitante: r.visitante,
    liga: r.liga,
  }));
  const marcarEu = (r) =>
    r.mandante === meu || r.visitante === meu ? "eu" : "";
  const minha = linhas.find((r) => r.mandante === meu || r.visitante === meu)?.liga;
  $("r-resultados").innerHTML = porLiga(linhas, minha, (lista) => tabela(
    lista,
    [["mandante", "Mandante"], ["placar", "Placar"], ["visitante", "Visitante"]],
    marcarEu
  ));
  ligarLinks($("r-resultados"));
  // a copa no meio da semana (v1.6)
  renderCopaDaRodada($("r-copa-rodada"), res.copa, meu);

  $("r-classificacao").innerHTML = tabela(
    res.classificacao,
    COLUNAS.classificacao,
    (c) => (c.clube === meu ? "eu" : "")
  );
  ligarLinks($("r-classificacao"));

  $("r-proxima").innerHTML = res.concluida
    ? `${icone("trofeu")} Ver a temporada completa`
    : `Próxima rodada (${res.rodada_atual}) →`;
}

export async function jogarRodada() {
  if (await enviarRodada()) mostrarRodadaTela();
}

// joga a rodada no servidor e guarda o resultado, sem mostrar — o jogo ao
// vivo (v1.1) mostra a partida antes da tela de resultados
export async function enviarRodada() {
  limparAviso();
  const corpo = decisaoAtual();
  $("r-jogar").disabled = true;
  // o POST já leva a escalação: o autosave pendente vira redundante, e um
  // PATCH em voo precisa terminar antes (senão chega depois da rodada)
  cancelarAutosave();
  await emVoo;
  $("r-mercado-msg").textContent = "";
  $("r-contrato-msg").textContent = "";
  $("c-form").innerHTML = "";
  ocupado(true, `Jogando a rodada ${estado.rodadaInfo.rodada}…`);
  const res = await pedir(`/simulacoes/${estado.simId}/rodadas`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(corpo),
  });
  ocupado(false);
  if (!res) {
    $("r-jogar").disabled = false;
    return null;
  }
  estado.temporada = res;
  estado.rodadaResultado = res;
  estado.faseRodada = "depois";
  pilhaVoltar.length = 0;
  return res;
}

export async function avancarAposResultado() {
  if (estado.rodadaResultado && estado.rodadaResultado.concluida) {
    await carregarLista(estado.simId);
  } else {
    estado.abaRodada = "hub";   // toda rodada nova começa no menu do clube
    await carregarProximaRodada();
  }
}

// ---------- autosave da escalação (v0.9) ----------
// Mexeu na formação, na tática ou num slot: 800 ms sem novas mudanças e a
// escalação vai pro servidor (PATCH /decisao) — sem jogar a rodada.

const ESPERA_AUTOSAVE = 800;
let timerAutosave = null;
let simAgendada = null;   // o save da mudança pendente (pode trocar em 800 ms)
let emVoo = Promise.resolve();

// a escalação na tela, para mandar junto de um POST (o autosave pendente
// vira redundante, e um PATCH em voo precisa terminar antes)
export async function decisaoParaEnviar() {
  cancelarAutosave();
  await emVoo;
  return decisaoAtual();
}

function decisaoAtual() {
  return {
    tatica: $("r-tatica").value,
    formacao: $("r-formacao").value,
    xi: xiDoEditor(),
    posicionamento: posicionamentoDoEditor(),
  };
}

function marcarSalvo(texto, erro = false) {
  $("r-salvo").textContent = texto;
  $("r-salvo").classList.toggle("erro", erro);
}

function cancelarAutosave() {
  clearTimeout(timerAutosave);
  timerAutosave = null;
}

function agendarAutosave() {
  cancelarAutosave();
  simAgendada = estado.simId;
  marcarSalvo("alterações não salvas…");
  timerAutosave = setTimeout(salvarEscalacaoAgora, ESPERA_AUTOSAVE);
}

// grava já a escalação da tela, mesmo sem mudança pendente
export async function salvarJa() {
  agendarAutosave();
  return salvarEscalacaoAgora();
}

// grava já o que estiver pendente (e espera um PATCH em voo terminar)
export async function salvarEscalacaoAgora() {
  if (timerAutosave === null) return emVoo;
  cancelarAutosave();
  const simId = simAgendada;
  const corpo = decisaoAtual();
  marcarSalvo("salvando…");
  emVoo = emVoo.then(async () => {
    // fetch direto em vez de `pedir`: falha de autosave não deve sujar o
    // aviso de erro global — o indicador ao lado da tática já conta
    try {
      const resp = await fetch(`${api()}/simulacoes/${simId}/decisao`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(corpo),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      if (estado.simId === simId) marcarSalvo("salvo");
    } catch {
      if (estado.simId === simId) marcarSalvo("não salvo — será enviado ao jogar", true);
    }
  });
  return emVoo;
}

// fechando/recarregando a aba com mudança pendente: `keepalive` deixa o
// pedido terminar mesmo depois que a página some
window.addEventListener("pagehide", () => {
  if (timerAutosave === null) return;
  cancelarAutosave();
  fetch(`${api()}/simulacoes/${simAgendada}/decisao`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(decisaoAtual()),
    keepalive: true,
  });
});

// tática e formação gravam na hora e o campo é refeito pelo servidor (v1.2)
$("r-tatica").addEventListener("change", () => gravarEConferir());

// "Jogar a rodada" passa pelo pré-jogo (v1.1), que chama jogarRodada; com a
// partida já rolando (v1.2), volta direto para ela
$("r-jogar").addEventListener("click", () =>
  estado.rodadaInfo.transmissao_ativa ? jogarAoVivo() : abrirPreJogo()
);
$("r-proxima").addEventListener("click", avancarAposResultado);
document.querySelectorAll("#r-hub [data-abrir]").forEach((b) =>
  b.addEventListener("click", () => {
    if (b.dataset.abrir === "tabela") navegarPara(mostrarTemporada);
    else abrirSecaoRodada(b.dataset.abrir);
  })
);
$("r-hub-voltar").addEventListener("click", () => abrirSecaoRodada("hub"));
$("ed-voltar-jogo").addEventListener("click", () => jogarAoVivo());
$("r-formacao").addEventListener("change", () => gravarEConferir());
