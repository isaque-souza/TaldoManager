// Categorias de base (v2.0): os jovens do clube, fora do elenco até serem
// promovidos. O técnico faz uma peneira a cada 90 dias (quantos e quão bons
// vêm depende do nível da base); os jovens crescem um pouco a cada rodada,
// mais rápido com a base de nível alto.
// Promover e dispensar não têm volta: dois cliques, como nas obras.
// Olheiros da base (v2.0, passo 5): o técnico manda um olheiro para uma
// região por 1, 3 ou 6 meses; a cada 30 dias ele manda jovens indicados,
// que o técnico traz para a base ou deixa sumir no relatório seguinte.

import { $, api, estado, limparAviso, ocupado, pedir } from "./nucleo.js";
import { blocoResumo, potTexto, potTitulo, reais } from "./tabelas.js";
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
      <td><strong>${j.nome}</strong>${j.pais ? ` <small class="bs-pais">${j.pais}</small>` : ""}</td>
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
    ${olheiros(d)}
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
  $("r-base").querySelectorAll(".bs-trazer:not([disabled])").forEach((b) =>
    b.addEventListener("click", () => trazer(+b.dataset.id))
  );
  $("r-base").querySelectorAll(".bs-descartar").forEach((b) =>
    b.addEventListener("click", () => descartar(+b.dataset.id))
  );
  $("r-base").querySelectorAll(".bs-enviar:not([disabled])").forEach((b) =>
    b.addEventListener("click", () =>
      doisCliques(b, `Pagar ${b.dataset.custo}?`, () => enviar(b.dataset.regiao, +b.dataset.meses)))
  );
}

// ---------- olheiros da base ----------

const plural = (n, um, varios) => `${n} ${n === 1 ? um : varios}`;

function olheiros(d) {
  const o = d.olheiros;
  const missoes = o.missoes.length
    ? `<ul class="bs-missoes">${o.missoes.map((m) => `<li>
        <strong>${m.regiao}</strong> · mês ${m.relatorios_feitos + 1} de ${m.meses}
        <small>próximo relatório em ${m.proximo_fmt}
          (${m.dias_ate_o_relatorio ? `em ${plural(m.dias_ate_o_relatorio, "dia", "dias")}` : "hoje"})</small>
      </li>`).join("")}</ul>`
    : "";
  const indicados = o.indicados.length
    ? `<figure><table class="bs-tabela"><thead><tr>
        <th>Indicado</th><th>Pos.</th><th class="num">Idade</th><th class="num">OVR</th>
        <th class="num">POT</th><th>Olheiro</th><th></th></tr></thead>
        <tbody>${o.indicados.map((i) => linhaIndicado(i, o.bloqueio_trazer)).join("")}</tbody></table></figure>`
    : `<p class="vazio">Nenhum indicado agora. ${o.missoes.length
      ? "Eles chegam com o próximo relatório." : "Mande um olheiro para uma região."}</p>`;
  return `<h3 class="es-titulo">${icone("alvo")} Olheiros da base</h3>
    <p class="mk-intro">Mande um olheiro para uma região por 1, 3 ou 6 meses (paga na hora).
      A cada 30 dias ele manda um relatório com os jovens que achou: traga para a base quem quiser
      (precisa de vaga); quem você não trouxer some com o relatório seguinte. O potencial é a
      estimativa do seu olheiro profissional. Com a base de nível ${d.nivel}, até
      <strong>${plural(o.limite, "olheiro", "olheiros")}</strong> em missão ao mesmo tempo
      (${o.missoes.length} agora).</p>
    ${missoes}
    ${o.bloqueio_trazer && o.indicados.length
      ? `<p class="mk-bloqueio">${icone("cadeado")} ${o.bloqueio_trazer}: promova ou dispense alguém para trazer.</p>` : ""}
    ${indicados}
    <div class="mk-campanhas">${o.regioes.map(cardRegiao).join("")}</div>`;
}

function linhaIndicado(i, bloqueio) {
  return `<tr>
      <td><strong>${i.nome}</strong> <small class="bs-pais">${i.pais}</small></td>
      <td title="${i.funcao}">${sigla(i.funcao)}</td>
      <td class="num">${i.idade}</td>
      <td class="num">${i.overall}</td>
      <td class="num bs-pot" title="${potTitulo(i)}">${potTexto(i)}</td>
      <td><small>${i.regiao} · some em ${plural(i.dias_restantes, "dia", "dias")}</small></td>
      <td class="bs-acoes">
        <button type="button" class="bs-trazer" data-id="${i.id}" ${bloqueio ? `disabled title="${bloqueio}"` : ""}>
          ${icone("assinou")} Trazer</button>
        <button type="button" class="bs-descartar secondary outline" data-id="${i.id}">Descartar</button>
      </td>
    </tr>`;
}

function cardRegiao(r) {
  const [min, max] = r.por_relatorio;
  // o mesmo motivo nas três durações (limite, região ocupada): mostra uma vez
  const motivos = [...new Set(r.duracoes.map((x) => x.bloqueio).filter(Boolean))];
  const todas = r.duracoes.every((x) => x.bloqueio);
  return `<article class="mk-campanha">
      <header><strong>${r.nome}</strong></header>
      <p>${r.perfil}.</p>
      <dl class="mk-ficha">
        <div><dt>Por relatório</dt><dd>${min === max ? min : `${min}–${max}`} <small>jovens</small></dd></div>
        <div><dt>Idade</dt><dd>${r.idades[0]}–${r.idades[1]}</dd></div>
        <div><dt>Mês</dt><dd>${reais(r.custo_mes)}</dd></div>
      </dl>
      ${todas && motivos.length ? `<small class="mk-bloqueio">${icone("cadeado")} ${motivos[0]}</small>` : ""}
      <div class="bs-duracoes" role="group" aria-label="Mandar o olheiro: ${r.nome}">
        ${r.duracoes.map((x) => `<button type="button" class="secondary outline bs-enviar"
          data-regiao="${r.id}" data-meses="${x.meses}" data-custo="${reais(x.custo)}"
          ${x.bloqueio ? `disabled title="${x.bloqueio}"` : ""}>
          ${plural(x.meses, "mês", "meses")}<small>${reais(x.custo)}</small></button>`).join("")}
      </div>
    </article>`;
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

async function enviar(regiao, meses) {
  const nome = bs.dados.olheiros.regioes.find((r) => r.id === regiao)?.nome;
  const { dados, erro } = await mandar("POST", "/olheiros", { regiao, meses }, `Mandando o olheiro: ${nome}…`);
  if (erro) {
    avisar(`${icone("nao")} Não deu: ${erro}.`, true);
    return carregarBase();
  }
  bs.dados = dados;
  avisar(`${icone("ok")} Olheiro a caminho: ${nome}, por ${plural(meses, "mês", "meses")}. O primeiro relatório chega em 30 dias.`);
  renderBase();
  await carregarProximaRodada();   // o caixa mudou
}

async function trazer(id) {
  const { dados, erro } = await mandar("POST", `/indicados/${id}`, null, "Trazendo para a base…");
  if (erro) {
    avisar(`${icone("nao")} Não deu: ${erro}.`, true);
    return carregarBase();
  }
  bs.dados = dados.base;
  avisar(`${icone("ok")} ${dados.jovem} chegou à base.`);
  renderBase();
}

async function descartar(id) {
  const nome = bs.dados.olheiros.indicados.find((i) => i.id === id)?.nome;
  const { dados, erro } = await mandar("DELETE", `/indicados/${id}`, null, `Descartando ${nome}…`);
  if (erro) {
    avisar(`${icone("nao")} Não deu: ${erro}.`, true);
    return carregarBase();
  }
  bs.dados = dados;
  avisar(`${nome} saiu dos indicados.`);
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
