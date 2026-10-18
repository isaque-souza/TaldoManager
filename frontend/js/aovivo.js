// Jogo ao vivo — simulação interativa (v1.2): a partida do técnico vista de
// cima, minuto a minuto, no estilo da Simulação de Partida Interativa do
// FIFA. O servidor devolve a partida inteira como ela sai com as decisões
// até aqui (POST /transmissao); aqui ela é REPRODUZIDA com um relógio. Ao
// pausar, o técnico muda a tática ou faz substituições: o servidor refaz a
// partida do minuto seguinte em diante e o relógio continua. A rodada só é
// gravada no apito final (POST /rodadas), que aplica essas decisões.

import { $, esconderTudo, estado, limparAviso, ocupado, pedir } from "./nucleo.js";
import { decisaoParaEnviar, enviarRodada, mostrarRodadaTela } from "./rodada.js";
import { corDoTexto, escudo, identidade } from "./identidade.js";
import { icone } from "./icones.js";

const MS_POR_MINUTO = 500;          // 1×: ~45 s por jogo (escolha do usuário)
const CHAVE_VELOCIDADE = "taldo:velocidade";
const TATICAS = [["ofensivo", "Ofensivo"], ["equilibrado", "Equilibrado"], ["defensivo", "Defensivo"]];
// formações, da mais ofensiva à mais fechada (a postura pesa no motor, v1.2)
const FORMACOES = ["3-4-3", "4-2-4", "3-5-2", "4-3-3", "4-4-2", "4-5-1", "5-3-2", "5-4-1"];
const SIGLA_POS = { Goleiro: "GOL", Defesa: "DEF", "Meio-Campo": "MEI", Atacante: "ATA" };

let jogo = null;   // estado da transmissão em curso

// ---------- narração ----------

function narrar(e) {
  const q = e.jogador || "";
  switch (e.tipo) {
    case "gol": return { classe: "gol", texto: `<b>GOL!</b> ${q} marca para o ${e.clube}` };
    case "penalti": return { classe: "gol", texto: `<b>GOL DE PÊNALTI!</b> ${q} bate e converte para o ${e.clube}` };
    case "penalti_perdido": return { classe: "perdido", texto: `Pênalti para fora! ${q} desperdiça a cobrança` };
    case "penalti_defendido": return { classe: "defesa", texto: `Defendeu! ${q}, goleiro do ${e.clube}, pega o pênalti` };
    case "chute_fora": return { classe: "chute", texto: `Uh! ${q} arrisca e manda para fora` };
    case "cartao_amarelo": return { classe: "amarelo", texto: `Cartão amarelo para ${q} (${e.clube})` };
    case "expulsao": return { classe: "vermelho", texto: `<b>Expulso!</b> ${q} (${e.clube}) recebe o vermelho` };
    case "substituicao": {
      const sai = (e.detalhe || "").replace(/^sai /, "");
      return { classe: "troca", texto: `Substituição no ${e.clube}: entra ${q}${sai ? `, sai ${sai}` : ""}` };
    }
    case "lesao": return { classe: "lesao", texto: `${q} (${e.clube}) sente e pede atendimento` };
    default: return { classe: "", texto: `${q} ${e.clube ? `(${e.clube})` : ""}` };
  }
}

const relogio = (m) => (m > 90 ? `90+${m - 90}'` : `${m}'`);

function adicionarLinha(minuto, html, classe = "") {
  $("av-narracao").insertAdjacentHTML(
    "afterbegin",
    `<li class="${classe}"><span class="av-min">${minuto}</span><span>${html}</span></li>`
  );
}

// ---------- velocidade (lembrada no navegador) ----------

function lerVelocidade() {
  try {
    const v = Number(localStorage.getItem(CHAVE_VELOCIDADE));
    return [1, 2, 4].includes(v) ? v : 1;
  } catch {
    return 1;
  }
}

function escolherVelocidade(v) {
  if (jogo) jogo.velocidade = v;
  document.querySelectorAll("[data-vel]").forEach((b) => {
    const ativa = Number(b.dataset.vel) === v;
    b.classList.toggle("ativa", ativa);
    b.setAttribute("aria-pressed", ativa);
  });
  try { localStorage.setItem(CHAVE_VELOCIDADE, String(v)); } catch { /* sem storage, segue */ }
}

// minuto assistido, para retomar de onde parou ao voltar para a partida
const chaveMinuto = () => `taldo:transmissao:${estado.simId}:${jogo.rodada}`;
function lembrarMinuto() {
  try { localStorage.setItem(chaveMinuto(), String(jogo.minuto)); } catch { /* segue */ }
}
function minutoLembrado() {
  try { return Number(localStorage.getItem(chaveMinuto())) || 0; } catch { return 0; }
}
function esquecerMinuto() {
  try { localStorage.removeItem(chaveMinuto()); } catch { /* segue */ }
}

// ---------- entrada: "Ir para o jogo" (ou voltar para a partida) ----------

export async function jogarAoVivo() {
  limparAviso();
  const info = estado.rodadaInfo;
  if (!info.adversario) {   // folga: não há partida para transmitir
    if (await enviarRodada()) mostrarRodadaTela();
    return;
  }
  const corpo = info.transmissao_ativa ? {} : await decisaoParaEnviar();
  ocupado(true, info.transmissao_ativa ? "Voltando para a partida…" : "Rola a bola…");
  const t = await pedir(`/simulacoes/${estado.simId}/transmissao`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(corpo),
  });
  ocupado(false);
  if (!t) return;
  info.transmissao_ativa = true;
  iniciar(t);
}

function iniciar(t) {
  pararRelogio();
  jogo = {
    rodada: t.rodada,
    meu: t.clube_usuario,
    mandante: t.mandante,
    visitante: t.visitante,
    fim: 90 + t.acrescimos,
    minutos: t.minutos,
    eventos: t.eventos,
    decisoes: t.decisoes,
    outros: t.outros,
    minuto: 0,
    placar: [0, 0],
    velocidade: lerVelocidade(),
    timer: null,
    pausado: false,
    acabou: false,
    selecao: { sai: null, entra: null },
    momento: null,
  };
  jogo.cores = coresDosTimes();

  esconderTudo();
  $("aovivo").hidden = false;
  window.scrollTo(0, 0);
  $("av-narracao").innerHTML = "";
  $("av-faixa").classList.remove("visivel");
  $("av-placar").classList.remove("pulso");
  $("av-fim").hidden = true;
  $("av-painel").hidden = true;
  $("av-pular").disabled = false;
  $("av-pausar").disabled = false;
  escolherVelocidade(jogo.velocidade);
  montarCampo();
  adicionarLinha("0'", `Rola a bola: ${t.mandante.clube} x ${t.visitante.clube}`, "apito");

  // voltando para uma partida em andamento: narra de uma vez até onde parou
  const ate = Math.min(minutoLembrado(), jogo.fim - 1);
  while (jogo.minuto < ate) {
    jogo.minuto += 1;
    avancarMinuto(jogo.minuto, { silencioso: true });
  }
  renderTudo();
  if (ate > 0) {
    adicionarLinha(relogio(ate), "A transmissão continua de onde parou", "apito");
    pausar();
  } else {
    agendar();
  }
}

// ---------- relógio ----------

function pararRelogio() {
  if (jogo && jogo.timer) clearTimeout(jogo.timer);
}

function agendar() {
  pararRelogio();
  jogo.timer = setTimeout(tique, MS_POR_MINUTO / jogo.velocidade);
}

function tique() {
  // saiu da tela (Menu, Voltar)? para a transmissão (ela fica no servidor)
  if (!jogo || $("aovivo").hidden) { pararRelogio(); return; }
  if (jogo.pausado) return;

  jogo.minuto += 1;
  avancarMinuto(jogo.minuto);
  lembrarMinuto();
  if (jogo.minuto >= jogo.fim) { encerrar(); return; }
  if (jogo.minuto === 45) {   // intervalo: o vestiário é a hora de mexer
    adicionarLinha("45'", "Fim do primeiro tempo", "apito");
    pausar();
    return;
  }
  agendar();
}

function avancarMinuto(m, { silencioso = false } = {}) {
  if (m === 46) adicionarLinha("46'", "Começa o segundo tempo", "apito");
  for (const d of jogo.decisoes.filter((x) => x.minuto === m && x.tatica)) {
    const rotulo = TATICAS.find(([k]) => k === d.tatica)[1];
    adicionarLinha(relogio(m), `Mudança tática no ${d.clube}: time agora <b>${rotulo.toLowerCase()}</b>`, "troca");
  }
  for (const d of jogo.decisoes.filter((x) => x.minuto === m && x.formacao)) {
    adicionarLinha(relogio(m), `O ${d.clube} muda o desenho: agora no <b>${d.formacao}</b>`, "troca");
    redesenharTime(d.clube, d.formacao);
  }
  for (const e of jogo.eventos.filter((x) => x.minuto === m)) {
    const { classe, texto } = narrar(e);
    adicionarLinha(relogio(m), texto, classe);
    if (classe === "gol" && !silencioso) comemorar(e);
    if (e.tipo === "substituicao") trocarNoCampo(e);
    if (e.tipo === "expulsao") marcarExpulso(e.jogador);
  }
  if (m === 90 && jogo.fim > 90) {
    adicionarLinha("90'", `O quarto árbitro levanta a placa: <b>+${jogo.fim - 90}</b>`, "placa");
  }
  const reg = jogo.minutos[m - 1];
  if (reg) jogo.placar = reg.placar;
  if (!silencioso) renderTudo();
}

function renderTudo() {
  renderPlacar(jogo.acabou ? "fim" : jogo.pausado ? (jogo.minuto === 45 ? "intervalo" : "pausa") : "ao-vivo");
  moverBola();
  renderMomentum();
  renderEstatisticas();
  renderOutros();
}

// ---------- pausa: tática e substituições ----------

async function pausar() {
  if (!jogo || jogo.acabou) return;
  pararRelogio();
  jogo.pausado = true;
  jogo.selecao = { sai: null, entra: null };
  $("av-pausar").innerHTML = `${icone("play")} Retomar`;
  renderTudo();
  await carregarMomento();
}

function retomar() {
  if (!jogo || jogo.acabou) return;
  jogo.pausado = false;
  $("av-painel").hidden = true;
  $("av-pausar").innerHTML = `${icone("pausa")} Pausar`;
  renderTudo();
  agendar();
}

async function carregarMomento() {
  const m = await pedir(`/simulacoes/${estado.simId}/transmissao/estado?minuto=${jogo.minuto}`);
  if (!m || !jogo.pausado) return;
  jogo.momento = m;
  renderPainel();
}

// decisões já marcadas para o minuto seguinte ainda não aparecem na foto
// do minuto atual: entram aqui
function meuTimeAgora() {
  const time = jogo.momento.clubes.find((c) => c.clube === jogo.meu);
  const prox = jogo.decisoes.filter((d) => d.minuto === jogo.minuto + 1);
  const saem = new Set(prox.filter((d) => d.sai).map((d) => d.sai));
  const entram = new Set(prox.filter((d) => d.entra).map((d) => d.entra));
  const tatica = [...prox].reverse().find((d) => d.tatica)?.tatica || time.tatica;
  const formacao = [...prox].reverse().find((d) => d.formacao)?.formacao || time.formacao;
  return {
    tatica,
    formacao,
    restantes: time.substituicoes_restantes - saem.size,
    em_campo: time.em_campo.map((j) => ({ ...j, saindo: saem.has(j.nome) })),
    banco: time.banco.map((j) => ({ ...j, entrando: entram.has(j.nome) })),
  };
}

function renderPainel() {
  const t = meuTimeAgora();
  const sel = jogo.selecao;
  const posSai = sel.sai && t.em_campo.find((j) => j.nome === sel.sai)?.posicao;
  const prox = relogio(jogo.minuto + 1);

  const energia = (v) =>
    `<span class="av-energia ${v < 45 ? "baixa" : v < 70 ? "media" : ""}" title="Energia ${v}"><i style="width:${v}%"></i></span>`;
  // a coluna dos cartões existe mesmo vazia: a grade da linha não desalinha
  const cartoes = (j) => `<span class="av-cartoes">${
    j.expulso ? `<span class="cartao vermelho" role="img" aria-label="expulso"></span>`
      : j.amarelos ? `<span class="cartao" role="img" aria-label="amarelo"></span>` : ""}</span>`;

  const linhaCampo = (j) => {
    const bloqueado = j.expulso || j.saindo || t.restantes <= 0;
    return `<li><button class="av-jog ${sel.sai === j.nome ? "escolhido" : ""} ${j.saindo ? "saindo" : ""}"
        data-sai="${j.nome}" ${bloqueado ? "disabled" : ""}>
      <b class="av-num">${j.numero ?? "–"}</b>
      <span class="av-nome">${j.nome}${j.saindo ? " <small>sai no " + prox + "</small>" : ""}</span>
      <small class="av-pos">${SIGLA_POS[j.posicao] || j.posicao}</small>
      ${cartoes(j)}
      ${energia(j.energia)}
      <span class="av-nota ${j.nota >= 7 ? "boa" : j.nota < 6 ? "ruim" : ""}">${j.nota.toFixed(1)}</span>
    </button></li>`;
  };
  const linhaBanco = (j) => {
    const bloqueado = !j.disponivel || j.entrando || t.restantes <= 0;
    const combina = posSai && j.posicao === posSai;
    return `<li><button class="av-jog ${sel.entra === j.nome ? "escolhido" : ""} ${combina ? "combina" : ""} ${j.entrando ? "entrando" : ""}"
        data-entra="${j.nome}" ${bloqueado ? "disabled" : ""}>
      <b class="av-num">${j.numero ?? "–"}</b>
      <span class="av-nome">${j.nome}${j.entrando ? " <small>entra no " + prox + "</small>" : !j.disponivel ? " <small>já saiu</small>" : ""}</span>
      <small class="av-pos">${SIGLA_POS[j.posicao] || j.posicao}</small>
      <span class="av-ovr">${j.overall}</span>
      ${energia(j.energia)}
    </button></li>`;
  };

  $("av-painel").innerHTML = `
    <div class="av-painel-topo">
      ${icone("prancheta")} <strong>${jogo.minuto === 45 ? "Intervalo" : `Pausado · ${relogio(jogo.minuto)}`}</strong>
      <span>As mudanças valem a partir do ${prox}</span>
      <button id="av-retomar">${icone("play")} Retomar</button>
    </div>
    <div class="av-tatica">
      <span class="av-tatica-rotulo">Tática</span>
      <div role="group" aria-label="Tática">
        ${TATICAS.map(([k, rot]) =>
          `<button data-tatica="${k}" class="secondary outline ${k === t.tatica ? "ativa" : ""}" aria-pressed="${k === t.tatica}">${rot}</button>`
        ).join("")}
      </div>
      <label class="av-formacao">
        <span class="av-tatica-rotulo">Formação</span>
        <select id="av-formacao">
          ${FORMACOES.map((f) => `<option${f === t.formacao ? " selected" : ""}>${f}</option>`).join("")}
        </select>
      </label>
    </div>
    <div class="av-trocas">
      <div>
        <h4>Em campo <small>toque em quem sai</small></h4>
        <ul>${t.em_campo.map(linhaCampo).join("")}</ul>
      </div>
      <div>
        <h4>Banco <small>${t.restantes > 0 ? `${t.restantes} ${t.restantes === 1 ? "troca restante" : "trocas restantes"}` : "sem trocas"}</small></h4>
        <ul>${t.banco.length ? t.banco.map(linhaBanco).join("") : `<li class="vazio">Sem reservas.</li>`}</ul>
      </div>
    </div>
    <p class="av-painel-acoes">
      <button id="av-trocar" ${sel.sai && sel.entra ? "" : "disabled"}>${icone("troca")}
        ${sel.sai && sel.entra ? `Sai ${sel.sai}, entra ${sel.entra}` : "Escolha quem sai e quem entra"}</button>
      <span id="av-painel-msg" class="av-painel-msg" role="status"></span>
    </p>`;
  $("av-painel").hidden = false;

  $("av-retomar").addEventListener("click", retomar);
  $("av-painel").querySelectorAll("[data-tatica]").forEach((b) =>
    b.addEventListener("click", () => {
      if (b.dataset.tatica !== t.tatica) decidir({ tatica: b.dataset.tatica });
    })
  );
  $("av-formacao").addEventListener("change", (e) => {
    if (e.target.value !== t.formacao) decidir({ formacao: e.target.value });
  });
  $("av-painel").querySelectorAll("[data-sai]").forEach((b) =>
    b.addEventListener("click", () => {
      jogo.selecao.sai = jogo.selecao.sai === b.dataset.sai ? null : b.dataset.sai;
      renderPainel();
    })
  );
  $("av-painel").querySelectorAll("[data-entra]").forEach((b) =>
    b.addEventListener("click", () => {
      jogo.selecao.entra = jogo.selecao.entra === b.dataset.entra ? null : b.dataset.entra;
      renderPainel();
    })
  );
  $("av-trocar").addEventListener("click", () =>
    decidir({ sai: jogo.selecao.sai, entra: jogo.selecao.entra })
  );
}

// manda a decisão; o servidor devolve a partida refeita do minuto seguinte
// em diante (o que já passou não muda)
async function decidir(mudanca) {
  const msg = $("av-painel-msg");
  msg.textContent = "Passando a instrução…";
  msg.classList.remove("erro");
  $("av-painel").querySelectorAll("button").forEach((b) => (b.disabled = true));
  let t = null;
  let erro = null;
  try {
    const resp = await fetch(`/simulacoes/${estado.simId}/transmissao/decisoes`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ minuto: jogo.minuto + 1, ...mudanca }),
    });
    const corpo = await resp.json();
    if (resp.ok) t = corpo;
    else erro = typeof corpo.detail === "string" ? corpo.detail : `HTTP ${resp.status}`;
  } catch (e) {
    erro = `Sem resposta do servidor (${e.message})`;
  }
  if (!jogo) return;
  if (!t) {
    renderPainel();
    $("av-painel-msg").textContent = erro;
    $("av-painel-msg").classList.add("erro");
    return;
  }
  jogo.minutos = t.minutos;
  jogo.eventos = t.eventos;
  jogo.decisoes = t.decisoes;
  jogo.selecao = { sai: null, entra: null };
  renderPainel();
  $("av-painel-msg").textContent = mudanca.tatica
    ? "Instrução passada: o time muda a postura no próximo lance."
    : mudanca.formacao
      ? `O time passa ao ${mudanca.formacao}. Para mudar quem joga, faça substituições.`
      : `${mudanca.entra} se aquece na beira do campo.`;
}

// ---------- fim ----------

async function encerrar() {
  pararRelogio();
  jogo.acabou = true;
  jogo.pausado = false;
  jogo.minuto = jogo.fim;
  $("av-painel").hidden = true;
  $("av-pular").disabled = true;
  $("av-pausar").disabled = true;
  $("av-faixa").classList.remove("visivel");
  adicionarLinha(relogio(jogo.fim), "Fim de jogo!", "apito");
  renderTudo();
  await gravar();
}

// o apito final grava a rodada inteira (com as decisões do técnico)
async function gravar() {
  $("av-fim").hidden = false;
  $("av-resultados").disabled = true;
  $("av-fim-msg").textContent = "Gravando a rodada…";
  const res = await enviarRodada();
  $("av-resultados").disabled = false;
  if (!res) {
    $("av-fim-msg").textContent = "Não deu para gravar a rodada.";
    $("av-resultados").innerHTML = `${icone("play")} Tentar de novo`;
    $("av-resultados").dataset.acao = "gravar";
    return;
  }
  esquecerMinuto();
  estado.rodadaInfo.transmissao_ativa = false;
  const minha = res.resultados.find((r) => r.mandante === jogo.meu || r.visitante === jogo.meu);
  if (minha) jogo.placar = [minha.gols_mandante, minha.gols_visitante];   // o placar oficial
  renderPlacar("fim");
  $("av-fim-msg").textContent = "";
  $("av-resultados").innerHTML = `${icone("play")} Ver resultados da rodada`;
  $("av-resultados").dataset.acao = "resultados";
}

// pular: narra de uma vez tudo o que faltava e apita o fim
function pular() {
  if (!jogo || jogo.acabou) return;
  pararRelogio();
  jogo.pausado = false;
  $("av-painel").hidden = true;
  while (jogo.minuto < jogo.fim) {
    jogo.minuto += 1;
    avancarMinuto(jogo.minuto, { silencioso: true });
    if (jogo.minuto === 45) adicionarLinha("45'", "Fim do primeiro tempo", "apito");
  }
  encerrar();
}

// ---------- placar, gol e outros jogos ----------

const SELO = {
  "ao-vivo": `<span class="chip chip-longe chip-ao-vivo"><span class="luz"></span>Ao vivo</span>`,
  pausa: `<span class="chip chip-perto">Pausado</span>`,
  intervalo: `<span class="chip">Intervalo</span>`,
  fim: `<span class="chip chip-batida">Fim de jogo</span>`,
};

function renderPlacar(fase) {
  const m = jogo.mandante.clube;
  const v = jogo.visitante.clube;
  const tempo = fase === "intervalo" ? "INT" : relogio(jogo.minuto);
  $("av-placar").innerHTML = `
    <span class="pt-rodada">Rodada ${jogo.rodada}</span>
    <span class="pt-time">${escudo(m, 30)}<b>${identidade(m).sigla}</b></span>
    <span class="pt-gols"><b>${jogo.placar[0]}</b><i>x</i><b>${jogo.placar[1]}</b></span>
    <span class="pt-time pt-time-fora"><b>${identidade(v).sigla}</b>${escudo(v, 30)}</span>
    <span class="pt-relogio">${tempo}</span>
    ${SELO[fase]}`;
  $("av-barra").style.width = `${Math.min(100, (jogo.minuto / jogo.fim) * 100)}%`;
}

function comemorar(e) {
  const id = identidade(e.clube);
  const faixa = $("av-faixa");
  faixa.style.setProperty("--cor-gol", id.cor_primaria);
  faixa.style.setProperty("--cor-gol-texto", corDoTexto(id.cor_primaria));
  faixa.innerHTML = `${escudo(e.clube, 34)}<b>GOL!</b><span>${e.jogador} · ${e.clube}</span>`;
  // mais rápido o jogo, mais rápida a faixa (2,4 s em 1×, 1,2 s em 4×)
  faixa.style.animationDuration = `${2.4 / Math.sqrt(jogo.velocidade)}s`;
  faixa.classList.remove("visivel");
  void faixa.offsetWidth;   // reinicia a animação se sair outro gol logo
  faixa.classList.add("visivel");
  $("av-placar").classList.remove("pulso");
  void $("av-placar").offsetWidth;
  $("av-placar").classList.add("pulso");
}

function renderOutros() {
  const m = jogo.minuto;
  $("av-outros").innerHTML = jogo.outros.map((x) => {
    const ate = x.gols.filter((g) => g.minuto <= m);
    const gm = ate.filter((g) => g.clube === x.mandante).length;
    const gv = ate.length - gm;
    const novo = x.gols.some((g) => g.minuto === m);
    return `<li class="${novo ? "mexeu" : ""}">
      <span class="o-time">${escudo(x.mandante, 18)}${identidade(x.mandante).sigla}</span>
      <b>${gm} x ${gv}</b>
      <span class="o-time o-fora">${identidade(x.visitante).sigla}${escudo(x.visitante, 18)}</span>
    </li>`;
  }).join("");
}

function renderEstatisticas() {
  const reg = jogo.minutos[Math.min(jogo.minuto, jogo.minutos.length) - 1];
  const zero = [0, 0];
  const s = reg || { posse: [50, 50], finalizacoes: zero, no_gol: zero, escanteios: zero };
  const linha = (rotulo, [a, b], sufixo = "") => {
    const total = a + b || 1;
    return `<div class="st-linha">
      <span class="st-valor">${a}${sufixo}</span>
      <span class="st-rotulo">${rotulo}</span>
      <span class="st-valor st-fora">${b}${sufixo}</span>
      <span class="st-barra"><i style="width:${(a / total) * 100}%;background:${jogo.cores[0]}"></i></span>
    </div>`;
  };
  $("av-stats").innerHTML =
    linha("Posse de bola", s.posse, "%") +
    linha("Finalizações", s.finalizacoes) +
    linha("Chutes no gol", s.no_gol) +
    linha("Escanteios", s.escanteios);
}

// ---------- o campo visto de cima ----------

// cor de cada time; se as camisas forem parecidas, o visitante vai de cor
// secundária e, se ainda assim não der, de uniforme branco
function coresDosTimes() {
  const a = identidade(jogo.mandante.clube).cor_primaria;
  const b = identidade(jogo.visitante.clube);
  const rgb = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  const dist = (x, y) => Math.hypot(...rgb(x).map((c, i) => c - rgb(y)[i]));
  const fora = [b.cor_primaria, b.cor_secundaria, "#f4f4f4", "#14181f"].find((c) => dist(a, c) >= 160);
  return [a, fora];
}

// x (% da largura) de cada linha da formação, atacando para a direita
const X_LINHA = [5, 19, 33, 44];

function montarCampo() {
  const pecas = [jogo.mandante, jogo.visitante].map((time, lado) => {
    const porLinha = [0, 1, 2, 3].map((n) => time.titulares.filter((j) => j.linha === n));
    return porLinha.flatMap((js, n) => js.map((j, i) => {
      const x = lado === 0 ? X_LINHA[n] : 100 - X_LINHA[n];
      const y = ((i + 1) / (js.length + 1)) * 100;
      return `<div class="sim-jog sim-lado-${lado}" data-nome="${j.nome}" data-x="${x}" data-linha="${n}" data-y="${y}"
          style="left:${x}%;top:${y}%;--cor:${jogo.cores[lado]};--cor-texto:${corDoTexto(jogo.cores[lado])}"
          title="${j.nome} · ${j.posicao}"><span>${j.numero ?? ""}</span></div>`;
    }));
  }).flat().join("");

  $("av-campo").setAttribute("aria-label",
    `Partida vista de cima: ${jogo.mandante.clube} ataca para a direita, ${jogo.visitante.clube} para a esquerda`);
  $("av-campo").innerHTML = `
    <svg class="sim-marcas" viewBox="0 0 120 80" preserveAspectRatio="none" aria-hidden="true">
      <rect x="1" y="1" width="118" height="78"/><line x1="60" y1="1" x2="60" y2="79"/>
      <circle cx="60" cy="40" r="9"/><rect x="1" y="22" width="16" height="36"/>
      <rect x="103" y="22" width="16" height="36"/><rect x="1" y="32" width="5" height="16"/>
      <rect x="114" y="32" width="5" height="16"/>
    </svg>
    <span class="sim-nome sim-nome-0">${escudo(jogo.mandante.clube, 18)} ${identidade(jogo.mandante.clube).sigla} →</span>
    <span class="sim-nome sim-nome-1">← ${identidade(jogo.visitante.clube).sigla} ${escudo(jogo.visitante.clube, 18)}</span>
    ${pecas}
    <div id="sim-bola" class="sim-bola" style="left:50%;top:50%"></div>
    <div id="sim-lance" class="sim-lance" aria-hidden="true"></div>`;
  jogo.bola = { x: 50, y: 50 };
}

// onde a bola termina o minuto: no ataque de quem atacou, mais perto do gol
// quanto mais perigoso o lance; sem ataque, rola pelo meio puxada pela posse
const PROFUNDIDADE = { cortado: 72, fora: 91, defesa: 93, penalti_perdido: 89, gol: 98, penalti: 98 };
const ROTULO_LANCE = {
  fora: "Pra fora!", defesa: "Defesa!", gol: "GOL!", penalti: "GOL!", penalti_perdido: "Perdeu o pênalti!",
};

function moverBola() {
  // re-render do mesmo minuto (pausa, troca de velocidade): a bola fica
  if (jogo.bolaMinuto === jogo.minuto && !jogo.acabou) return;
  jogo.bolaMinuto = jogo.minuto;
  const reg = jogo.minutos[jogo.minuto - 1];
  let x = 50;
  let y = 50;
  const lance = reg && reg.lance;
  if (lance) {
    const fundo = PROFUNDIDADE[lance.fim] + (Math.random() * 6 - 3) * (lance.fim === "cortado" ? 1 : 0);
    x = lance.lado === "mandante" ? fundo : 100 - fundo;
    y = ["gol", "penalti"].includes(lance.fim) ? 50 : 28 + Math.random() * 44;
  } else if (reg) {
    const puxa = (reg.posse[0] - 50) * 0.4;
    x = 50 + puxa + (Math.random() * 24 - 12);
    y = 22 + Math.random() * 56;
  }
  if (jogo.minuto === 0 || jogo.minuto === 45 && jogo.pausado) { x = 50; y = 50; }
  jogo.bola = { x, y };

  const dur = jogo.acabou ? 0.4 : (MS_POR_MINUTO / jogo.velocidade) * 0.85 / 1000;
  const bola = $("sim-bola");
  if (!bola) return;
  bola.style.transitionDuration = `${dur}s`;
  bola.style.left = `${x}%`;
  bola.style.top = `${y}%`;

  // o bloco dos dois times acompanha a bola
  const desloca = (x - 50) * 0.32;
  $("av-campo").querySelectorAll(".sim-jog").forEach((p) => {
    const base = Number(p.dataset.x);
    const goleiro = base === X_LINHA[0] || base === 100 - X_LINHA[0];
    p.style.transitionDuration = `${dur}s`;
    p.style.left = `${Math.max(2, Math.min(98, base + (goleiro ? desloca * 0.15 : desloca)))}%`;
  });

  const rotulo = $("sim-lance");
  rotulo.classList.remove("visivel");
  if (lance && ROTULO_LANCE[lance.fim] && !jogo.acabou) {
    rotulo.textContent = ROTULO_LANCE[lance.fim];
    rotulo.style.left = `${x}%`;
    void rotulo.offsetWidth;
    rotulo.classList.add("visivel");
  }
}

function acharPeca(nome) {
  return [...$("av-campo").querySelectorAll(".sim-jog")].find((p) => p.dataset.nome === nome);
}

// formação mudada no meio do jogo: os bonecos do time vão para as linhas do
// novo desenho por setor (goleiro, defesa, meio, ataque); dentro do setor,
// quem estava mais atrás continua mais atrás. Quem joga só muda por
// substituição, então um setor com gente a mais empurra o excedente para a
// linha seguinte.
const SETORES = ["Goleiro", "Defesa", "Meio-Campo", "Atacante"];

function redesenharTime(clube, formacao) {
  const lado = [jogo.mandante, jogo.visitante].findIndex((t) => t.clube === clube);
  if (lado < 0) return;
  const time = [jogo.mandante, jogo.visitante][lado];
  const elenco = [...time.titulares, ...time.banco];
  const setor = (p) => {
    const j = elenco.find((x) => x.nome === p.dataset.nome);
    const i = SETORES.indexOf(j && j.posicao);
    return i < 0 ? Number(p.dataset.linha) : i;
  };
  const pecas = [...$("av-campo").querySelectorAll(`.sim-jog.sim-lado-${lado}`)].sort((a, b) =>
    setor(a) - setor(b) || a.dataset.linha - b.dataset.linha || a.dataset.y - b.dataset.y
  );
  const tamanhos = [1, ...formacao.split("-").map(Number)];
  let k = 0;
  tamanhos.forEach((quantos, n) => {
    // a última linha leva quem sobrar (time que ainda não fechou as contas)
    const linha = pecas.slice(k, n === tamanhos.length - 1 ? pecas.length : k + quantos);
    k += linha.length;
    linha.forEach((p, i) => {
      const x = lado === 0 ? X_LINHA[n] : 100 - X_LINHA[n];
      const y = ((i + 1) / (linha.length + 1)) * 100;
      Object.assign(p.dataset, { x, linha: n, y });
      p.style.left = `${x}%`;
      p.style.top = `${y}%`;
    });
  });
}

function trocarNoCampo(e) {
  const sai = (e.detalhe || "").replace(/^sai /, "");
  const peca = acharPeca(sai);
  if (!peca) return;
  // procura no time inteiro do apito (titulares e banco), não só no banco:
  // a camisa nunca fica sem número, seja quem for que entre
  const time = [jogo.mandante, jogo.visitante].find((t) => t.clube === e.clube);
  const entra = time && [...time.titulares, ...time.banco].find((j) => j.nome === e.jogador);
  peca.dataset.nome = e.jogador;
  peca.title = `${e.jogador}${entra ? ` · ${entra.posicao}` : ""}`;
  peca.querySelector("span").textContent = entra?.numero ?? "";
  peca.classList.remove("entrou");
  void peca.offsetWidth;
  peca.classList.add("entrou");
}

function marcarExpulso(nome) {
  const peca = acharPeca(nome);
  if (peca) peca.classList.add("expulso");
}

// momentum: uma barra por minuto, para cima quando o mandante ataca e para
// baixo quando é o visitante; mais alta quanto mais perigoso o lance
const PESO = { cortado: 5, fora: 9, defesa: 11, penalti_perdido: 11, gol: 16, penalti: 16 };

function renderMomentum() {
  const svg = $("av-momentum");
  svg.setAttribute("viewBox", `0 0 ${jogo.fim} 36`);
  const barras = jogo.minutos.slice(0, jogo.minuto).filter((r) => r.lance).map((r) => {
    const h = PESO[r.lance.fim];
    const casa = r.lance.lado === "mandante";
    return `<rect x="${r.minuto - 1}" y="${casa ? 18 - h : 18}" width=".8" height="${h}"
      fill="${jogo.cores[casa ? 0 : 1]}" opacity="${["gol", "penalti"].includes(r.lance.fim) ? 1 : .75}"/>`;
  }).join("");
  svg.innerHTML = `<line x1="0" y1="18" x2="${jogo.fim}" y2="18" class="mom-meio"/>
    <line x1="45" y1="0" x2="45" y2="36" class="mom-int"/>
    ${barras}
    <line x1="${jogo.minuto}" y1="0" x2="${jogo.minuto}" y2="36" class="mom-agora"/>`;
}

// ---------- ligações ----------

document.querySelectorAll("[data-vel]").forEach((b) =>
  b.addEventListener("click", () => {
    escolherVelocidade(Number(b.dataset.vel));
    if (jogo && !jogo.pausado && !jogo.acabou) agendar();
  })
);
$("av-pausar").addEventListener("click", () => (jogo && jogo.pausado ? retomar() : pausar()));
$("av-pular").addEventListener("click", pular);
$("av-resultados").addEventListener("click", () => {
  if ($("av-resultados").dataset.acao === "gravar") { gravar(); return; }
  pararRelogio();
  jogo = null;
  mostrarRodadaTela();   // faseRodada já é "depois": a tela de resultados
});
