// Pós-jogo (v2.2): o relatório do último jogo do técnico. Tudo vem de
// GET /pos-jogo, que só lê o que a rodada já gravou: abrir de novo (ou
// depois de recarregar a página) mostra o mesmo relatório e não mexe em nada.
// v2.4: a capa com o estádio (atmosfera.js) e a linha do jogo, as notas do
// time no campo, a vizinhança na tabela e os outros jogos da rodada.

import { $, esconderTudo, estado, limparAviso, ocupado, pedir } from "./nucleo.js";
import { camisa, escudo } from "./identidade.js";
import { cartao, icone } from "./icones.js";
import { linhaEvento, minutoFmt } from "./partida.js";
import { ligarLinks, reais } from "./tabelas.js";
import { nomeLiga } from "./ligas.js";
import { dataLonga, paraData } from "./calendario.js";
import { avancarAposResultado, mostrarRodadaTela } from "./rodada.js";
import { estadioNoturno } from "./atmosfera.js";

const RESULTADO = {
  vitoria: ["v", "Vitória"],
  empate: ["e", "Empate"],
  derrota: ["d", "Derrota"],
};

const chip = (classe, texto) => `<span class="chip${classe ? ` chip-${classe}` : ""}">${texto}</span>`;
const decimal = (n) => n.toFixed(1).replace(".", ",");
const sinal = (n) => (n > 0 ? "+" : "") + (Number.isInteger(n) ? `${n}` : decimal(n));
const nota = decimal;
const sobrenome = (nome) => nome.split(" ").slice(-1)[0];

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

  $("pg-capa").innerHTML = capa(r);
  ligarLinks($("pg-capa"));

  $("pg-notas").innerHTML = notasDoTime(r);
  $("pg-impacto").innerHTML = r.tabela ? impactoLiga(r) : impactoCopa(r);
  $("pg-destaques").innerHTML = destaques(r);

  $("pg-lances").innerHTML = r.eventos.length
    ? r.eventos.map(linhaEvento).join("")
    : `<li class="vazio">Nenhum lance de destaque: foi um jogo travado.</li>`;
  $("pg-stats").innerHTML = r.estatisticas
    ? estatisticas(r)
    : `<p class="vazio">Este jogo da copa é de antes do relatório: só os gols ficaram guardados.</p>`;

  $("pg-outros-titulo").textContent = r.copa ? `Outros jogos · ${r.copa.nome}` : "Outros resultados da rodada";
  $("pg-outros-bloco").hidden = !r.outros_resultados.length;
  $("pg-outros").innerHTML = r.outros_resultados.map(outroJogo).join("");
  ligarLinks($("pg-outros"));

  $("pg-clube-bloco").hidden = !r.mensagens.length;
  $("pg-mensagens").innerHTML = r.mensagens.map((m) =>
    `<li><span class="pg-setor">${m.setor}</span> <b>${m.assunto}</b><p>${m.corpo}</p></li>`
  ).join("");

  $("pg-proximo").innerHTML = proximo(r);
  $("pg-continuar").addEventListener("click", continuar);
  const res = $("pg-resultados");
  if (res) res.addEventListener("click", verResultados);
}

// ---------- 1. a capa: resultado, estádio e a linha do jogo ----------

function capa(r) {
  let [classe, rotulo] = RESULTADO[r.resultado];
  if (r.copa && r.copa.penaltis) {
    const p = r.copa.penaltis;
    [classe, rotulo] = r.copa.classificado
      ? ["v", `Classificado nos pênaltis (${p.pro} x ${p.contra})`]
      : ["d", `Eliminado nos pênaltis (${p.pro} x ${p.contra})`];
  }
  const fundo = estadioNoturno({
    mandante: r.mandante, visitante: r.visitante,
    ocupacao: r.ocupacao ?? 0.5, classico: r.classico, lotado: (r.ocupacao ?? 0) >= 1,
    semente: `pos${r.rodada}${r.copa ? r.copa.fase : ""}`,
  });
  const time = (nome) =>
    `<span class="capa-time${nome === r.clube ? " capa-eu" : ""}">${escudo(nome, 64)}<b>${nome}</b></span>`;
  const publico = r.publico ? `${r.publico.toLocaleString("pt-BR")} pagantes` : "";
  const link = r.partida_id != null
    ? `<a class="partida" data-partida="${r.partida_id}">Ver a partida completa</a>`
    : "";
  return `<div class="cartaz-fundo">${fundo}</div>
    <div class="capa capa-${classe}">
      <span class="capa-resultado">${rotulo}${r.classico ? ` ${chip("longe", "Clássico")}` : ""}</span>
      <div class="capa-placar">
        ${time(r.mandante)}
        <strong>${r.gols_mandante}<small>x</small>${r.gols_visitante}</strong>
        ${time(r.visitante)}
      </div>
      ${linhaDoJogo(r)}
      <p class="capa-rodape">${[publico, link].filter(Boolean).join(" · ")}</p>
    </div>`;
}

// o que entra na linha do jogo e como aparece
const NA_LINHA = {
  gol: ["gol", "Gol"],
  penalti: ["gol", "Gol de pênalti"],
  penalti_perdido: ["perdido", "Pênalti perdido"],
  penalti_defendido: ["perdido", "Pênalti defendido"],
  cartao_amarelo: ["amarelo", "Cartão amarelo"],
  expulsao: ["vermelho", "Expulsão"],
  lesao: ["lesao", "Lesão"],
};

// 0' a 90' (mais os acréscimos): o mandante em cima, o visitante embaixo
function linhaDoJogo(r) {
  const fim = Math.max(90, ...r.eventos.map((e) => e.minuto)) + 1;
  const marcas = r.eventos.filter((e) => NA_LINHA[e.tipo]).map((e) => {
    const [tipo, nome] = NA_LINHA[e.tipo];
    const lado = e.clube === r.visitante ? "baixo" : "cima";
    const desenho = tipo === "gol" || tipo === "perdido"
      ? icone(tipo === "gol" ? "gol" : "nao")
      : tipo === "lesao" ? icone("lesao")
      : cartao(tipo === "vermelho" ? "vermelho" : "");
    const texto = `${minutoFmt(e.minuto)}' ${nome}${e.jogador ? `: ${e.jogador}` : ""} (${e.clube || ""})`;
    return `<li class="lj-marca lj-${lado} lj-${tipo}" style="--m:${(e.minuto / fim) * 100}%" title="${texto}">
      <span class="lj-icone" aria-hidden="true">${desenho}</span>
      ${tipo === "gol" ? `<span class="lj-quem">${minutoFmt(e.minuto)}' ${e.jogador ? sobrenome(e.jogador) : ""}</span>` : ""}
      <span class="sr">${texto}</span></li>`;
  }).join("");
  const regua = [0, 15, 30, 45, 60, 75, 90].map((m) =>
    `<span class="lj-tique${m === 45 ? " lj-intervalo" : ""}" style="--m:${(m / fim) * 100}%">${m === 45 ? "Intervalo" : `${m}'`}</span>`
  ).join("");
  return `<div class="linha-jogo">
    <span class="lj-lado lj-lado-cima">${r.mandante}</span>
    <ol class="lj-trilho" aria-label="Linha do jogo, minuto a minuto">${marcas}</ol>
    <div class="lj-regua" aria-hidden="true">${regua}</div>
    <span class="lj-lado lj-lado-baixo">${r.visitante}</span>
  </div>`;
}

// ---------- 2. as notas do time, no campo ----------

const SETORES = ["Atacante", "Meio-Campo", "Defesa", "Goleiro"];

function classeNota(n) {
  if (n >= 7.5) return "nota-boa";
  if (n < 6) return "nota-ruim";
  return "";
}

function notasDoTime(r) {
  const meus = r.atuacoes.filter((a) => a.clube === r.clube);
  if (!meus.length) return `<p class="vazio">Sem notas guardadas deste jogo.</p>`;
  const titulares = meus.filter((a) => a.titular);
  const entraram = meus.filter((a) => !a.titular);
  const melhor = Math.max(...meus.map((a) => a.nota));

  const peca = (a) => {
    const saiu = a.saiu_min != null
      ? `<span class="nt-saiu" title="Saiu aos ${minutoFmt(a.saiu_min)}'">${icone("troca")}</span>` : "";
    const fez = a.gols ? `<span class="nt-gols" title="${a.gols} ${a.gols === 1 ? "gol" : "gols"}">${icone("gol")}${a.gols > 1 ? a.gols : ""}</span>` : "";
    return `<li class="nt-peca${a.nota === melhor ? " nt-melhor" : ""}" title="${a.jogador} · nota ${nota(a.nota)}">
      <span class="nt-camisa">${camisa(r.clube, { tamanho: 36 })}${saiu}${fez}</span>
      <span class="nt-nota ${classeNota(a.nota)}">${nota(a.nota)}</span>
      <span class="nt-nome">${sobrenome(a.jogador)}</span>
    </li>`;
  };
  const linhas = SETORES.map((setor) => {
    const deles = titulares.filter((a) => a.posicao === setor);
    return deles.length ? `<ol class="nt-linha">${deles.map(peca).join("")}</ol>` : "";
  }).join("");
  const banco = entraram.length
    ? `<p class="nt-banco"><b>Entraram</b> ${entraram.map((a) =>
      `<span>${a.jogador}${a.entrou_min != null ? ` <small>${minutoFmt(a.entrou_min)}'</small>` : ""}
        <span class="nt-nota ${classeNota(a.nota)}">${nota(a.nota)}</span></span>`).join("")}</p>`
    : "";
  return `<div class="nt-campo" role="img" aria-label="Notas dos titulares do ${r.clube}, por setor">${linhas}</div>${banco}`;
}

// ---------- 3. impacto: tabela ou copa ----------

function seta(andou) {
  if (!andou) return `<span class="viz-seta" aria-label="manteve"></span>`;
  const sobe = andou > 0;
  return `<svg class="viz-seta ${sobe ? "sobe" : "desce"}" viewBox="0 0 10 10" width="10" height="10" role="img"
    aria-label="${sobe ? `subiu ${andou}` : `caiu ${-andou}`}"><path d="${sobe ? "M5 1L9 8H1Z" : "M5 9L1 2H9Z"}"/></svg>`;
}

function impactoLiga(r) {
  const t = r.tabela;
  const andou = t.posicao_antes - t.posicao;
  const frase = andou > 0 ? `subiu ${andou}` : andou < 0 ? `caiu ${-andou}` : "manteve a posição";
  const linhas = t.vizinhos.map((v) => `<tr class="${v.clube === r.clube ? "eu" : ""}">
      <td class="viz-pos">${v.posicao}º</td>
      <td>${seta(v.posicao_antes - v.posicao)}</td>
      <td class="viz-clube">${escudo(v.clube, 16)} ${v.clube}</td>
      <td class="viz-num">${v.jogos}</td>
      <td class="viz-num">${v.saldo > 0 ? "+" : ""}${v.saldo}</td>
      <td class="viz-num"><b>${v.pontos}</b></td>
    </tr>`).join("");
  return `<span class="hub-rotulo">${icone("trofeu")} Na tabela</span>
    <p class="pg-numero">${t.posicao}º <small>de ${t.total_clubes}</small></p>
    <p class="pg-detalhe">${t.posicao_antes}º → ${t.posicao}º (${frase}) ·
      ${sinal(t.pontos_ganhos)} ${t.pontos_ganhos === 1 ? "ponto" : "pontos"}, agora ${t.pontos}</p>
    ${linhas ? `<table class="vizinhos"><thead><tr><th></th><th></th><th>Clube</th>
      <th class="viz-num" title="Jogos">J</th><th class="viz-num" title="Saldo de gols">SG</th><th class="viz-num" title="Pontos">P</th></tr></thead>
      <tbody>${linhas}</tbody></table>` : ""}
    ${cargo(r)}`;
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

// ---------- 4. destaques e números ----------

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
  if (d.melhor_do_time && d.melhor_em_campo && d.melhor_do_time.jogador !== d.melhor_em_campo.jogador) {
    cards.push(card("Melhor do time", "camisa", atuacao(d.melhor_do_time)));
  }
  return cards.join("");
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

// ---------- 5. a rodada ----------

function outroJogo(o) {
  const pen = o.penaltis ? `<small>pên. ${o.penaltis[0]}–${o.penaltis[1]}</small>` : "";
  const placar = `<b>${o.gols_mandante}<small>x</small>${o.gols_visitante}</b>`;
  return `<li>
    <span class="ou-time">${o.mandante} ${escudo(o.mandante, 18)}</span>
    ${o.partida_id != null ? `<a class="partida ou-placar" data-partida="${o.partida_id}" title="Ver a partida">${placar}</a>` : `<span class="ou-placar">${placar}</span>`}
    <span class="ou-time">${escudo(o.visitante, 18)} ${o.visitante}</span>
    ${pen}
  </li>`;
}

// ---------- 6. continuidade ----------

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
