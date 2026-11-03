// Gráfico de pontos por rodada (SVG puro, aba Evolução).

import { estado } from "./nucleo.js";
import { icone } from "./icones.js";
import { identidade } from "./identidade.js";

// ---------- gráfico de pontos por rodada ----------

export function corClube(i) {
  return `hsl(${Math.round((i * 360) / 20)}, 62%, ${i % 2 ? 62 : 46}%)`;
}

export function renderEvolucao() {
  const ev = estado.temporada.evolucao;
  if (!ev || !ev.series.length) return `<p class="vazio">Sem dados.</p>`;

  // v2.4: as linhas dos outros ficam neutras; a do técnico vai em dourado e
  // a escolhida na legenda acende na cor dela. As siglas no fim da linha
  // dizem quem é quem sem precisar da legenda (líder, técnico, escolhido).
  const W = 900, H = 440, padL = 34, padR = 52, padT = 14, padB = 26;
  const rodadas = ev.rodadas;
  const maxR = rodadas[rodadas.length - 1];
  const final = (s) => s.pontos[s.pontos.length - 1];
  const maxP = Math.max(...ev.series.map(final));
  const topo = Math.max(10, Math.ceil(maxP / 10) * 10);

  const x = (r) => padL + ((r - 1) / Math.max(1, maxR - 1)) * (W - padL - padR);
  const y = (p) => H - padB - (p / topo) * (H - padT - padB);

  let grade = "";
  for (let p = 0; p <= topo; p += 10) {
    grade += `<line x1="${padL}" y1="${y(p)}" x2="${W - padR}" y2="${y(p)}" class="grade"/>`;
    grade += `<text x="${padL - 6}" y="${y(p) + 3}" class="eixo" text-anchor="end">${p}</text>`;
  }
  for (let r = 1; r < maxR; r += 5) {
    grade += `<text x="${x(r)}" y="${H - padB + 16}" class="eixo" text-anchor="middle">${r}</text>`;
  }
  grade += `<text x="${x(maxR)}" y="${H - padB + 16}" class="eixo" text-anchor="middle">${maxR}</text>`;

  const meu = estado.temporada.clube_usuario;
  const cor = new Map(ev.series.map((s, i) => [s.clube, corClube(i)]));

  // o técnico por cima de todos
  const ordem = [...ev.series].sort((a, b) => (a.clube === meu) - (b.clube === meu));
  const linhas = ordem
    .map((s) => {
      const pts = s.pontos
        .map((p, k) => `${x(rodadas[k]).toFixed(1)},${y(p).toFixed(1)}`)
        .join(" ");
      const cls = s.clube === meu ? "eu" : "outro";
      return `<polyline class="${cls}" points="${pts}" style="--cor:${cor.get(s.clube)}" data-clube="${s.clube}"><title>${s.clube}: ${final(s)} pts</title></polyline>`;
    })
    .join("");

  // as siglas no fim: uma por clube, empurradas para não se encostarem
  const fim = ev.series
    .map((s) => ({ clube: s.clube, y: y(final(s)), pts: final(s) }))
    .sort((a, b) => a.y - b.y);
  for (let i = 1; i < fim.length; i++) fim[i].y = Math.max(fim[i].y, fim[i - 1].y + 11);
  const lider = fim[0] && fim[0].clube;
  const siglas = fim.map((f) => {
    const cls = f.clube === meu ? "fim eu" : f.clube === lider ? "fim lider" : "fim";
    return `<text x="${W - padR + 6}" y="${(f.y + 3.5).toFixed(1)}" class="${cls}" data-clube="${f.clube}">${identidade(f.clube).sigla} ${f.pts}</text>`;
  }).join("");

  const legenda = [...ev.series]
    .sort((a, b) => final(b) - final(a))
    .map((s) => {
      const marca = s.clube === meu ? ` ${icone("voce", "seu clube")}` : "";
      return `<button data-clube="${s.clube}"${s.clube === meu ? ' class="eu"' : ""}><span class="bolinha" style="background:${s.clube === meu ? "var(--refletor)" : cor.get(s.clube)}"></span>${s.clube}${marca} <strong>${final(s)}</strong></button>`;
    })
    .join("");

  return `
    <div class="grafico grafico-evolucao">
      <p class="grafico-dica">Pontos acumulados por rodada. Toque num clube da legenda para acender a linha dele.</p>
      <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Pontos acumulados por rodada">
        ${grade}${linhas}${siglas}
      </svg>
      <div class="grafico-legenda">
        <button data-clube="" class="limpar">Todos</button>${legenda}
      </div>
    </div>`;
}

export function ligarEvolucao(container) {
  const grafico = container.querySelector(".grafico");
  if (!grafico) return;
  const botoes = container.querySelectorAll(".grafico-legenda button");
  botoes.forEach((b) =>
    b.addEventListener("click", () => {
      const alvo = b.dataset.clube;
      const ativar = alvo && !b.classList.contains("sel");
      botoes.forEach((x) => x.classList.remove("sel"));
      grafico.querySelectorAll("polyline, text.fim").forEach((el) =>
        el.classList.toggle("sel", ativar && el.dataset.clube === alvo)
      );
      grafico.classList.toggle("tem-selecao", !!ativar);
      if (ativar) b.classList.add("sel");
    })
  );
}
