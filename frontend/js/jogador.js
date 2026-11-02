// Página do jogador: ficha, mercado e game log.

import { $, esconderTudo, estado, limparAviso, pedir, voltarUm } from "./nucleo.js";
import { decimal, ligarLinks, potTexto, potTitulo, reais, tabela } from "./tabelas.js";
import { minutoFmt } from "./partida.js";
import { cartao, icone, seloIdolo } from "./icones.js";
import { barrasAtributos, radarAtributos } from "./atributos.js";
import { camisa, comEscudo, escudo, identidade } from "./identidade.js";
import { sigla } from "./posicoes.js";

// ---------- visão jogador ----------

export const COLS_GAMELOG = [
  ["rodada", "R"], ["adversario", "Adversário"], ["mando", "Local"],
  ["placar", "Placar"], ["resultado", "Res."], ["atuacao", "Atuação"],
  ["gols", "G"], ["assistencias", "A"], ["nota", "Nota"],
];

export async function abrirJogador(jogadorId) {
  limparAviso();
  const d = await pedir(`/simulacoes/${estado.simId}/jogadores/${jogadorId}`);
  if (!d) return;

  estado.jogadorAtualId = Number(jogadorId);
  esconderTudo();
  $("jogador").hidden = false;
  window.scrollTo(0, 0);   // vindo de uma lista rolada, a página abre no topo

  const j = d.jogador;
  $("jogador-topo").innerHTML = fichaTopo(j);

  const bloco = (rotulo, valor) => `<div><dt>${rotulo}</dt><dd>${valor}</dd></div>`;
  const jogou = j.partidas > 0;
  const penas = j.penaltis + j.penaltis_perdidos;
  const temporada = [
    bloco("Jogos", j.partidas), bloco("Gols", j.gols), bloco("Assist.", j.assistencias),
    bloco("Nota média", jogou ? decimal(j.nota_media) : "—"),
    bloco("Melhor nota", jogou ? decimal(j.melhor_nota) : "—"),
    bloco("Melhor em campo", `${j.melhor_em_campo}x`),
    bloco("Cartões", `${cartao()} ${j.amarelos} ${cartao("vermelho")} ${j.vermelhos}`),
    bloco("Faltas", j.faltas),
    penas ? bloco("Pênaltis", `${j.penaltis}/${penas}`) : "",
  ].join("");
  // saves anteriores à v0.7 não têm dados de mercado (vêm zerados); a fama
  // (v1.4) vem null nos anteriores a ela
  const casa = j.temporadas_no_clube;
  const contrato = [
    j.valor_mercado ? bloco("Valor", reais(j.valor_mercado)) : "",
    j.valor_mercado ? bloco("Salário/temp.", reais(j.salario)) : "",
    j.valor_mercado ? bloco("Restam", `${j.contrato_anos} temp.`) : "",
    j.multa_rescisoria ? bloco("Multa", reais(j.multa_rescisoria)) : "",
    j.fama != null ? bloco("Fama", `${j.fama}/100`) : "",
    j.fama != null ? bloco("No clube", `${casa} temp.`) : "",
  ].join("");
  // de onde ele vem e para onde quer ir (v1.9); saves antigos vêm sem
  const pais = j.formador_pais ? ` (${j.formador_pais})` : "";
  const sonhoAqui = j.sonho === j.clube ? " · <em>está lá</em>" : "";
  const carreira = [
    j.formador ? `<li><span>Formado no</span> <strong>${j.formador}</strong>${pais}</li>` : "",
    j.clube_historia ? `<li><span>Fez história no</span> <strong>${j.clube_historia}</strong></li>` : "",
    j.sonho ? `<li><span>${j.sonho_encerrar ? "Quer encerrar a carreira no" : "Sonha jogar no"}</span> ` +
      `<strong>${j.sonho}</strong>${sonhoAqui}</li>` : "",
  ].join("");
  $("jogador-blocos").innerHTML = `
    <h3 class="secao">Temporada</h3>
    <dl class="jg-blocos">${temporada}</dl>
    ${contrato ? `<h3 class="secao">Contrato</h3><dl class="jg-blocos">${contrato}</dl>` : ""}
    ${carreira ? `<h3 class="secao">Carreira</h3><ul class="jg-carreira">${carreira}</ul>` : ""}`;

  $("jogador-atributos").innerHTML = j.atributos && Object.keys(j.atributos).length
    ? `<h3 class="secao">Atributos</h3>
       <div class="jg-atributos">${radarAtributos(j.atributos)}${barrasAtributos(j.atributos)}</div>`
    : "";
  $("jogador-notas").innerHTML = graficoNotas(d.jogos, j.nota_media);

  const linhas = d.jogos.map((g) => ({
    partida_id: g.partida_id,
    rodada: g.rodada,
    adversario: comEscudo(g.adversario),
    mando: g.mando === "casa" ? "Casa" : "Fora",
    placar: `${g.gols_pro} x ${g.gols_contra}`,
    resultado: `<span class="pj-res pj-res-${g.resultado}">${g.resultado}</span>`,
    atuacao: g.titular ? "Titular" : `entrou ${minutoFmt(g.entrou_min)}'`,
    gols: g.gols,
    assistencias: g.assistencias,
    nota: `<span class="jg-nota jg-nota-${faixaNota(g.nota)}">${decimal(g.nota)}</span>`,
  }));
  $("jogador-log").innerHTML = linhas.length
    ? tabela(linhas, COLS_GAMELOG)
    : `<p class="vazio">Não entrou em campo nesta temporada.</p>`;
  ligarLinks($("jogador-log"));
}

// ---------- a ficha (v2.4) ----------

// onde cada posição fica no campinho da ficha (x largura, y profundidade,
// 0–100, atacando para cima); lateral e ponta têm os dois lados
const LUGAR = {
  Goleiro: [[50, 6]], Zagueiro: [[50, 22]], Lateral: [[12, 30], [88, 30]],
  Volante: [[50, 40]], "Meia central": [[50, 54]], "Meia-atacante": [[50, 68]],
  Ponta: [[12, 74], [88, 74]], "Segundo atacante": [[50, 80]], Centroavante: [[50, 90]],
};

function campinhoPosicoes(principal, secundarias) {
  const marca = (pos, cls) => (LUGAR[pos] || []).map(([x, y]) => {
    const cx = (4 + x * 0.72).toFixed(1);
    const cy = (98 - y * 0.92).toFixed(1);
    return `<g class="${cls}"><circle cx="${cx}" cy="${cy}" r="${cls === "cp-principal" ? 7.5 : 6}"/>
      <text x="${cx}" y="${(+cy + 2.2).toFixed(1)}">${sigla(pos)}</text></g>`;
  }).join("");
  const nomes = [principal, ...secundarias].join(", ");
  return `<svg class="jg-campinho" viewBox="0 0 80 102" role="img" aria-label="Posições: ${nomes}">
    <rect x=".5" y=".5" width="79" height="101" rx="2" class="cp-gramado"/>
    <g class="cp-linhas"><line x1=".5" y1="51" x2="79.5" y2="51"/><circle cx="40" cy="51" r="8"/>
      <rect x="22" y=".5" width="36" height="14"/><rect x="22" y="87.5" width="36" height="14"/></g>
    ${secundarias.map((p) => marca(p, "cp-secundaria")).join("")}
    ${marca(principal, "cp-principal")}
  </svg>`;
}

function fichaTopo(j) {
  const id = j.clube ? identidade(j.clube) : null;
  const funcao = j.funcao || j.posicao;
  const sec = (j.secundarias || []).filter((p) => p !== funcao);
  const visual = j.clube
    ? camisa(j.clube, { tamanho: 104, numero: j.numero })
    : `<span class="tr-sem-clube">${icone("assinou")}</span>`;
  const estilo = id ? ` style="--jg-cor:${id.cor_primaria};--jg-cor2:${id.cor_secundaria}"` : "";
  const pot = j.potencial
    ? `<div><dt>POT</dt><dd class="${j.potencial > j.overall ? "sobe" : ""}" title="${potTitulo(j)}">${potTexto(j)}</dd></div>`
    : "";
  return `<div class="jg-ficha"${estilo}>
      <div class="jg-ficha-camisa">${visual}</div>
      <div class="jg-ficha-nome">
        <h2>${j.nome}${j.idolo ? ` ${seloIdolo()}` : ""}</h2>
        <p class="jg-ficha-clube">${j.clube ? `${escudo(j.clube, 22)} <strong>${j.clube}</strong>` : "Sem clube"}
          <span>· ${j.idade} anos${j.idolo ? " · ídolo da torcida" : ""}</span></p>
        <p class="jg-ficha-pos"><span class="chip jg-pos-principal">${sigla(funcao)} · ${funcao}</span>
          ${sec.map((p) => `<span class="chip jg-pos-sec" title="Também joga de ${p.toLowerCase()}">${sigla(p)}</span>`).join("")}</p>
      </div>
      <dl class="el-notas jg-notas"><div><dt>OVR</dt><dd>${j.overall}</dd></div>${pot}</dl>
      ${LUGAR[funcao] ? campinhoPosicoes(funcao, sec) : ""}
    </div>`;
}

// faixas da nota de um jogo (as cores dos atributos): 6,5 já é um bom jogo
const faixaNota = (n) => (n >= 7.5 ? "otimo" : n >= 6.5 ? "bom" : n >= 6 ? "medio" : "fraco");

// as notas jogo a jogo: uma barra por jogo (a escala vai de 4 a 10), a
// média tracejada, e uma bolinha por gol e um quadradinho por assistência
function graficoNotas(jogos, media) {
  if (!jogos.length) return "";
  const W = 900, H = 190, padL = 26, padR = 8, padT = 22, padB = 22;
  const piso = 4, teto = 10;
  const passo = (W - padL - padR) / Math.max(jogos.length, 12);
  const larg = Math.max(6, Math.min(26, passo * 0.62));
  const y = (n) => padT + (1 - (Math.min(teto, Math.max(piso, n)) - piso) / (teto - piso)) * (H - padT - padB);
  let grade = "";
  for (let n = 5; n <= 9; n += 2) {
    grade += `<line x1="${padL}" x2="${W - padR}" y1="${y(n)}" y2="${y(n)}" class="grade"/>
      <text x="${padL - 6}" y="${y(n) + 3}" class="eixo" text-anchor="end">${n}</text>`;
  }
  const barras = jogos.map((g, i) => {
    const cx = padL + passo * i + passo / 2;
    const topo = y(g.nota);
    const res = g.resultado === "V" ? "vitória" : g.resultado === "D" ? "derrota" : "empate";
    const dica = `Rodada ${g.rodada}, ${res} ${g.gols_pro}–${g.gols_contra} contra o ${g.adversario}: nota ${decimal(g.nota)}` +
      `${g.gols ? `, ${g.gols} ${g.gols === 1 ? "gol" : "gols"}` : ""}` +
      `${g.assistencias ? `, ${g.assistencias} ${g.assistencias === 1 ? "assistência" : "assistências"}` : ""}`;
    let marcas = "";
    let my = topo - 7;
    for (let k = 0; k < g.gols; k++, my -= 9) marcas += `<circle cx="${cx}" cy="${my}" r="3.4" class="gn-gol"/>`;
    for (let k = 0; k < g.assistencias; k++, my -= 9) marcas += `<rect x="${cx - 3}" y="${my - 3}" width="6" height="6" class="gn-assist"/>`;
    const rotulo = jogos.length <= 20 || i % 2 === 0
      ? `<text x="${cx}" y="${H - 6}" class="eixo" text-anchor="middle">${g.rodada}</text>` : "";
    return `<g class="gn-jogo"><title>${dica}</title>
      <rect x="${(cx - larg / 2).toFixed(1)}" y="${topo.toFixed(1)}" width="${larg.toFixed(1)}" height="${(H - padB - topo).toFixed(1)}" rx="2" class="gn-barra gn-${faixaNota(g.nota)}"/>
      ${marcas}${rotulo}</g>`;
  }).join("");
  const ym = y(media);
  const linhaMedia = media ? `<line x1="${padL}" x2="${W - padR}" y1="${ym}" y2="${ym}" class="gn-media"/>
    <text x="${W - padR}" y="${ym - 5}" class="gn-media-rotulo" text-anchor="end">média ${decimal(media)}</text>` : "";
  return `<h3 class="secao">Notas na temporada</h3>
    <figure class="jg-grafico-notas">
      <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Nota em cada jogo da temporada; média ${decimal(media)}">
        ${grade}${barras}${linhaMedia}
      </svg>
      <figcaption><span><i class="gn-gol-leg"></i> gol</span><span><i class="gn-assist-leg"></i> assistência</span><span>a rodada vai embaixo de cada barra</span></figcaption>
    </figure>`;
}

document
  .querySelectorAll("[data-voltar]")
  .forEach((b) => b.addEventListener("click", voltarUm));
