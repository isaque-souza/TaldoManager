// Dashboard financeiro de um clube: números principais, caixa rodada a
// rodada, receitas × despesas e a folha por jogador.

import { dinheiro, reais, tabela } from "./tabelas.js";
import { icone } from "./icones.js";
import { estado } from "./nucleo.js";

// ---------- helpers ----------

// escapa texto vindo da API antes de ir para innerHTML (nomes de clube/jogador)
function esc(texto) {
  const d = document.createElement("div");
  d.textContent = texto;
  return d.innerHTML;
}

// ticks "redondos" para o eixo do dinheiro (0, 5 mi, 10 mi...)
function ticksRedondos(min, max, quantos = 4) {
  const bruto = (max - min) / quantos || 1;
  const mag = 10 ** Math.floor(Math.log10(bruto));
  const passo = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((p) => p >= bruto);
  const ticks = [];
  for (let v = Math.floor(min / passo) * passo; v <= max + passo / 2; v += passo) ticks.push(v);
  return ticks;
}

// faixa do eixo do caixa: é um gráfico de LINHA, então não precisa partir do
// zero (só a barra exige — o comprimento dela é o dado). Partir do zero
// achataria a variação rodada a rodada numa reta. O zero entra se o caixa
// ficar negativo, para a linha da dívida aparecer.
function faixa(valores) {
  let lo = Math.min(...valores);
  let hi = Math.max(...valores);
  if (lo < 0) hi = Math.max(hi, 0);
  const folga = (hi - lo) * 0.1 || Math.abs(hi) * 0.1 || 1;
  return [lo - folga, hi + folga];
}

// ---------- números principais ----------

function tile(rotulo, valor, detalhe = "", negativo = false) {
  return `<div class="tile">
    <span class="tile-rotulo">${rotulo}</span>
    <span class="tile-valor${negativo ? " negativo" : ""}">${valor}</span>
    ${detalhe ? `<span class="tile-detalhe">${detalhe}</span>` : ""}
  </div>`;
}

// torcida (v1.4): cresce com vitórias, clássicos e boa campanha; saves
// antigos não guardam (0) e ficam sem o tile
function tileTorcida(clube) {
  if (!clube.torcedores) return "";
  const ini = clube.torcedores_inicial || clube.torcedores;
  const pct = (clube.torcedores / ini - 1) * 100;
  const fmt = Math.abs(pct).toLocaleString("pt-BR", { maximumFractionDigits: 1 });
  const detalhe = Math.abs(pct) < 0.05
    ? "igual ao início da temporada"
    : `${pct > 0 ? "▲ +" : "▼ −"}${fmt}% na temporada`;
  return tile("Torcida", dinheiro(clube.torcedores), detalhe);
}

function tiles(clube, elenco) {
  const saldo = clube.dinheiro - clube.dinheiro_inicial;
  const folha = elenco.reduce((s, j) => s + (j.salario || 0), 0);
  const maior = elenco.reduce((a, j) => ((j.salario || 0) > (a?.salario || 0) ? j : a), null);
  const sinal = saldo > 0 ? "+" : "";
  return `<div class="tiles">
    ${tile("Caixa atual", reais(clube.dinheiro), `começou com ${reais(clube.dinheiro_inicial)}`, clube.dinheiro < 0)}
    ${tile("Saldo da temporada", sinal + reais(saldo), saldo >= 0 ? "▲ no azul" : "▼ no vermelho", saldo < 0)}
    ${tile("Folha salarial", reais(folha), "por temporada")}
    ${maior ? tile("Maior salário", reais(maior.salario), esc(maior.nome)) : ""}
    ${tileProjecao(clube)}
    ${tileTorcida(clube)}
  </div>`;
}

// onde o caixa termina no ritmo de agora, com o prêmio da posição de hoje
function tileProjecao(clube) {
  const p = projecao(clube);
  if (!p) return "";
  const detalhe = p.premio
    ? `projeção · com o prêmio do ${p.posicao}º (${dinheiro(p.premio)})`
    : "projeção no ritmo atual";
  return tile(`Fim da temporada`, reais(p.comPremio), detalhe, p.comPremio < 0);
}

// ---------- projeção do fim da temporada (v2.4) ----------

// o prêmio pela posição final (app/domain/financas.py: PREMIO_CAMPEAO e
// PREMIO_DEGRAU) — só entra no fim, então a linha do caixa não o mostra
const PREMIO_CAMPEAO = 10_000_000;
const PREMIO_DEGRAU = 500_000;
const premioDa = (posicao) => Math.max(PREMIO_DEGRAU, PREMIO_CAMPEAO - (posicao - 1) * PREMIO_DEGRAU);

// No ritmo das últimas rodadas (a mediana: uma venda ou compra no meio não
// distorce), onde o caixa chega na última rodada, e quanto o prêmio da
// posição de hoje soma em cima. null antes da 3ª rodada ou no fim.
function projecao(clube) {
  const hist = [clube.dinheiro_inicial, ...clube.historico_caixa];
  const feitas = hist.length - 1;
  const sim = estado.temporada;
  const total = sim?.rodadas;
  if (!total || sim.estado !== "em_andamento" || feitas < 3 || feitas >= total) return null;
  const deltas = hist.slice(1).map((v, i) => v - hist[i]).slice(-8).sort((a, b) => a - b);
  const porRodada = deltas[Math.floor(deltas.length / 2)];
  const semPremio = clube.dinheiro + porRodada * (total - feitas);
  const posicao = clube.posicao_final;
  const premio = posicao ? premioDa(posicao) : 0;
  return { feitas, total, porRodada, semPremio, premio, comPremio: semPremio + premio, posicao };
}

// ---------- caixa rodada a rodada (linha) ----------

const G = { W: 640, H: 230, padL: 68, padR: 16, padT: 16, padB: 26 };

// a geometria do gráfico: o eixo x vai até a última rodada da temporada
// quando há projeção (o tracejado ocupa o resto)
function geometria(valores, proj) {
  const n = valores.length - 1;
  const N = proj ? proj.total : n;
  const extra = proj ? [proj.semPremio, proj.comPremio] : [];
  const [lo, hi] = faixa([...valores, ...extra]);
  const ticks = ticksRedondos(lo, hi);
  const yMin = ticks[0], yMax = ticks[ticks.length - 1];
  const x = (i) => G.padL + (i / (N || 1)) * (G.W - G.padL - G.padR);
  const y = (v) => G.H - G.padB - ((v - yMin) / (yMax - yMin || 1)) * (G.H - G.padT - G.padB);
  return { n, N, ticks, yMin, yMax, x, y };
}

function graficoCaixa(clube) {
  // ponto 0 = antes da rodada 1 (caixa inicial), depois um por rodada
  const valores = [clube.dinheiro_inicial, ...clube.historico_caixa];
  if (valores.length < 2) {
    return `<p class="vazio">O gráfico aparece depois da primeira rodada.</p>`;
  }
  const proj = projecao(clube);
  const { n, N, ticks, yMin, x, y } = geometria(valores, proj);

  let eixos = "";
  for (const t of ticks) {
    const cls = t === 0 && yMin < 0 ? "base" : "grade";
    eixos += `<line class="${cls}" x1="${G.padL}" x2="${G.W - G.padR}" y1="${y(t)}" y2="${y(t)}"/>`;
    eixos += `<text class="eixo" x="${G.padL - 6}" y="${y(t) + 4}" text-anchor="end">${dinheiro(t)}</text>`;
  }
  const passoX = N > 20 ? 5 : N > 10 ? 2 : 1;
  for (let i = 0; i <= N; i += passoX) {
    eixos += `<text class="eixo" x="${x(i)}" y="${G.H - 8}" text-anchor="middle">${i === 0 ? "início" : `R${i}`}</text>`;
  }

  const pts = valores.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const base = y(yMin);
  const area = `${x(0)},${base} ${pts} ${x(n)},${base}`;
  const fim = valores[n];
  // cada rodada pinta a área de verde (o caixa subiu) ou vermelho (desceu)
  const faixas = valores.slice(1).map((v, k) => {
    const sobe = v >= valores[k];
    return `<rect class="rodada-${sobe ? "sobe" : "desce"}" x="${x(k).toFixed(1)}" y="${G.padT}" width="${(x(k + 1) - x(k)).toFixed(1)}" height="${(G.H - G.padB - G.padT).toFixed(1)}"/>`;
  }).join("");

  const projetado = proj ? `
      <polyline class="projecao" points="${x(n).toFixed(1)},${y(fim).toFixed(1)} ${x(N).toFixed(1)},${y(proj.semPremio).toFixed(1)}"/>
      ${proj.premio ? `<line class="premio" x1="${x(N)}" x2="${x(N)}" y1="${y(proj.semPremio)}" y2="${y(proj.comPremio)}"/>
      <circle class="ponto-premio" r="4" cx="${x(N)}" cy="${y(proj.comPremio)}"/>
      <text class="rotulo-premio" x="${x(N) - 8}" y="${y(proj.comPremio) - 8}" text-anchor="end">${dinheiro(proj.comPremio)} com o prêmio</text>` : ""}
      <circle class="ponto-proj" r="3" cx="${x(N)}" cy="${y(proj.semPremio)}"/>` : "";

  return `<div class="viz caixa" data-valores="${valores.join(",")}">
    <svg viewBox="0 0 ${G.W} ${G.H}" role="img" aria-label="Caixa do clube rodada a rodada${proj ? `, com a projeção até a rodada ${proj.total}` : ""}">
      ${faixas}${eixos}
      <polygon class="area" points="${area}"/>
      <polyline class="linha" points="${pts}"/>
      ${projetado}
      <line class="cruz" x1="0" x2="0" y1="${G.padT}" y2="${G.H - G.padB}" visibility="hidden"/>
      <circle class="ponto" r="4" cx="${x(n)}" cy="${y(fim)}"/>
      <text class="rotulo-fim" x="${x(n) - 8}" y="${y(fim) - 10}" text-anchor="end">${dinheiro(fim)}</text>
      <rect class="alvo" x="${G.padL}" y="0" width="${G.W - G.padL - G.padR}" height="${G.H}"/>
    </svg>
    <div class="dica" hidden><strong></strong><span></span></div>
    ${proj ? `<p class="caixa-legenda"><span><i class="cl-sobe"></i> rodada no azul</span><span><i class="cl-desce"></i> no vermelho</span>
      <span><i class="cl-proj"></i> no ritmo atual (${proj.porRodada >= 0 ? "+" : ""}${dinheiro(proj.porRodada)} por rodada)</span></p>` : ""}
  </div>`;
}

// crosshair: acha a rodada mais próxima do ponteiro e mostra o caixa
function ligarGraficoCaixa(box, clube) {
  const viz = box.querySelector(".viz.caixa");
  if (!viz) return;
  const valores = viz.dataset.valores.split(",").map(Number);
  const { n, x, y } = geometria(valores, projecao(clube));
  const svg = viz.querySelector("svg");
  const cruz = viz.querySelector(".cruz");
  const ponto = viz.querySelector(".ponto");
  const dica = viz.querySelector(".dica");
  const fim = () => {
    cruz.setAttribute("visibility", "hidden");
    ponto.setAttribute("cx", x(n));
    ponto.setAttribute("cy", y(valores[n]));
    dica.hidden = true;
  };

  viz.querySelector(".alvo").addEventListener("pointermove", (e) => {
    const r = svg.getBoundingClientRect();
    const sx = ((e.clientX - r.left) / r.width) * G.W;
    // passa da última rodada jogada: fica nela (o resto é a projeção)
    const passo = x(1) - x(0);
    const i = Math.max(0, Math.min(n, Math.round((sx - G.padL) / passo)));
    cruz.setAttribute("x1", x(i));
    cruz.setAttribute("x2", x(i));
    cruz.setAttribute("visibility", "visible");
    ponto.setAttribute("cx", x(i));
    ponto.setAttribute("cy", y(valores[i]));
    // o valor lidera, o rótulo vem depois (textContent: nada de HTML aqui)
    dica.querySelector("strong").textContent = dinheiro(valores[i]);
    const delta = i > 0 ? valores[i] - valores[i - 1] : 0;
    dica.querySelector("span").textContent =
      (i === 0 ? "início da temporada" : `após a rodada ${i}`) +
      (i > 0 ? ` · ${delta >= 0 ? "+" : ""}${dinheiro(delta)}` : "");
    dica.hidden = false;
    const px = (x(i) / G.W) * r.width;
    dica.style.left = `${Math.min(Math.max(px, 70), r.width - 70)}px`;
  });
  viz.querySelector(".alvo").addEventListener("pointerleave", fim);
}

// ---------- receitas × despesas (barras horizontais) ----------

function barrasFluxo(clube) {
  // [rótulo, valor, tipo, aparece mesmo zerado?, ícone]
  const itens = [
    ["Cota de TV", clube.receita_tv, "receita", true, "tv"],
    ["Bilheteria", clube.receita_bilheteria, "receita", true, "ingresso"],
    ["Premiação", clube.receita_premiacao, "receita", false, "trofeu"],
    ["Vendas", clube.receita_vendas, "receita", false, "troca"],
    ["Salários", clube.despesa_salarios, "despesa", true, "dinheiro"],
    ["Compras", clube.despesa_compras, "despesa", false, "troca"],
    ["Marketing", clube.despesa_marketing, "despesa", false, "torcida"],
    ["Estádio", clube.despesa_estadio || 0, "despesa", false, "obra"],
    ["Olheiros", clube.despesa_olheiros || 0, "despesa", false, "alvo"],
    ["Base", clube.despesa_base || 0, "despesa", false, "base"],
  ].filter(([, v, , sempre]) => sempre || v > 0);

  const max = Math.max(...itens.map(([, v]) => v), 1);
  const soma = (tipo) => itens.filter(([, , t]) => t === tipo).reduce((a, [, v]) => a + v, 0);
  const entrou = soma("receita"), saiu = soma("despesa");
  const escala = Math.max(entrou, saiu, 1);
  const pilha = (tipo, total) => {
    const partes = itens.filter(([, v, t]) => t === tipo && v > 0).map(([rot, v], k) =>
      `<span class="pilha-parte p${k % 4}" style="width:${((v / escala) * 100).toFixed(2)}%" title="${rot}: ${dinheiro(v)} (${Math.round((v / (total || 1)) * 100)}%)"></span>`).join("");
    return `<div class="pilha-linha"><span class="pilha-rotulo">${tipo === "receita" ? "Entrou" : "Saiu"}</span>
      <span class="pilha ${tipo}">${partes}</span><strong>${dinheiro(total)}</strong></div>`;
  };
  const saldo = entrou - saiu;
  const resumo = `<div class="fluxo-resumo">
      ${pilha("receita", entrou)}${pilha("despesa", saiu)}
      <p class="fluxo-saldo ${saldo < 0 ? "negativo" : "positivo"}">${saldo < 0 ? "Saiu" : "Entrou"} ${dinheiro(Math.abs(saldo))} a ${saldo < 0 ? "mais do que entrou" : "mais do que saiu"}</p>
    </div>`;
  const linhas = itens.map(([rot, v, tipo, , ic]) => {
    const pct = (v / max) * 100;
    return `<div class="barra-linha" tabindex="0" title="${rot}: ${dinheiro(v)}">
      <span class="barra-rotulo">${icone(ic)} ${rot}</span>
      <span class="barra-trilho"><span class="barra ${tipo}" style="width:calc(${pct.toFixed(1)}% * 0.72)"></span>
        <span class="barra-valor">${dinheiro(tipo === "despesa" ? -v : v)}</span></span>
    </div>`;
  }).join("");

  return `${resumo}<div class="legenda-fluxo">
      <span><i class="chave receita"></i>Receitas</span><span><i class="chave despesa"></i>Despesas</span>
    </div>
    <div class="barras">${linhas}</div>`;
}

// ---------- folha por jogador ----------

function folhaPorJogador(elenco) {
  const folha = elenco.reduce((s, j) => s + (j.salario || 0), 0) || 1;
  const top = [...elenco]
    .sort((a, b) => (b.salario || 0) - (a.salario || 0))
    .slice(0, 6)
    .map((j) => {
      // acima do que o mercado paga: o salário em âmbar, com o ▲ da legenda
      const acima = j.salario_referencia && j.salario > j.salario_referencia;
      return {
        ...j,
        sal: acima
          ? `<span class="acima-mercado" title="ganha mais que o mercado paga">▲ ${dinheiro(j.salario)}</span>`
          : dinheiro(j.salario || 0),
        ref: j.salario_referencia ? dinheiro(j.salario_referencia) : "—",
        fatia: `<span class="fatia" title="${(((j.salario || 0) / folha) * 100).toFixed(1)}% da folha"><i style="width:${Math.min(100, ((j.salario || 0) / folha) * 100 * 4).toFixed(1)}%"></i><b>${Math.round(((j.salario || 0) / folha) * 100)}%</b></span>`,
      };
    });
  return tabela(top, [
    ["nome", "Jogador"], ["posicao", "Pos."], ["overall", "OVR"],
    ["sal", "Salário"], ["ref", "Mercado paga"], ["fatia", "Da folha"],
  ]);
}

// ---------- montagem ----------

// `clube` = ClubeInfo da API (com historico_caixa); `elenco` = jogadores com
// salario (e salario_referencia, quando houver)
export function renderDashboard(container, clube, elenco) {
  if (!clube.dinheiro_inicial) {   // saves anteriores à v0.7
    container.innerHTML = "";
    return;
  }
  container.innerHTML = `
    <section class="dashboard">
      ${tiles(clube, elenco)}
      <div class="dash-grade">
        <article>
          <header><strong>Caixa rodada a rodada</strong></header>
          ${graficoCaixa(clube)}
        </article>
        <article>
          <header><strong>De onde vem, para onde vai</strong></header>
          ${barrasFluxo(clube)}
        </article>
      </div>
      <article class="dash-salarios">
        <header><strong>Maiores salários</strong> <small class="bloqueio">▲ ganha mais que o mercado paga</small></header>
        ${folhaPorJogador(elenco)}
      </article>
    </section>`;
  ligarGraficoCaixa(container, clube);
}
