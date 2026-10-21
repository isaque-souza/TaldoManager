// Categorias de base (v2.0): os jovens do clube, fora do elenco até serem
// promovidos. O técnico faz uma peneira a cada 90 dias (quantos e quão bons
// vêm depende do nível da base); os jovens crescem um pouco a cada rodada,
// mais rápido com a base de nível alto.
// Promover e dispensar não têm volta: dois cliques, como nas obras.

import { $, api, estado, limparAviso, ocupado, pedir } from "./nucleo.js";
import { blocoResumo, reais } from "./tabelas.js";
import { sigla } from "./posicoes.js";
import { icone } from "./icones.js";
import { carregarCaixa } from "./caixa.js";
import { carregarProximaRodada } from "./rodada.js";

const bs = { dados: null, aviso: "", ruim: false, avisoRodada: null };
const rodadaAtual = () => estado.rodadaInfo && estado.rodadaInfo.rodada;
const caminho = () => `/simulacoes/${estado.simId}/base`;
const ritmo = (r) => `${Math.round(r * 100)}%`;

export async function carregarBase() {
  if (!estado.simId) return;
  const dados = await pedir(caminho());
  if (!dados) return;
  bs.dados = dados;
  if (bs.avisoRodada !== rodadaAtual()) bs.aviso = "";
  renderBase();
}

function linhaJovem(j, bloqueio) {
  const pct = (j.progresso * 100).toFixed(0);
  const idade = j.ultimo_ano
    ? `${j.idade} <span class="chip chip-perto" title="Faz ${bs.dados.idade_limite} na virada">último ano</span>`
    : `${j.idade}`;
  return `<tr>
      <td><strong>${j.nome}</strong></td>
      <td title="${j.funcao}">${sigla(j.funcao)}</td>
      <td class="num">${idade}</td>
      <td class="num bs-ovr">${j.overall}
        <span class="es-progresso bs-progresso" role="progressbar" aria-valuemin="0" aria-valuemax="100"
          aria-valuenow="${pct}" aria-label="Até o próximo ponto de overall"><span style="width:${pct}%"></span></span></td>
      <td class="num">${j.potencial}</td>
      <td class="bs-acoes">
        <button type="button" class="bs-promover" data-id="${j.id}" ${bloqueio ? `disabled title="${bloqueio}"` : ""}>
          ${icone("assinou")} Promover</button>
        <button type="button" class="bs-dispensar secondary outline" data-id="${j.id}">Dispensar</button>
      </td>
    </tr>`;
}

function cardNivel(n, atual) {
  const eAtual = n.nivel === atual;
  const custo = n.custo_temporada ? `${reais(n.custo_temporada)}<small>/temporada</small>` : "grátis";
  const agora = !eAtual && n.custo_agora
    ? `<p>Agora: <strong>${reais(n.custo_agora)}</strong> até o fim da temporada.</p>` : "";
  const motivo = !eAtual && n.bloqueio ? `<small class="mk-bloqueio">${icone("cadeado")} ${n.bloqueio}</small>` : "";
  return `<article class="mk-campanha${eAtual ? " ol-atual" : ""}">
      <header><strong>Nível ${n.nivel}</strong>${eAtual ? ` <span class="chip chip-batida">Atual</span>` : ""}</header>
      <dl class="mk-ficha">
        <div><dt>Crescimento</dt><dd>${ritmo(n.ritmo)}</dd></div>
        <div><dt>Peneira</dt><dd>${n.por_peneira[0]}–${n.por_peneira[1]}</dd></div>
      </dl>
      <dl class="mk-ficha"><div><dt>Custo</dt><dd>${custo}</dd></div></dl>
      ${agora}${motivo}
      ${eAtual ? "" : `<button type="button" class="secondary outline bs-nivel" data-nivel="${n.nivel}" ${n.bloqueio ? "disabled" : ""}>
        ${n.nivel > atual ? "Investir" : "Reduzir"}</button>`}
    </article>`;
}

function renderBase() {
  const d = bs.dados;
  const nivel = d.niveis.find((n) => n.nivel === d.nivel);
  const p = d.peneira;
  const faixa = `${p.por_peneira[0]} a ${p.por_peneira[1]} jovens`;
  const peneira = `<div class="tile bs-peneira">
      <span class="tile-rotulo">Peneira</span>
      <button type="button" id="bs-peneira" ${p.bloqueio ? "disabled" : ""}>${icone("base")} Fazer peneira</button>
      <span class="tile-detalhe" title="${p.bloqueio || ""}">${p.liberada_fmt
        ? `liberada em ${p.liberada_fmt}`
        : p.bloqueio ? "base cheia" : `traz ${faixa}`}</span>
    </div>`;
  const cheia = d.jovens.length >= d.vagas;
  const lista = d.jovens.length
    ? `<figure><table class="bs-tabela"><thead><tr>
        <th>Jovem</th><th>Pos.</th><th class="num">Idade</th><th class="num">OVR</th>
        <th class="num">POT</th><th></th></tr></thead>
        <tbody>${d.jovens.map((j) => linhaJovem(j, d.bloqueio_promocao)).join("")}</tbody></table></figure>`
    : `<p class="vazio">Nenhum jovem na base. Faça uma peneira para trazer os próximos.</p>`;

  $("r-base").innerHTML = `
    <div class="tiles">
      ${blocoResumo("Nível", d.nivel, `ritmo de crescimento: ${ritmo(nivel.ritmo)}`)}
      ${blocoResumo("Jovens", `${d.jovens.length}/${d.vagas}`, cheia ? "base cheia: sem vaga para peneira" : "vagas na base", cheia ? "ruim" : "")}
      ${peneira}
    </div>
    <p class="mk-intro">A peneira traz ${faixa} (pelo nível da base), e a próxima só
      ${p.intervalo_dias} dias depois. Os jovens treinam a cada rodada e crescem até o potencial; a barrinha
      mostra quanto falta para o próximo ponto. Na base eles não jogam nem recebem salário.
      Quem faz ${d.idade_limite} anos sem ser promovido vai embora na virada. Promovido, ele
      vai para o elenco (${d.elenco.jogadores}/${d.elenco.maximo}) com contrato de 3 temporadas.</p>
    <p class="mk-msg${bs.ruim ? " ruim" : ""}" role="status">${bs.aviso}</p>
    ${d.bloqueio_promocao && d.jovens.length
      ? `<p class="mk-bloqueio">${icone("cadeado")} ${d.bloqueio_promocao}: venda ou dispense alguém para promover.</p>` : ""}
    ${lista}
    <h3 class="es-titulo">${icone("base")} Investimento na base</h3>
    <p class="mk-intro">Nível maior faz os jovens crescerem mais rápido e traz peneiras com
      mais jovens e mais talento. Como o olheiro: subir paga na hora a diferença pelas rodadas que faltam;
      descer não devolve nada. Na virada, renova pela temporada cheia.
      Gasto nesta temporada: <strong>${reais(d.gasto_temporada)}</strong>.</p>
    <div class="mk-campanhas">${d.niveis.map((n) => cardNivel(n, d.nivel)).join("")}</div>`;

  $("bs-peneira").addEventListener("click", fazerPeneira);
  $("r-base").querySelectorAll(".bs-promover:not([disabled])").forEach((b) =>
    b.addEventListener("click", () => doisCliques(b, "Confirmar?", () => promover(+b.dataset.id)))
  );
  $("r-base").querySelectorAll(".bs-dispensar").forEach((b) =>
    b.addEventListener("click", () => doisCliques(b, "Dispensar mesmo?", () => dispensar(+b.dataset.id)))
  );
  $("r-base").querySelectorAll(".bs-nivel:not([disabled])").forEach((b) =>
    b.addEventListener("click", () => trocarNivel(+b.dataset.nivel))
  );
}

// sem confirm(), que trava a página
function doisCliques(botao, texto, acao) {
  if (botao.dataset.confirmar !== "1") {
    botao.dataset.confirmar = "1";
    botao.textContent = texto;
    return;
  }
  acao();
}

function avisar(texto, ruim = false) {
  bs.aviso = texto;
  bs.ruim = ruim;
  bs.avisoRodada = rodadaAtual();
}

async function mandar(metodo, sufixo, corpo, texto) {
  limparAviso();
  ocupado(true, texto);
  try {
    const resp = await fetch(`${api()}${caminho()}${sufixo}`, {
      method: metodo,
      headers: { "Content-Type": "application/json" },
      body: corpo ? JSON.stringify(corpo) : undefined,
    });
    const dados = await resp.json().catch(() => ({}));
    if (!resp.ok) return { erro: dados.detail || `HTTP ${resp.status}` };
    return { dados };
  } catch (e) {
    return { erro: e.message };
  } finally {
    ocupado(false);
  }
}

async function fazerPeneira() {
  const { dados, erro } = await mandar("POST", "/peneira", null, "Fazendo a peneira…");
  if (erro) {
    avisar(`${icone("nao")} Não deu: ${erro}.`, true);
    return carregarBase();
  }
  bs.dados = dados.base;
  const fora = dados.de_fora ? ` ${dados.de_fora} ficou de fora por falta de vaga.` : "";
  avisar(dados.novos.length
    ? `${icone("ok")} A peneira trouxe ${dados.novos.length}: ${dados.novos.join(", ")}.${fora}`
    : `A peneira não trouxe ninguém.${fora}`);
  renderBase();
  carregarCaixa();
}

async function promover(id) {
  const nome = bs.dados.jovens.find((j) => j.id === id)?.nome;
  const { dados, erro } = await mandar("POST", `/${id}/promover`, null, `Promovendo ${nome}…`);
  if (erro) {
    avisar(`${icone("nao")} Não deu: ${erro}.`, true);
    return carregarBase();
  }
  bs.dados = dados.base;
  avisar(`${icone("ok")} ${dados.jogador} subiu ao profissional: já está no elenco.`);
  renderBase();
  await carregarProximaRodada();   // o elenco mudou
}

async function dispensar(id) {
  const nome = bs.dados.jovens.find((j) => j.id === id)?.nome;
  const { dados, erro } = await mandar("DELETE", `/${id}`, null, `Dispensando ${nome}…`);
  if (erro) {
    avisar(`${icone("nao")} Não deu: ${erro}.`, true);
    return carregarBase();
  }
  bs.dados = dados;
  avisar(`${nome} deixou a base.`);
  renderBase();
}

async function trocarNivel(nivel) {
  const { dados, erro } = await mandar("POST", "/nivel", { nivel }, "Mudando o investimento…");
  if (erro) {
    avisar(`${icone("nao")} Não deu: ${erro}.`, true);
    return carregarBase();
  }
  bs.dados = dados;
  avisar(`${icone("ok")} Base agora no nível ${dados.nivel}.`);
  renderBase();
  carregarCaixa();
  await carregarProximaRodada();   // o caixa mudou
}
