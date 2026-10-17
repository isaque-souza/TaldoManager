// Dashboard financeiro de um clube: números principais, caixa rodada a
// rodada, receitas × despesas e a folha por jogador.

import { dinheiro, tabela } from "./tabelas.js";
import { icone } from "./icones.js";

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

function tiles(clube, elenco) {
  const saldo = clube.dinheiro - clube.dinheiro_inicial;
  const folha = elenco.reduce((s, j) => s + (j.salario || 0), 0);
  const maior = elenco.reduce((a, j) => ((j.salario || 0) > (a?.salario || 0) ? j : a), null);
  const sinal = saldo > 0 ? "+" : "";
  return `<div class="tiles">
    ${tile("Caixa atual", dinheiro(clube.dinheiro), `começou com ${dinheiro(clube.dinheiro_inicial)}`, clube.dinheiro < 0)}
    ${tile("Saldo da temporada", sinal + dinheiro(saldo), saldo >= 0 ? "▲ no azul" : "▼ no vermelho", saldo < 0)}
    ${tile("Folha salarial", dinheiro(folha), "por temporada")}
    ${maior ? tile("Maior salário", dinheiro(maior.salario), esc(maior.nome)) : ""}
  </div>`;
}

// ---------- caixa rodada a rodada (linha) ----------

const G = { W: 640, H: 220, padL: 52, padR: 16, padT: 12, padB: 26 };

function graficoCaixa(clube) {
  // ponto 0 = antes da rodada 1 (caixa inicial), depois um por rodada
  const valores = [clube.dinheiro_inicial, ...clube.historico_caixa];
  if (valores.length < 2) {
    return `<p class="vazio">O gráfico aparece depois da primeira rodada.</p>`;
  }
  const n = valores.length - 1;
  const [lo, hi] = faixa(valores);
  const ticks = ticksRedondos(lo, hi);
  const yMin = ticks[0], yMax = ticks[ticks.length - 1];

  const x = (i) => G.padL + (i / n) * (G.W - G.padL - G.padR);
  const y = (v) => G.H - G.padB - ((v - yMin) / (yMax - yMin || 1)) * (G.H - G.padT - G.padB);

  let eixos = "";
  for (const t of ticks) {
    const cls = t === 0 && yMin < 0 ? "base" : "grade";
    eixos += `<line class="${cls}" x1="${G.padL}" x2="${G.W - G.padR}" y1="${y(t)}" y2="${y(t)}"/>`;
    eixos += `<text class="eixo" x="${G.padL - 6}" y="${y(t) + 4}" text-anchor="end">${dinheiro(t)}</text>`;
  }
  const passoX = n > 20 ? 5 : n > 10 ? 2 : 1;
  for (let i = 0; i <= n; i += passoX) {
    eixos += `<text class="eixo" x="${x(i)}" y="${G.H - 8}" text-anchor="middle">${i === 0 ? "início" : `R${i}`}</text>`;
  }

  const pts = valores.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const base = y(yMin);
  const area = `${x(0)},${base} ${pts} ${x(n)},${base}`;
  const fim = valores[n];

  return `<div class="viz caixa" data-valores="${valores.join(",")}">
    <svg viewBox="0 0 ${G.W} ${G.H}" role="img" aria-label="Caixa do clube rodada a rodada">
      ${eixos}
      <polygon class="area" points="${area}"/>
      <polyline class="linha" points="${pts}"/>
      <line class="cruz" x1="0" x2="0" y1="${G.padT}" y2="${G.H - G.padB}" visibility="hidden"/>
      <circle class="ponto" r="4" cx="${x(n)}" cy="${y(fim)}"/>
      <text class="rotulo-fim" x="${x(n) - 8}" y="${y(fim) - 10}" text-anchor="end">${dinheiro(fim)}</text>
      <rect class="alvo" x="${G.padL}" y="0" width="${G.W - G.padL - G.padR}" height="${G.H}"/>
    </svg>
    <div class="dica" hidden><strong></strong><span></span></div>
  </div>`;
}

// crosshair: acha a rodada mais próxima do ponteiro e mostra o caixa
function ligarGraficoCaixa(box) {
  const viz = box.querySelector(".viz.caixa");
  if (!viz) return;
  const valores = viz.dataset.valores.split(",").map(Number);
  const n = valores.length - 1;
  const svg = viz.querySelector("svg");
  const cruz = viz.querySelector(".cruz");
  const ponto = viz.querySelector(".ponto");
  const dica = viz.querySelector(".dica");
  const [lo, hi] = faixa(valores);
  const ticks = ticksRedondos(lo, hi);
  const yMin = ticks[0], yMax = ticks[ticks.length - 1];
  const x = (i) => G.padL + (i / n) * (G.W - G.padL - G.padR);
  const y = (v) => G.H - G.padB - ((v - yMin) / (yMax - yMin || 1)) * (G.H - G.padT - G.padB);
  const fim = () => {
    cruz.setAttribute("visibility", "hidden");
    ponto.setAttribute("cx", x(n));
    ponto.setAttribute("cy", y(valores[n]));
    dica.hidden = true;
  };

  viz.querySelector(".alvo").addEventListener("pointermove", (e) => {
    const r = svg.getBoundingClientRect();
    const sx = ((e.clientX - r.left) / r.width) * G.W;
    const i = Math.max(0, Math.min(n, Math.round(((sx - G.padL) / (G.W - G.padL - G.padR)) * n)));
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
  ].filter(([, v, , sempre]) => sempre || v > 0);

  const max = Math.max(...itens.map(([, v]) => v), 1);
  const linhas = itens.map(([rot, v, tipo, , ic]) => {
    const pct = (v / max) * 100;
    return `<div class="barra-linha" tabindex="0" title="${rot}: ${dinheiro(v)}">
      <span class="barra-rotulo">${icone(ic)} ${rot}</span>
      <span class="barra-trilho"><span class="barra ${tipo}" style="width:calc(${pct.toFixed(1)}% * 0.72)"></span>
        <span class="barra-valor">${dinheiro(tipo === "despesa" ? -v : v)}</span></span>
    </div>`;
  }).join("");

  return `<div class="legenda-fluxo">
      <span><i class="chave receita"></i>Receitas</span><span><i class="chave despesa"></i>Despesas</span>
    </div>
    <div class="barras">${linhas}</div>`;
}

// ---------- folha por jogador ----------

function folhaPorJogador(elenco) {
  const top = [...elenco]
    .sort((a, b) => (b.salario || 0) - (a.salario || 0))
    .slice(0, 6)
    .map((j) => {
      const dif = (j.salario || 0) - (j.salario_referencia || j.salario || 0);
      return {
        ...j,
        sal: dinheiro(j.salario || 0),
        ref: j.salario_referencia ? dinheiro(j.salario_referencia) : "—",
        dif: !j.salario_referencia || dif === 0
          ? "="
          : `${dif > 0 ? "▲ +" : "▼ "}${dinheiro(dif)}`,
      };
    });
  return tabela(top, [
    ["nome", "Jogador"], ["posicao", "Pos."], ["overall", "OVR"],
    ["sal", "Salário"], ["ref", "Mercado paga"], ["dif", "Diferença"],
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
      <article>
        <header><strong>Maiores salários</strong> <small class="bloqueio">▲ ganha mais que o mercado paga</small></header>
        ${folhaPorJogador(elenco)}
      </article>
    </section>`;
  ligarGraficoCaixa(container);
}
