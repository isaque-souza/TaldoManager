// Identidade visual dos clubes (v1.1): escudo e camisa em SVG, desenhados
// a partir das cores e formatos de cada clube (GET /clubes → identidade).
// Sem imagens: tudo é string de SVG, então cabe em qualquer innerHTML.

const porNome = new Map();   // nome do clube → identidade
let carregando = null;

// busca uma vez só (a seed não muda); chame antes de desenhar
export function carregarIdentidades() {
  carregando ??= fetch("/clubes")
    .then((r) => (r.ok ? r.json() : []))
    .then((clubes) => clubes.forEach((c) => porNome.set(c.nome, c.identidade)))
    .catch(() => {});   // sem identidade o jogo segue, com o visual neutro
  return carregando;
}

const NEUTRA = {
  cor_primaria: "#5b6472", cor_secundaria: "#d7dbe0",
  camisa: "lisa", escudo: "classico", sigla: "?",
};

export function identidade(nome) {
  return porNome.get(nome) || { ...NEUTRA, sigla: (nome || "?").slice(0, 3).toUpperCase() };
}

// texto escuro ou claro, o que se lê melhor sobre `hex`
export function corDoTexto(hex) {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const lum = 0.2126 * r + 0.7152 * g + 0.0722 * b;
  return lum > 0.6 ? "#111111" : "#ffffff";
}

// contorno que destaca o texto sobre faixas e listras
function contorno(hex) {
  return corDoTexto(hex) === "#ffffff" ? "rgba(0,0,0,.6)" : "rgba(255,255,255,.75)";
}

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => `&#${c.charCodeAt(0)};`);

// ids únicos para os clipPath (vários SVGs na mesma página)
let seq = 0;

// ---------- escudo ----------

const FORMAS = {
  classico: "M4 3H36V21C36 33 28 40 20 45C12 40 4 33 4 21Z",
  moderno: "M3 3H37V27L20 45L3 27Z",
  redondo: "M20 4A20 20 0 1 1 19.99 4Z",
};
const FORMAS_INTERNAS = {
  classico: "M8 7H32V21C32 30.5 26 36 20 40C14 36 8 30.5 8 21Z",
  moderno: "M7 7H33V25.5L20 39.5L7 25.5Z",
  redondo: "M20 8.5A15.5 15.5 0 1 1 19.99 8.5Z",
};

export function escudo(nome, tamanho = 24) {
  const id = identidade(nome);
  const forma = FORMAS[id.escudo] ? id.escudo : "classico";
  const texto = corDoTexto(id.cor_primaria);
  const y = forma === "redondo" ? 27.8 : 24.5;
  const brilho = `esc${++seq}`;
  return `<svg class="escudo" viewBox="0 0 40 48" width="${tamanho}" height="${tamanho * 1.2}" role="img" aria-label="Escudo do ${esc(nome)}">
    <defs><linearGradient id="${brilho}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#fff" stop-opacity=".35"/>
      <stop offset=".5" stop-color="#fff" stop-opacity="0"/>
      <stop offset="1" stop-color="#000" stop-opacity=".2"/>
    </linearGradient></defs>
    <path d="${FORMAS[forma]}" fill="${id.cor_secundaria}" stroke="rgba(0,0,0,.45)" stroke-width="1.2"/>
    <path d="${FORMAS_INTERNAS[forma]}" fill="${id.cor_primaria}"/>
    <text x="20" y="${y}" text-anchor="middle" font-size="8.5" font-weight="800"
      font-family="system-ui, sans-serif" fill="${texto}" letter-spacing=".3">${esc(id.sigla)}</text>
    <path d="${FORMAS[forma]}" fill="url(#${brilho})"/>
  </svg>`;
}

// nome do clube com o escudo pequeno na frente (tabelas, confrontos)
export function comEscudo(nome, html = esc(nome), tamanho = 18) {
  return `<span class="com-escudo">${escudo(nome, tamanho)}${html}</span>`;
}

// ---------- camisa ----------

const CAMISA = "M16 4L9 6.5L2 13L7.5 21L12 18.5V44H36V18.5L40.5 21L46 13L39 6.5L32 4C30 8.5 18 8.5 16 4Z";

function padrao(tipo, sec) {
  switch (tipo) {
    case "listras":
      return [13, 21, 29].map((x) => `<rect x="${x}" y="0" width="4.5" height="48" fill="${sec}"/>`).join("")
        + `<rect x="37" y="0" width="4.5" height="48" fill="${sec}"/>`
        + `<rect x="5" y="0" width="4.5" height="48" fill="${sec}"/>`;
    case "aros":
      return [14, 24, 34].map((y) => `<rect x="0" y="${y}" width="48" height="5" fill="${sec}"/>`).join("");
    case "faixa":
      return `<polygon points="10,4 18,4 40,44 32,44" fill="${sec}"/>`;
    case "metade":
      return `<rect x="24" y="0" width="24" height="48" fill="${sec}"/>`;
    default:
      return "";
  }
}

// numero: opcional, vai no peito (no pré-jogo, cada jogador tem o seu)
export function camisa(nome, { numero = null, tamanho = 32 } = {}) {
  const id = identidade(nome);
  const clip = `cam${++seq}`;
  const volume = `vol${seq}`;
  const num = numero == null ? "" : `
    <text x="24" y="33" text-anchor="middle" font-size="15" font-weight="800"
      font-family="system-ui, sans-serif" fill="${corDoTexto(id.cor_primaria)}"
      stroke="${contorno(id.cor_primaria)}" stroke-width="2.4" paint-order="stroke">${esc(numero)}</text>`;
  return `<svg class="camisa" viewBox="0 0 48 48" width="${tamanho}" height="${tamanho}" role="img" aria-label="Camisa do ${esc(nome)}">
    <defs>
      <clipPath id="${clip}"><path d="${CAMISA}"/></clipPath>
      <linearGradient id="${volume}" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0" stop-color="#000" stop-opacity=".28"/>
        <stop offset=".35" stop-color="#fff" stop-opacity=".12"/>
        <stop offset=".65" stop-color="#fff" stop-opacity="0"/>
        <stop offset="1" stop-color="#000" stop-opacity=".28"/>
      </linearGradient>
    </defs>
    <g clip-path="url(#${clip})">
      <rect width="48" height="48" fill="${id.cor_primaria}"/>
      ${padrao(id.camisa, id.cor_secundaria)}
      <rect width="48" height="48" fill="url(#${volume})"/>
    </g>
    <path d="M16 4C18 8.5 30 8.5 32 4" fill="none" stroke="${id.cor_secundaria}" stroke-width="2.2"/>
    <path d="${CAMISA}" fill="none" stroke="rgba(0,0,0,.5)" stroke-width="1.2" stroke-linejoin="round"/>
    ${num}
  </svg>`;
}
