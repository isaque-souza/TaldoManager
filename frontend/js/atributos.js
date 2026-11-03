// Atributos do jogador (v1.3), como os seis do FIFA/EA FC: Velocidade,
// Finalização, Passe, Drible, Marcação e Físico; goleiro tem Reflexos e
// Posicionamento. Vêm prontos do servidor (overall + perfil da posição +
// estilo do jogador).

export const NOME = {
  velocidade: "Velocidade", finalizacao: "Finalização", passe: "Passe",
  drible: "Drible", marcacao: "Marcação", fisico: "Físico",
  reflexos: "Reflexos", posicionamento: "Posicionamento",
};

export const SIGLA = {
  velocidade: "VEL", finalizacao: "FIN", passe: "PAS", drible: "DRI",
  marcacao: "MAR", fisico: "FIS", reflexos: "REF", posicionamento: "POS",
};

// faixa de cor como no FIFA: verde forte, verde, âmbar, vermelho
const faixa = (v) => (v >= 85 ? "otimo" : v >= 75 ? "bom" : v >= 65 ? "medio" : "fraco");

// "VEL 91 · DRI 88": os dois melhores, para listas (mercado)
export function destaques(atributos, quantos = 2) {
  return Object.entries(atributos || {})
    .sort((a, b) => b[1] - a[1])
    .slice(0, quantos)
    .map(([a, v]) => `${SIGLA[a]} ${v}`)
    .join(" · ");
}

// "VEL 91 · FIN 80 · ..." completo, para dicas (title)
export function linhaAtributos(atributos) {
  return Object.entries(atributos || {}).map(([a, v]) => `${SIGLA[a]} ${v}`).join(" · ");
}

// barras da ficha do jogador
export function barrasAtributos(atributos) {
  const linhas = Object.entries(atributos || {}).map(([a, v]) => `
    <li class="atr ${faixa(v)}">
      <span class="atr-nome"><b>${SIGLA[a]}</b> ${NOME[a]}</span>
      <span class="atr-barra" aria-hidden="true"><i style="width:${v}%"></i></span>
      <b class="atr-valor">${v}</b>
    </li>`).join("");
  return linhas ? `<ul class="atributos" aria-label="Atributos">${linhas}</ul>` : "";
}

// v2.4: o radar dos seis atributos (hexágono), como nas fichas do FIFA. A
// escala começa em 40 — abaixo disso ninguém joga a liga — para o desenho
// mostrar a diferença entre um 70 e um 90.
const PISO = 40;
const R = 78;

export function radarAtributos(atributos, cor = "#22b46a") {
  const lista = Object.entries(atributos || {});
  if (lista.length < 3) return "";
  const n = lista.length;
  const ang = (i) => -Math.PI / 2 + (i * 2 * Math.PI) / n;
  const ponto = (i, v) => {
    const r = (R * (Math.max(PISO, v) - PISO)) / (100 - PISO);
    return [Math.cos(ang(i)) * r, Math.sin(ang(i)) * r];
  };
  const anel = (v) => lista.map((_, i) => ponto(i, v).map((c) => c.toFixed(1)).join(",")).join(" ");
  const aneis = [55, 70, 85, 100].map((v) => `<polygon points="${anel(v)}" class="rd-anel"/>`).join("");
  const eixos = lista.map((_, i) => {
    const [x, y] = ponto(i, 100);
    return `<line x1="0" y1="0" x2="${x.toFixed(1)}" y2="${y.toFixed(1)}" class="rd-eixo"/>`;
  }).join("");
  const forma = lista.map(([, v], i) => ponto(i, v).map((c) => c.toFixed(1)).join(",")).join(" ");
  const rotulos = lista.map(([a, v], i) => {
    const x = Math.cos(ang(i)) * (R + 20);
    const y = Math.sin(ang(i)) * (R + 20);
    return `<text x="${x.toFixed(1)}" y="${(y - 3).toFixed(1)}" class="rd-sigla">${SIGLA[a]}</text>
      <text x="${x.toFixed(1)}" y="${(y + 11).toFixed(1)}" class="rd-valor rd-${faixa(v)}">${v}</text>`;
  }).join("");
  const texto = lista.map(([a, v]) => `${NOME[a]} ${v}`).join(", ");
  return `<svg class="radar" viewBox="-120 -112 240 226" role="img" aria-label="Atributos: ${texto}">
    ${aneis}${eixos}
    <polygon points="${forma}" class="rd-forma" style="--rd-cor:${cor}"/>
    ${rotulos}
  </svg>`;
}
