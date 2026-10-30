// Pré-jogo (v1.1): as duas escalações no campo, antes do apito.
// "Jogar a rodada" abre esta tela; "Ir para o jogo" joga de fato. O XI vem
// de GET /pre-jogo, que roda a mesma escalação do motor: é quem vai entrar.
// v2.3: com o contexto do jogo — forma recente, desfalques, estádio e
// público previsto (tudo lido do save). v2.4: o cartaz do jogo, com o
// estádio desenhado (atmosfera.js), o jogador que mais decide no rival e o
// confronto direto na carreira.

import { $, esconderTudo, estado, limparAviso, ocupado, pedir } from "./nucleo.js";
import { abrirSecaoRodada, jogarRodada, salvarEscalacaoAgora } from "./rodada.js";
import { jogarAoVivo } from "./aovivo.js";
import { camisa, escudo } from "./identidade.js";
import { icone } from "./icones.js";
import { estadioNoturno } from "./atmosfera.js";

const TATICA = { ofensivo: "Ofensivo", equilibrado: "Equilibrado", defensivo: "Defensivo" };
const RESULTADO = { V: "Vitória", E: "Empate", D: "Derrota" };

const chip = (classe, texto) => `<span class="chip${classe ? ` chip-${classe}` : ""}">${texto}</span>`;
const milhar = (n) => n.toLocaleString("pt-BR");
const pct = (n) => `${Math.round(n * 100)}%`;
const decimal = (n) => n.toFixed(1).replace(".", ",");
const plural = (n, um, varios) => `${n} ${n === 1 ? um : varios}`;

export async function abrirPreJogo() {
  limparAviso();
  $("r-jogar").disabled = true;
  await salvarEscalacaoAgora();   // o pré-jogo lê a escalação gravada
  ocupado(true, "Preparando o pré-jogo…");
  const pj = await pedir(`/simulacoes/${estado.simId}/pre-jogo`);
  ocupado(false);
  $("r-jogar").disabled = false;
  if (!pj) return;
  if (!pj.adversario) {   // folga: não há jogo para mostrar
    await jogarRodada();
    return;
  }
  renderPreJogo(pj);
}

function renderPreJogo(pj) {
  const eu = pj.mandante.clube === pj.clube_usuario ? pj.mandante : pj.visitante;
  const rival = eu === pj.mandante ? pj.visitante : pj.mandante;
  const local = pj.mando === "casa" ? "em casa" : "fora";

  esconderTudo();
  $("prejogo").hidden = false;
  window.scrollTo(0, 0);

  $("pj-titulo").textContent = pj.copa
    ? `Copa · ${pj.copa.nome}`
    : `Rodada ${pj.rodada} de ${pj.total_rodadas}`;
  $("pj-confronto").innerHTML =
    `<strong>${eu.clube}</strong> <span class="x">x</span> <strong>${rival.clube}</strong> ` +
    `<small>${local === "em casa" ? "em casa" : "fora de casa"}</small>`;

  const ctxDe = (nome) => [pj.contexto_mandante, pj.contexto_visitante].find((c) => c && c.clube === nome);
  $("pj-cartaz").innerHTML = cartaz(pj, ctxDe);
  $("pj-perigo").innerHTML = perigo(ctxDe(rival.clube), rival.clube);
  $("pj-direto").innerHTML = confrontoDireto(pj.confronto_direto);

  $("pj-tarja-eu").innerHTML = tarjaTime(eu);
  $("pj-tarja-rival").innerHTML = tarjaTime(rival);
  $("pj-campo").setAttribute("aria-label",
    `Escalações: ${eu.clube} no ${eu.formacao} contra ${rival.clube} no ${rival.formacao}`);
  $("pj-campo").innerHTML =
    MARCAS + metade(eu, "eu") + metade(rival, "rival");

  $("pj-chega-eu-titulo").textContent = `Desfalques — ${eu.clube}`;
  $("pj-chega-rival-titulo").textContent = `Desfalques — ${rival.clube}`;
  $("pj-chega-eu").innerHTML = desfalques(ctxDe(eu.clube)?.desfalques || []);
  $("pj-chega-rival").innerHTML = desfalques(ctxDe(rival.clube)?.desfalques || []);

  $("pj-banco-eu-titulo").textContent = `Banco — ${eu.clube}`;
  $("pj-banco-rival-titulo").textContent = `Banco — ${rival.clube}`;
  $("pj-banco-eu").innerHTML = banco(eu);
  $("pj-banco-rival").innerHTML = banco(rival);
}

// ---------- o cartaz do jogo (v2.4) ----------

// a média de overall de quem vai entrar: a força real do jogo, com os
// desfalques e o cansaço já pesando na escolha do XI
function forcaDoXI(t) {
  return Math.round(t.titulares.reduce((s, j) => s + j.overall, 0) / t.titulares.length);
}

function cartaz(pj, ctxDe) {
  const e = pj.estadio;
  const fundo = estadioNoturno({
    mandante: pj.mandante.clube, visitante: pj.visitante.clube,
    ocupacao: e ? e.ocupacao : 0.5, classico: !!(e && e.classico), lotado: !!(e && e.lotado),
    semente: `pre${pj.rodada}`,
  });
  const fm = forcaDoXI(pj.mandante);
  const fv = forcaDoXI(pj.visitante);
  const selos = e ? [
    e.classico ? chip("longe", "Clássico") : "",
    e.lotado ? chip("batida", "Lotado") : "",
  ].join(" ").trim() : "";
  const comp = pj.copa ? `Copa · ${pj.copa.nome}` : `Rodada ${pj.rodada}`;
  return `<div class="cartaz-fundo">${fundo}</div>
    <div class="cartaz-palco">
      ${timeDoCartaz(pj.mandante, ctxDe(pj.mandante.clube), pj.clube_usuario, fm, fv)}
      <div class="cartaz-meio">
        <span class="cartaz-comp">${comp}</span>
        <b class="cartaz-x">x</b>
        ${selos ? `<span class="cartaz-selos">${selos}</span>` : ""}
      </div>
      ${timeDoCartaz(pj.visitante, ctxDe(pj.visitante.clube), pj.clube_usuario, fv, fm)}
    </div>
    ${e ? publico(e, pj.mando) : ""}`;
}

function timeDoCartaz(t, c, meu, forca, outra) {
  const tabela = c && c.posicao
    ? `<span class="cartaz-pos"><b>${c.posicao}º</b> · ${plural(c.pontos, "ponto", "pontos")}</span>`
    : `<span class="cartaz-pos">Estreia na temporada</span>`;
  const melhor = forca > outra ? " cartaz-forte" : "";
  return `<div class="cartaz-time${t.clube === meu ? " cartaz-eu" : ""}">
    ${escudo(t.clube, 76)}
    <strong class="cartaz-nome">${t.clube}</strong>
    ${tabela}
    ${c ? formaCurta(c.forma) : ""}
    <span class="cartaz-forca${melhor}" title="Média de overall dos 11 que vão entrar">Força do XI <b>${forca}</b></span>
  </div>`;
}

// os últimos jogos em quadradinhos, do mais antigo para o mais recente
function formaCurta(jogos) {
  if (!jogos.length) return "";
  return `<ol class="cartaz-forma" aria-label="Últimos jogos, do mais antigo para o mais recente">${jogos.map((j) => {
    const texto = `${RESULTADO[j.resultado]} ${j.gols_pro}–${j.gols_contra} contra o ${j.adversario}` +
      `${j.competicao === "copa" ? " (copa)" : ""}`;
    return `<li class="pj-res pj-res-${j.resultado}" title="${texto}" aria-label="${texto}">${j.resultado}</li>`;
  }).join("")}</ol>`;
}

function publico(e, mando) {
  const onde = mando === "casa" ? "Nosso estádio" : `Estádio do ${e.clube}`;
  return `<div class="cartaz-publico">
    <span class="cartaz-onde">${icone("torcida")} ${onde}</span>
    <span><b>${milhar(e.publico_previsto)}</b> torcedores previstos</span>
    <span class="pj-ocupacao" role="img" aria-label="${pct(e.ocupacao)} de ocupação">
      <i style="width:${Math.min(100, e.ocupacao * 100)}%"></i></span>
    <span>${pct(e.ocupacao)} de ${milhar(e.capacidade)} lugares · ingresso ${e.ingresso.toLowerCase()}</span>
  </div>`;
}

// ---------- análise do adversário (v2.4) ----------

function perigo(c, clube) {
  const titulo = `<h3 class="secao">Fique de olho</h3>`;
  const p = c && c.perigo;
  if (!p) return `${titulo}<p class="pg-detalhe">O ${clube} não tem ninguém disponível que se destaque.</p>`;
  let porque;
  if (p.motivo === "overall") {
    porque = `Ainda sem jogos na temporada: é o melhor do ataque, overall ${p.overall}.`;
  } else {
    const conta = [p.gols && plural(p.gols, "gol", "gols"),
      p.assistencias && plural(p.assistencias, "assistência", "assistências")].filter(Boolean).join(" e ");
    porque = `${conta ? `${conta} em ` : ""}${plural(p.partidas, "jogo", "jogos")} · nota média ${decimal(p.nota_media)}`;
  }
  return `${titulo}
    <div class="pj-perigo">
      ${camisa(clube, { numero: p.numero, tamanho: 56 })}
      <div>
        <strong>${p.nome}</strong>
        <small>${p.funcao || p.posicao} · overall ${p.overall}</small>
        <p class="pg-linha">${porque}</p>
      </div>
    </div>`;
}

function confrontoDireto(d) {
  const titulo = `<h3 class="secao">Confronto direto</h3>`;
  if (!d || !d.total) {
    return `${titulo}<p class="pg-detalhe">Primeiro encontro entre os dois na sua carreira.</p>`;
  }
  const parte = (n, classe) => (n ? `<i class="cd-${classe}" style="flex:${n}"></i>` : "");
  const lista = d.jogos.map((j) => {
    const onde = j.competicao === "copa" ? `Copa · ${j.fase}` : `Rodada ${j.rodada}`;
    const pen = j.penaltis ? ` <small>(pên. ${j.penaltis.pro}–${j.penaltis.contra})</small>` : "";
    return `<li><span class="pj-res pj-res-${j.resultado}" aria-label="${RESULTADO[j.resultado]}">${j.resultado}</span>
      <b>${j.gols_pro}–${j.gols_contra}</b>${pen}
      <small>Temporada ${j.temporada} · ${onde} · ${j.mando === "casa" ? "em casa" : "fora"}</small></li>`;
  }).join("");
  return `${titulo}
    <p class="pg-linha cd-placar"><b>${d.vitorias}</b> ${d.vitorias === 1 ? "vitória" : "vitórias"} ·
      <b>${d.empates}</b> ${d.empates === 1 ? "empate" : "empates"} ·
      <b>${d.derrotas}</b> ${d.derrotas === 1 ? "derrota" : "derrotas"}
      <small>gols ${d.gols_pro}–${d.gols_contra} em ${plural(d.total, "jogo", "jogos")}</small></p>
    <div class="cd-barra" role="img" aria-label="${d.vitorias} vitórias, ${d.empates} empates e ${d.derrotas} derrotas">
      ${parte(d.vitorias, "v")}${parte(d.empates, "e")}${parte(d.derrotas, "d")}</div>
    <ol class="cd-jogos" aria-label="Últimos encontros, do mais antigo para o mais recente">${lista}</ol>`;
}

function desfalques(lista) {
  if (!lista.length) return `<p class="pg-detalhe">Ninguém fora: elenco completo.</p>`;
  return `<ul class="pj-desfalques">${lista.map((d) => {
    const motivo = d.motivo === "lesao"
      ? `${icone("lesao")} lesionado · ${d.jogos} ${d.jogos === 1 ? "rodada" : "rodadas"}`
      : `<span class="cartao vermelho" aria-hidden="true"></span> suspenso · ${d.jogos} ${d.jogos === 1 ? "jogo" : "jogos"}`;
    return `<li><span>${d.nome}</span> <small>${d.funcao || d.posicao} · ${d.overall}</small>
      <span class="pj-motivo pj-motivo-${d.motivo}">${motivo}</span></li>`;
  }).join("")}</ul>`;
}

function tarjaTime(t) {
  return `${escudo(t.clube, 30)}<span class="pj-tarja-nome">${t.clube}</span>` +
    `<span class="pj-tarja-esquema">${t.formacao}</span>` +
    `<span class="pj-tarja-tatica">${TATICA[t.tatica] || t.tatica}</span>`;
}

// uma metade do campo: cada titular no seu lugar do desenho da formação
// (v1.3). O CSS transforma --x (largura) e --y (profundidade) na posição, no
// campo deitado do computador e no em pé do celular
function metade(t, lado) {
  return `<div class="metade metade-${lado}">${t.titulares.map((j) => peca(t.clube, j)).join("")}</div>`;
}

function sobrenome(nome) {
  const partes = nome.split(" ");
  return partes[partes.length - 1];
}

function sinais(j) {
  const s = [];
  if (j.craque) s.push(`<span class="pj-ic pj-craque" title="Craque">${icone("estrela", "craque")}</span>`);
  if (j.condicao !== "Normal") {
    s.push(`<span class="pj-ic pj-cansado" title="${j.condicao} (energia ${j.energia})">${icone("raio", j.condicao)}</span>`);
  }
  if (j.pendurado) s.push(`<span class="cartao" title="Pendurado" role="img" aria-label="pendurado"></span>`);
  return s.join("");
}

function peca(clube, j) {
  const lugar = j.x != null ? ` style="--x:${j.x};--y:${j.y}"` : "";
  return `<div class="peca"${lugar} title="${j.nome} · ${j.rotulo || j.vaga || j.funcao || j.posicao} · overall ${j.overall} · energia ${j.energia}">
    <span class="peca-camisa">${camisa(clube, { numero: j.numero, tamanho: 44 })}
      <span class="peca-sinais">${sinais(j)}</span></span>
    <span class="peca-nome">${sobrenome(j.nome)}</span>
    <span class="peca-ovr">${j.overall}</span>
  </div>`;
}

function banco(t) {
  if (!t.banco.length) return `<li class="vazio">Sem reservas disponíveis.</li>`;
  return t.banco.map((j) =>
    `<li><b>${j.numero ?? "–"}</b> <span>${j.nome}</span> <small>${j.funcao || j.posicao} · ${j.overall}</small> ${sinais(j)}</li>`
  ).join("");
}

// marcações do gramado: uma versão deitada (computador) e uma em pé
// (celular); o CSS mostra a certa
const MARCAS = `
  <svg class="marcas marcas-h" viewBox="0 0 120 80" preserveAspectRatio="none" aria-hidden="true">
    <rect x="1" y="1" width="118" height="78"/><line x1="60" y1="1" x2="60" y2="79"/>
    <circle cx="60" cy="40" r="9"/><rect x="1" y="22" width="16" height="36"/>
    <rect x="103" y="22" width="16" height="36"/><rect x="1" y="32" width="5" height="16"/>
    <rect x="114" y="32" width="5" height="16"/>
  </svg>
  <svg class="marcas marcas-v" viewBox="0 0 80 120" preserveAspectRatio="none" aria-hidden="true">
    <rect x="1" y="1" width="78" height="118"/><line x1="1" y1="60" x2="79" y2="60"/>
    <circle cx="40" cy="60" r="9"/><rect x="22" y="1" width="36" height="16"/>
    <rect x="22" y="103" width="36" height="16"/><rect x="32" y="1" width="16" height="5"/>
    <rect x="32" y="114" width="16" height="5"/>
  </svg>`;

// volta à rodada SEM redesenhá-la: os seletores continuam no DOM (só
// escondidos) com a escalação que o técnico montou — mostrarRodadaTela
// os refaria a partir do rodadaInfo de quando a rodada abriu
function voltarParaRodada() {
  esconderTudo();
  $("rodada").hidden = false;
}

$("pj-jogar").addEventListener("click", async () => {
  $("pj-jogar").disabled = true;
  voltarParaRodada();
  await jogarAoVivo();   // envia a escalação desses mesmos seletores
  $("pj-jogar").disabled = false;
});
$("pj-voltar").addEventListener("click", () => {
  voltarParaRodada();
  abrirSecaoRodada("partida");   // direto na escalação, não no menu do clube
});
