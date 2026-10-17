// Ícones (v1.1): traços do Lucide (lucide.dev, licença ISC), todos com o
// mesmo traço de 2px e cor herdada do texto. No HTML, um
// <span data-icone="play"></span> vira o SVG em preencherIcones().

const TRACOS = {
  play: "M5 5a2 2 0 0 1 3.008-1.728l11.997 6.998a2 2 0 0 1 .003 3.458l-12 7A2 2 0 0 1 5 19z",
  mais: "M5 12h14m-7-7v14",
  pasta: "m6 14l1.5-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.54 6a2 2 0 0 1-1.95 1.5H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H18a2 2 0 0 1 2 2v2",
  casa: "M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8M3 10a2 2 0 0 1 .709-1.528l7-6a2 2 0 0 1 2.582 0l7 6A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
  chave: "M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.106-3.105c.32-.322.863-.22.983.218a6 6 0 0 1-8.259 7.057l-7.91 7.91a1 1 0 0 1-2.999-3l7.91-7.91a6 6 0 0 1 7.057-8.259c.438.12.54.662.219.984z",
  alvo: "M12 22a10 10 0 1 0 0-20a10 10 0 0 0 0 20m0-4a6 6 0 1 0 0-12a6 6 0 0 0 0 12m0-4a2 2 0 1 0 0-4a2 2 0 0 0 0 4",
  camisa: "M20.38 3.46L16 2a4 4 0 0 1-8 0L3.62 3.46a2 2 0 0 0-1.34 2.23l.58 3.47a1 1 0 0 0 .99.84H6v10c0 1.1.9 2 2 2h8a2 2 0 0 0 2-2V10h2.15a1 1 0 0 0 .99-.84l.58-3.47a2 2 0 0 0-1.34-2.23",
  troca: "M8 3L4 7l4 4M4 7h16m-4 14l4-4l-4-4m4 4H4",
  contrato: "M6 22a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.704.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 2zM14 2v5a1 1 0 0 0 1 1h5M10 9H8m8 4H8m8 4H8",
  carteira: "M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4",
  cadeado: "M5 11h14a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2M7 11V7a5 5 0 0 1 10 0v4",
  lixo: "M3 6h18m-2 0v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2",
};

export function icone(nome, rotulo = "") {
  const d = TRACOS[nome];
  if (!d) return "";
  const a11y = rotulo ? `role="img" aria-label="${rotulo}"` : `aria-hidden="true"`;
  return `<svg class="icone" viewBox="0 0 24 24" width="1.1em" height="1.1em" ${a11y}>` +
    `<path d="${d}" fill="none" stroke="currentColor" stroke-width="2" ` +
    `stroke-linecap="round" stroke-linejoin="round"/></svg>`;
}

export function preencherIcones(raiz = document) {
  raiz.querySelectorAll("[data-icone]").forEach((el) => {
    el.innerHTML = icone(el.dataset.icone);
  });
}
