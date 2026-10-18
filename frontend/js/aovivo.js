// Jogo ao vivo (v1.1): a transmissão da partida do técnico, minuto a
// minuto. A rodada já foi simulada inteira no servidor ao clicar em "Ir
// para o jogo"; aqui os lances que o motor gravou são REPRODUZIDOS com um
// relógio — nada é sorteado na tela.

import { $, esconderTudo, estado, limparAviso, pedir } from "./nucleo.js";
import { enviarRodada, mostrarRodadaTela } from "./rodada.js";
import { corDoTexto, escudo, identidade } from "./identidade.js";

const MS_POR_MINUTO = 500;          // 1×: ~45 s por jogo (escolha do usuário)
const PAUSA_INTERVALO = 4;          // o intervalo dura "4 minutos" de relógio
const CHAVE_VELOCIDADE = "taldo:velocidade";

let jogo = null;   // estado do replay em curso

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

// ---------- entrada: "Ir para o jogo" ----------

export async function jogarAoVivo() {
  const res = await enviarRodada();
  if (!res) return;
  const meu = res.clube_usuario;
  const minha = res.resultados.find((r) => r.mandante === meu || r.visitante === meu);
  if (!minha) { mostrarRodadaTela(); return; }   // folga

  const [det, av] = await Promise.all([
    pedir(`/simulacoes/${estado.simId}/partidas/${minha.partida_id}`),
    pedir(`/simulacoes/${estado.simId}/rodadas/${res.rodada_jogada}/ao-vivo`),
  ]);
  if (!det || !av) { mostrarRodadaTela(); return; }
  iniciar(res, det, av);
}

function iniciar(res, det, av) {
  limparAviso();
  pararRelogio();
  const p = det.partida;
  const ultimo = Math.max(90, ...det.eventos.map((e) => e.minuto));
  const fim = p.acrescimos != null ? 90 + p.acrescimos : ultimo;

  jogo = {
    rodada: res.rodada_jogada,
    partida: p,
    eventos: det.eventos,
    outros: av.partidas.filter((x) => x.partida_id !== p.id),
    meu: res.clube_usuario,
    fim,
    minuto: 0,
    placar: [0, 0],
    velocidade: lerVelocidade(),
    timer: null,
    pausa: 0,
  };

  esconderTudo();
  $("aovivo").hidden = false;
  window.scrollTo(0, 0);
  $("av-narracao").innerHTML = "";
  // a faixa e o pulso do jogo anterior ficam com a classe; ao reexibir a
  // tela o navegador reinicia a animação e um "GOL!" fantasma aparece no 0'
  $("av-faixa").classList.remove("visivel");
  $("av-placar").classList.remove("pulso");
  $("av-fim").hidden = true;
  $("av-pular").disabled = false;
  escolherVelocidade(jogo.velocidade);
  adicionarLinha("0'", `Rola a bola: ${p.mandante.nome} x ${p.visitante.nome}`, "apito");
  renderPlacar("ao-vivo");
  renderOutros();
  agendar();
}

// ---------- relógio ----------

function pararRelogio() {
  if (jogo && jogo.timer) clearTimeout(jogo.timer);
}

function agendar() {
  jogo.timer = setTimeout(tique, MS_POR_MINUTO / jogo.velocidade);
}

function tique() {
  // saiu da tela (Menu, Voltar)? para a transmissão
  if (!jogo || $("aovivo").hidden) { pararRelogio(); return; }

  if (jogo.pausa > 0) {             // intervalo
    jogo.pausa -= 1;
    if (jogo.pausa === 0) {
      adicionarLinha("46'", "Começa o segundo tempo", "apito");
      renderPlacar("ao-vivo");
    }
    agendar();
    return;
  }

  jogo.minuto += 1;
  avancarMinuto(jogo.minuto);
  if (jogo.minuto >= jogo.fim) { encerrar(); return; }
  if (jogo.minuto === 45) {
    adicionarLinha("45'", "Fim do primeiro tempo", "apito");
    jogo.pausa = PAUSA_INTERVALO;
    renderPlacar("intervalo");
  }
  agendar();
}

function avancarMinuto(m) {
  const p = jogo.partida;
  for (const e of jogo.eventos.filter((x) => x.minuto === m)) {
    const { classe, texto } = narrar(e);
    adicionarLinha(relogio(m), texto, classe);
    if (classe === "gol") {
      jogo.placar[e.clube === p.mandante.nome ? 0 : 1] += 1;
      comemorar(e);
    }
  }
  if (m === 90 && jogo.fim > 90) {
    adicionarLinha("90'", `O quarto árbitro levanta a placa: <b>+${jogo.fim - 90}</b>`, "placa");
  }
  renderPlacar(jogo.pausa > 0 ? "intervalo" : "ao-vivo");
  renderOutros();
}

function encerrar() {
  pararRelogio();
  const p = jogo.partida;
  jogo.placar = [p.gols_mandante, p.gols_visitante];   // garante o placar oficial
  jogo.minuto = jogo.fim;
  adicionarLinha(relogio(jogo.fim), "Fim de jogo!", "apito");
  renderPlacar("fim");
  renderOutros();
  renderEstatisticas();
  $("av-fim").hidden = false;
  $("av-pular").disabled = true;
}

// pular: narra de uma vez tudo o que faltava e apita o fim
function pular() {
  if (!jogo) return;
  pararRelogio();
  jogo.pausa = 0;
  while (jogo.minuto < jogo.fim) {
    jogo.minuto += 1;
    avancarMinuto(jogo.minuto);
    if (jogo.minuto === 45) adicionarLinha("45'", "Fim do primeiro tempo", "apito");
  }
  $("av-faixa").classList.remove("visivel");
  encerrar();
}

// ---------- placar, gol e outros jogos ----------

const SELO = {
  "ao-vivo": `<span class="chip chip-longe chip-ao-vivo"><span class="luz"></span>Ao vivo</span>`,
  intervalo: `<span class="chip">Intervalo</span>`,
  fim: `<span class="chip chip-batida">Fim de jogo</span>`,
};

function renderPlacar(fase) {
  const p = jogo.partida;
  const tempo = fase === "intervalo" ? "INT" : relogio(jogo.minuto);
  $("av-placar").innerHTML = `
    <span class="pt-rodada">Rodada ${jogo.rodada}</span>
    <span class="pt-time">${escudo(p.mandante.nome, 30)}<b>${identidade(p.mandante.nome).sigla}</b></span>
    <span class="pt-gols"><b>${jogo.placar[0]}</b><i>x</i><b>${jogo.placar[1]}</b></span>
    <span class="pt-time pt-time-fora"><b>${identidade(p.visitante.nome).sigla}</b>${escudo(p.visitante.nome, 30)}</span>
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
  const p = jogo.partida;
  const linha = (rotulo, a, b, sufixo = "") => {
    const total = a + b || 1;
    return `<div class="st-linha">
      <span class="st-valor">${a}${sufixo}</span>
      <span class="st-rotulo">${rotulo}</span>
      <span class="st-valor st-fora">${b}${sufixo}</span>
      <span class="st-barra"><i style="width:${(a / total) * 100}%"></i></span>
    </div>`;
  };
  $("av-stats").innerHTML =
    linha("Posse de bola", p.posse_mandante, p.posse_visitante, "%") +
    linha("Finalizações", p.finalizacoes_mandante, p.finalizacoes_visitante) +
    linha("Chutes no gol", p.finalizacoes_gol_mandante, p.finalizacoes_gol_visitante) +
    linha("Escanteios", p.escanteios_mandante, p.escanteios_visitante);
}

// ---------- ligações ----------

document.querySelectorAll("[data-vel]").forEach((b) =>
  b.addEventListener("click", () => escolherVelocidade(Number(b.dataset.vel)))
);
$("av-pular").addEventListener("click", pular);
$("av-resultados").addEventListener("click", () => {
  pararRelogio();
  jogo = null;
  mostrarRodadaTela();   // faseRodada já é "depois": a tela de resultados
});
