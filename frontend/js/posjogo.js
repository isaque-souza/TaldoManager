// Pós-jogo (v2.2): o relatório do último jogo do técnico. Tudo vem de
// GET /pos-jogo, que só lê o que a rodada já gravou: abrir de novo (ou
// depois de recarregar a página) mostra o mesmo relatório e não mexe em nada.

import { $, esconderTudo, estado, limparAviso, ocupado, pedir } from "./nucleo.js";
import { escudo } from "./identidade.js";
import { icone } from "./icones.js";
import { linhaEvento } from "./partida.js";
import { ligarLinks, reais } from "./tabelas.js";
import { nomeLiga } from "./ligas.js";
import { ROTULOS } from "./diretoria.js";
import { dataLonga, paraData } from "./calendario.js";
import { avancarAposResultado, mostrarRodadaTela } from "./rodada.js";

const RESULTADO = {
  vitoria: ["v", "Vitória"],
  empate: ["e", "Empate"],
  derrota: ["d", "Derrota"],
};

// o selo do desempenho: verde acima, neutro no esperado, vermelho abaixo
const DESEMPENHO_CHIP = {
  muito_acima: "batida", acima: "batida", esperado: "", abaixo: "perto", muito_abaixo: "longe",
};

const MOMENTO = {
  gol_da_vitoria: "Gol da vitória",
  gol_do_empate: "Gol do empate",
  penalti_perdido: "Pênalti perdido",
  penalti_defendido: "Pênalti defendido",
  expulsao: "Expulsão",
};

const chip = (classe, texto) => `<span class="chip${classe ? ` chip-${classe}` : ""}">${texto}</span>`;
const minuto = (m) => (m > 90 ? `90+${m - 90}'` : `${m}'`);
const decimal = (n) => n.toFixed(1).replace(".", ",");
const sinal = (n) => (n > 0 ? "+" : "") + (Number.isInteger(n) ? `${n}` : decimal(n));
const nota = decimal;

let atual = null;   // o relatório na tela

export async function abrirPosJogo() {
  limparAviso();
  ocupado(true, "Preparando o relatório…");
  const r = await pedir(`/simulacoes/${estado.simId}/pos-jogo`);
  ocupado(false);
  if (!r) return;
  atual = r;
  render(r);
}

function render(r) {
  esconderTudo();
  $("posjogo").hidden = false;
  window.scrollTo(0, 0);

  $("pg-titulo").textContent = r.copa
    ? `Apito final · Copa · ${r.copa.nome}`
    : `Apito final · ${nomeLiga(r.liga)}`;
  const quando = dataLonga(paraData(r.data));
  $("pg-confronto").innerHTML = r.copa
    ? `${quando} <small>${r.mando === "casa" ? "em casa" : "fora"}</small>`
    : `Rodada ${r.rodada} de ${r.total_rodadas} <small>${quando} · ${r.mando === "casa" ? "em casa" : "fora"}</small>`;

  $("pg-placar").innerHTML = placar(r);
  ligarLinks($("pg-placar"));
  $("pg-expectativa").innerHTML = expectativa(r);
  $("pg-impacto").innerHTML = r.tabela ? impactoLiga(r) : impactoCopa(r);
  $("pg-destaques").innerHTML = destaques(r);

  $("pg-lances").innerHTML = r.eventos.length
    ? r.eventos.map(linhaEvento).join("")
    : `<li class="vazio">Nenhum lance de destaque: foi um jogo travado.</li>`;
  $("pg-stats").innerHTML = r.estatisticas
    ? estatisticas(r)
    : `<p class="vazio">Este jogo da copa é de antes do relatório: só os gols ficaram guardados.</p>`;

  $("pg-clube-bloco").hidden = !r.mensagens.length;
  $("pg-mensagens").innerHTML = r.mensagens.map((m) =>
    `<li><span class="pg-setor">${m.setor}</span> <b>${m.assunto}</b><p>${m.corpo}</p></li>`
  ).join("");

  $("pg-proximo").innerHTML = proximo(r);
  $("pg-continuar").addEventListener("click", continuar);
  const res = $("pg-resultados");
  if (res) res.addEventListener("click", verResultados);
}

// ---------- 1. o resultado ----------

function placar(r) {
  let [classe, rotulo] = RESULTADO[r.resultado];
  if (r.copa && r.copa.penaltis) {
    const p = r.copa.penaltis;
    [classe, rotulo] = r.copa.classificado
      ? ["v", `Classificado nos pênaltis (${p.pro} x ${p.contra})`]
      : ["d", `Eliminado nos pênaltis (${p.pro} x ${p.contra})`];
  }
  const time = (nome) =>
    `<span class="mj-time${nome === r.clube ? " mj-eu" : ""}">${escudo(nome, 44)}<b>${nome}</b></span>`;
  const publico = r.publico ? `${r.publico.toLocaleString("pt-BR")} pagantes` : "";
  const link = r.partida_id != null
    ? `<a class="partida mj-link" data-partida="${r.partida_id}">Ver a partida completa →</a>`
    : "";
  return `<article class="meu-jogo mj-${classe}">
    <span class="mj-resultado">${rotulo}</span>
    <div class="mj-placar">
      ${time(r.mandante)}
      <strong>${r.gols_mandante} <small>x</small> ${r.gols_visitante}</strong>
      ${time(r.visitante)}
    </div>
    <span class="pg-publico">${publico}${link ? `<br>${link}` : ""}</span>
  </article>`;
}

// ---------- 3. expectativa × resultado ----------

function expectativa(r) {
  const e = r.expectativa;
  const vant = e.vantagem > 0 ? "a seu favor" : e.vantagem < 0 ? "contra você" : "nenhuma";
  return `<span class="hub-rotulo">${icone("alvo")} Expectativa × resultado</span>
    <p class="pg-linha"><b>Antes do jogo:</b> ${e.texto}</p>
    <p class="pg-detalhe">Força do elenco ${decimal(e.forca)} contra ${decimal(e.forca_adversario)},
      ${r.mando === "casa" ? "jogando em casa" : "jogando fora"}
      (vantagem ${vant}${e.vantagem ? `: ${sinal(e.vantagem)}` : ""}).</p>
    <p class="pg-linha"><b>Resultado:</b> ${chip(DESEMPENHO_CHIP[e.desempenho.nivel], e.desempenho.texto)}</p>`;
}

// ---------- 4. impacto na carreira ----------

function impactoLiga(r) {
  const t = r.tabela;
  const andou = t.posicao_antes - t.posicao;
  const seta = andou > 0 ? `subiu ${andou}` : andou < 0 ? `caiu ${-andou}` : "manteve a posição";
  let meta = "";
  if (t.meta) {
    const fim = r.temporada_concluida ? "fim" : "andamento";
    const rotulo = ROTULOS[fim][t.meta.situacao];
    const mudou = t.meta.situacao !== t.meta.situacao_antes
      ? ` <small>antes: ${ROTULOS.andamento[t.meta.situacao_antes].toLowerCase()}</small>` : "";
    meta = `<p class="pg-linha"><b>Meta:</b> ${t.meta.descricao} ${chip(t.meta.situacao, rotulo)}${mudou}</p>`;
  }
  return `<span class="hub-rotulo">${icone("trofeu")} Na tabela</span>
    <p class="pg-numero">${t.posicao}º <small>de ${t.total_clubes}</small></p>
    <p class="pg-detalhe">${t.posicao_antes}º → ${t.posicao}º (${seta}) ·
      ${sinal(t.pontos_ganhos)} ${t.pontos_ganhos === 1 ? "ponto" : "pontos"}, agora ${t.pontos}</p>
    ${meta}${cargo(r)}`;
}

function impactoCopa(r) {
  const c = r.copa;
  let destino;
  if (c.campeao) destino = `<p class="pg-numero">Campeão</p>`;
  else if (c.classificado) destino = `<p class="pg-numero">Classificado</p>
    <p class="pg-detalhe">Próxima fase: ${c.proxima_fase.nome.toLowerCase()}</p>`;
  else destino = `<p class="pg-numero pg-ruim">Eliminado</p>
    <p class="pg-detalhe">A copa acabou para nós ${c.nome === "Final" ? "na final" : `nas ${c.nome.toLowerCase()}`}.</p>`;
  const premio = c.premio ? `<p class="pg-linha"><b>Prêmio:</b> ${reais(c.premio)} no caixa</p>` : "";
  return `<span class="hub-rotulo">${icone("trofeu")} Na copa</span>${destino}${premio}
    <p class="pg-detalhe">A tabela da liga não muda com o jogo da copa.</p>${cargo(r)}`;
}

function cargo(r) {
  if (!r.cargo || r.cargo.estado === "mantido") return "";
  const classe = r.cargo.estado === "demitido" ? "longe" : "perto";
  const texto = r.cargo.estado === "demitido" ? "Demitido" : "Cargo ameaçado";
  return `<p class="pg-linha">${chip(classe, texto)} <small>${r.cargo.motivo || ""}</small></p>`;
}

// ---------- 2. análise: destaques e números ----------

function destaques(r) {
  const d = r.destaques;
  const atuacao = (a) => {
    const conta = [a.gols && `${a.gols} ${a.gols === 1 ? "gol" : "gols"}`,
      a.assistencias && `${a.assistencias} ${a.assistencias === 1 ? "assistência" : "assistências"}`]
      .filter(Boolean).join(", ");
    return `<strong>${a.jogador}</strong>
      <small>${a.clube === r.clube ? "" : `${a.clube} · `}${a.posicao} · nota ${nota(a.nota)}${conta ? ` · ${conta}` : ""}</small>`;
  };
  const card = (rotulo, ic, corpo) =>
    `<article class="pg-card"><span class="hub-rotulo">${icone(ic)} ${rotulo}</span>${corpo}</article>`;

  const cards = [];
  cards.push(card("Melhor em campo", "estrela", d.melhor_em_campo
    ? atuacao(d.melhor_em_campo)
    : `<small class="vazio">Sem notas guardadas deste jogo.</small>`));
  cards.push(card("Momento decisivo", "gol", momento(r)));
  if (d.melhor_do_time && d.melhor_em_campo && d.melhor_do_time.jogador !== d.melhor_em_campo.jogador) {
    cards.push(card("Melhor do time", "camisa", atuacao(d.melhor_do_time)));
  } else if (d.pior_do_time) {
    cards.push(card("Menor nota do time", "alerta", atuacao(d.pior_do_time)));
  }
  return cards.join("");
}

function momento(r) {
  if (r.copa && r.copa.penaltis) {
    const p = r.copa.penaltis;
    return `<strong>Disputa de pênaltis</strong>
      <small>${p.pro} x ${p.contra} · ${r.copa.classificado ? "a vaga é nossa" : "a vaga ficou com o " + r.adversario}</small>`;
  }
  const m = r.momento_decisivo;
  if (!m) return `<strong>0 x 0</strong><small>Nenhum lance mudou o jogo.</small>`;
  return `<strong>${MOMENTO[m.tipo_momento]} · ${minuto(m.minuto)}</strong>
    <small>${m.jogador || ""}${m.clube ? ` (${m.clube})` : ""}</small>`;
}

function estatisticas(r) {
  const s = r.estatisticas;
  const linha = (rotulo, a, b, sufixo = "") => {
    const total = a + b || 1;
    return `<div class="st-linha">
      <span class="st-valor">${a}${sufixo}</span>
      <span class="st-rotulo">${rotulo}</span>
      <span class="st-valor st-fora">${b}${sufixo}</span>
      <span class="st-barra"><i style="width:${(a / total) * 100}%"></i></span>
    </div>`;
  };
  return `<p class="pg-detalhe pg-lados"><span>${r.mandante}</span><span>${r.visitante}</span></p>` +
    linha("Posse de bola", s.posse_mandante, 100 - s.posse_mandante, "%") +
    linha("Finalizações", s.finalizacoes_mandante, s.finalizacoes_visitante) +
    linha("Chutes no gol", s.finalizacoes_gol_mandante, s.finalizacoes_gol_visitante) +
    linha("Escanteios", s.escanteios_mandante, s.escanteios_visitante);
}

// ---------- 5. continuidade ----------

function proximo(r) {
  // "Ver resultados" só existe logo depois de jogar (a tela da rodada
  // guarda os resultados); depois de recarregar, volta-se ao menu do clube
  const resultados = estado.faseRodada === "depois"
    ? `<button id="pg-resultados" class="secondary outline">${r.copa ? "Resultados da copa" : "Resultados da rodada"}</button>`
    : "";
  if (!r.proximo) {
    return `<span class="hub-rotulo">${icone("calendario")} Próximo compromisso</span>
      <p class="pg-linha">A temporada acabou.</p>
      <div class="pg-acoes">${resultados}<button id="pg-continuar">${icone("trofeu")} Ver a temporada completa</button></div>`;
  }
  const p = r.proximo;
  const comp = p.copa ? `Copa · ${p.copa.nome}` : `Rodada ${p.rodada}`;
  const quando = dataLonga(paraData(p.data));
  const jogo = p.adversario
    ? `<div class="hub-confronto">
         <span>${escudo(r.clube, 32)}<b>${r.clube}</b></span><i>x</i>
         <span>${escudo(p.adversario, 32)}<b>${p.adversario}</b></span>
       </div>
       <small>${comp} · ${quando} · ${p.mando === "casa" ? "em casa" : "fora"}</small>`
    : `<p class="pg-linha">Folga na rodada ${p.rodada}</p><small>${quando}</small>`;
  return `<span class="hub-rotulo">${icone("calendario")} Próximo compromisso</span>
    ${jogo}
    <div class="pg-acoes">${resultados}<button id="pg-continuar">${icone("play")} Continuar carreira</button></div>`;
}

async function continuar() {
  atual = null;
  // logo depois do jogo, o mesmo caminho de "Próxima rodada"; depois de
  // recarregar, a tela da rodada já é a de antes do próximo jogo
  if (estado.faseRodada === "depois") await avancarAposResultado();
  else mostrarRodadaTela();
}

function verResultados() {
  mostrarRodadaTela();   // faseRodada é "depois": a tela de resultados
}

export function reabrirPosJogo() {
  if (atual) render(atual);
  else abrirPosJogo();
}
