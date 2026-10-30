// Atmosfera (v2.4): o estádio à noite em SVG, desenhado a partir do jogo.
// A torcida tem as cores do mandante e enche a arquibancada na proporção do
// público; a dos visitantes fica num canto, com as cores deles. Clássico
// acende sinalizadores; estádio lotado levanta bandeiras. Nada de imagem:
// é uma string de SVG, como o escudo e a camisa (identidade.js).
//
// O sorteio dos lugares usa uma semente do próprio jogo: o mesmo jogo
// desenha sempre o mesmo estádio.

import { identidade } from "./identidade.js";

const L = 1200;   // largura do desenho
const A = 360;    // altura

// gerador pequeno e determinístico (mulberry32) a partir de um texto
function sorteio(texto) {
  let h = 1779033703;
  for (let i = 0; i < texto.length; i++) {
    h = Math.imul(h ^ texto.charCodeAt(i), 3432918353);
    h = (h << 13) | (h >>> 19);
  }
  return () => {
    h = (h + 0x6d2b79f5) | 0;
    let t = Math.imul(h ^ (h >>> 15), 1 | h);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// a cor sob o refletor: um pouco mais clara e menos saturada que a camisa
function sobLuz(hex, quanto = 0.18) {
  const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
  const m = c.map((v) => Math.round(v + (225 - v) * quanto));
  return `rgb(${m.join(",")})`;
}

// as quatro torres de luz: x da torre e x de onde o facho cai no gramado
const TORRES = [[70, 330], [345, 520], [855, 680], [1130, 870]];

// ids únicos por desenho: um gradiente de um SVG escondido (display: none)
// não pinta o SVG que está à mostra
let seq = 0;

function torres(u) {
  return TORRES.map(([x, alvo]) => {
    const lampadas = [];
    for (let l = 0; l < 3; l++) {
      for (let c = 0; c < 6; c++) {
        lampadas.push(`<circle cx="${x - 25 + c * 10}" cy="${22 + l * 8}" r="3"/>`);
      }
    }
    return `
      <polygon class="atm-feixe" points="${x - 30},44 ${x + 30},44 ${alvo + 170},${A} ${alvo - 170},${A}" fill="url(#atm-facho${u})"/>
      <ellipse cx="${x}" cy="30" rx="150" ry="95" fill="url(#atm-halo${u})"/>
      <rect x="${x - 3}" y="44" width="6" height="90" fill="#0b1119"/>
      <rect x="${x - 32}" y="15" width="64" height="30" rx="2" fill="#141c26" stroke="#2a3644"/>
      <g fill="#fff8e1">${lampadas.join("")}</g>`;
  }).join("");
}

// uma fileira de torcedores: domos (ombros + cabeça) agrupados por cor,
// para o SVG ter poucos nós mesmo com mil lugares
function fileiras(tinta, { y0, linhas, passo, alto, largura, ocupacao, cores, rng, de = 0, ate = L, vazio }) {
  for (let r = 0; r < linhas; r++) {
    const y = y0 + r * alto;
    const desloca = (r % 2) * (passo / 2);
    for (let x = de + desloca; x < ate - largura; x += passo) {
      if (rng() > ocupacao) {
        tinta(vazio, `M${x.toFixed(1)} ${y + alto - 3}h${largura}v2h-${largura}z`);
        continue;
      }
      const cor = cores[Math.floor(rng() * cores.length)];
      const meia = largura / 2;
      const sobe = (rng() * 1.6).toFixed(1);   // um pula, outro senta
      tinta(cor,
        `M${x.toFixed(1)} ${y + alto - 1}v-${(alto * 0.45 + +sobe).toFixed(1)}` +
        `a${meia} ${meia} 0 0 1 ${largura} 0v${(alto * 0.45 + +sobe).toFixed(1)}z`);
    }
  }
}

function sinalizadores(rng, quantos, u) {
  let s = "";
  for (let i = 0; i < quantos; i++) {
    const x = 120 + rng() * 620;
    const y = 240 + rng() * 40;
    s += `<ellipse cx="${x.toFixed(0)}" cy="${(y - 40).toFixed(0)}" rx="70" ry="38" fill="#9aa4ad" opacity=".09"/>
      <circle cx="${x.toFixed(0)}" cy="${y.toFixed(0)}" r="26" fill="url(#atm-fogo${u})"/>
      <circle cx="${x.toFixed(0)}" cy="${y.toFixed(0)}" r="2.6" fill="#fff3d6"/>`;
  }
  return s;
}

function bandeiras(rng, cores) {
  let s = "";
  for (let x = 60; x < L - 260; x += 70 + rng() * 60) {
    const cor = cores[Math.floor(rng() * cores.length)];
    const alto = 18 + rng() * 10;
    s += `<line x1="${x.toFixed(0)}" y1="128" x2="${x.toFixed(0)}" y2="${(128 - alto - 8).toFixed(0)}" stroke="#56616e" stroke-width="1.2"/>
      <path d="M${x.toFixed(0)} ${(128 - alto - 8).toFixed(0)}q14 -5 26 2v12q-12 -7 -26 -2z" fill="${cor}" opacity=".9"/>`;
  }
  return s;
}

// a placa de LED na beira do gramado, com a sigla do mandante
function placa(id, u) {
  const textos = [];
  for (let x = 30; x < L; x += 150) {
    textos.push(`<text x="${x}" y="297.5">${id.sigla}</text>`);
  }
  return `<rect x="0" y="288" width="${L}" height="13" fill="${id.cor_primaria}"/>
    <rect x="0" y="288" width="${L}" height="13" fill="url(#atm-led${u})"/>
    <g fill="${id.cor_secundaria}" font-family="Barlow Condensed, Arial Narrow, sans-serif"
      font-size="10" font-weight="800" letter-spacing="3" opacity=".9">${textos.join("")}</g>`;
}

function gramado() {
  const faixas = [];
  for (let i = 0; i < 12; i++) {
    const x0 = i * 100;
    // perspectiva: as faixas abrem para a frente
    const b0 = (x0 - L / 2) * 1.5 + L / 2;
    const b1 = (x0 + 100 - L / 2) * 1.5 + L / 2;
    faixas.push(`<polygon points="${x0},301 ${x0 + 100},301 ${b1},${A} ${b0},${A}" fill="${i % 2 ? "#1a7041" : "#17643a"}"/>`);
  }
  return `${faixas.join("")}
    <line x1="0" y1="306" x2="${L}" y2="306" stroke="rgba(255,255,255,.55)" stroke-width="1.5"/>`;
}

// jogo: { mandante, visitante, ocupacao (0–1), classico, lotado, semente }
export function estadioNoturno({ mandante, visitante, ocupacao = 0.6, classico = false, lotado = false, semente = "" }) {
  const casa = identidade(mandante);
  const fora = identidade(visitante);
  const rng = sorteio(`${mandante}|${visitante}|${semente}`);
  const u = `-${++seq}`;
  const cheio = lotado ? 1 : Math.max(0.08, Math.min(1, ocupacao));

  const tintas = new Map();
  const tinta = (cor, d) => {
    if (!tintas.has(cor)) tintas.set(cor, []);
    tintas.get(cor).push(d);
  };
  const daCasa = [sobLuz(casa.cor_primaria), sobLuz(casa.cor_primaria), sobLuz(casa.cor_secundaria), "#b9c2cc"];
  const deFora = [sobLuz(fora.cor_primaria), sobLuz(fora.cor_secundaria)];
  const vazio = "#1b2637";

  // anel de cima: a casa toda
  fileiras(tinta, { y0: 132, linhas: 7, passo: 8, alto: 11, largura: 5, ocupacao: cheio, cores: daCasa, rng, vazio });
  // anel de baixo: a casa e, no canto direito, separada por um vão, a visita
  fileiras(tinta, { y0: 222, linhas: 5, passo: 10, alto: 13, largura: 7, ocupacao: cheio, cores: daCasa, rng, ate: 960, vazio });
  fileiras(tinta, { y0: 222, linhas: 5, passo: 10, alto: 13, largura: 7, ocupacao: Math.min(1, cheio + 0.2), cores: deFora, rng, de: 1000, vazio });

  const torcida = [...tintas].map(([cor, ds]) => `<path fill="${cor}" d="${ds.join("")}"/>`).join("");

  return `<svg class="atmosfera" viewBox="0 0 ${L} ${A}" preserveAspectRatio="xMidYMax slice" aria-hidden="true" focusable="false">
    <defs>
      <linearGradient id="atm-ceu${u}" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#03060a"/><stop offset=".75" stop-color="#0c1724"/>
      </linearGradient>
      <radialGradient id="atm-halo${u}">
        <stop offset="0" stop-color="#fff4cf" stop-opacity=".55"/>
        <stop offset=".35" stop-color="#f4c430" stop-opacity=".12"/>
        <stop offset="1" stop-color="#f4c430" stop-opacity="0"/>
      </radialGradient>
      <linearGradient id="atm-facho${u}" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#fff6d8" stop-opacity=".22"/>
        <stop offset="1" stop-color="#fff6d8" stop-opacity="0"/>
      </linearGradient>
      <radialGradient id="atm-fogo${u}">
        <stop offset="0" stop-color="#ffb347" stop-opacity=".95"/>
        <stop offset=".4" stop-color="#ff5a1f" stop-opacity=".45"/>
        <stop offset="1" stop-color="#ff5a1f" stop-opacity="0"/>
      </radialGradient>
      <linearGradient id="atm-led${u}" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#fff" stop-opacity=".25"/><stop offset="1" stop-color="#000" stop-opacity=".35"/>
      </linearGradient>
      <linearGradient id="atm-sombra${u}" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#05080d" stop-opacity=".55"/><stop offset="1" stop-color="#05080d" stop-opacity="0"/>
      </linearGradient>
    </defs>
    <rect width="${L}" height="${A}" fill="url(#atm-ceu${u})"/>
    ${torres(u)}
    ${lotado ? bandeiras(rng, [casa.cor_primaria, casa.cor_secundaria]) : ""}
    <rect x="0" y="122" width="${L}" height="8" fill="#0a0f16"/>
    <g fill="#fff3c4" opacity=".7">${Array.from({ length: 30 }, (_, i) => `<rect x="${20 + i * 40}" y="129" width="12" height="1.5"/>`).join("")}</g>
    <rect x="0" y="130" width="${L}" height="82" fill="#0d1521"/>
    <rect x="0" y="212" width="${L}" height="8" fill="#090e15"/>
    <rect x="0" y="220" width="${L}" height="68" fill="#0f1826"/>
    ${torcida}
    <rect x="0" y="130" width="${L}" height="40" fill="url(#atm-sombra${u})"/>
    ${classico ? sinalizadores(rng, 4, u) : ""}
    ${placa(casa, u)}
    ${gramado()}
  </svg>`;
}
