// Gráfico de pontos por rodada (SVG puro, aba Evolução).

import { estado } from "./nucleo.js";

// ---------- gráfico de pontos por rodada ----------

export function corClube(i) {
  return `hsl(${Math.round((i * 360) / 20)}, 62%, ${i % 2 ? 62 : 46}%)`;
}

export function renderEvolucao() {
  const ev = estado.temporada.evolucao;
  if (!ev || !ev.series.length) return `<p class="vazio">Sem dados.</p>`;

  const W = 900, H = 460, padL = 34, padR = 12, padT = 12, padB = 26;
  const rodadas = ev.rodadas;
  const maxR = rodadas[rodadas.length - 1];
  const maxP = Math.max(...ev.series.map((s) => s.pontos[s.pontos.length - 1]));
  const topo = Math.max(10, Math.ceil(maxP / 10) * 10);

  const x = (r) => padL + ((r - 1) / (maxR - 1)) * (W - padL - padR);
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

  const linhas = ev.series
    .map((s, i) => {
      const pts = s.pontos
        .map((p, k) => `${x(rodadas[k]).toFixed(1)},${y(p).toFixed(1)}`)
        .join(" ");
      const cls = s.clube === meu ? ' class="eu"' : "";
      return `<polyline${cls} points="${pts}" fill="none" stroke="${corClube(i)}" stroke-width="1.4" data-clube="${s.clube}"/>`;
    })
    .join("");

  const legenda = ev.series
    .map((s, i) => {
      const total = s.pontos[s.pontos.length - 1];
      const marca = s.clube === meu ? " 🎮" : "";
      return `<button data-clube="${s.clube}"><span class="bolinha" style="background:${corClube(i)}"></span>${s.clube}${marca} <strong>${total}</strong></button>`;
    })
    .join("");

  return `
    <div class="grafico">
      <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Pontos acumulados por rodada">
        ${grade}${linhas}
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
      grafico.querySelectorAll("polyline").forEach((pl) =>
        pl.classList.toggle("sel", ativar && pl.dataset.clube === alvo)
      );
      grafico.classList.toggle("tem-selecao", !!ativar);
      if (ativar) b.classList.add("sel");
    })
  );
}
