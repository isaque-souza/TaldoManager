// Marketing (v1.4): o tamanho da torcida, o mando de campo que ela dá e as
// campanhas para ela crescer (uma por turno, pagas do caixa).

import { $, api, estado, limparAviso, ocupado, pedir } from "./nucleo.js";
import { dinheiro, reais, tabela } from "./tabelas.js";
import { icone } from "./icones.js";
import { estadioNoturno } from "./atmosfera.js";
import { escudo } from "./identidade.js";
import { carregarCaixa } from "./caixa.js";
import { carregarProximaRodada } from "./rodada.js";

// aviso: o resultado da última campanha (sobrevive ao recarregamento da
// rodada que vem logo depois); ruim = o motivo de não ter dado
const mk = { dados: null, aviso: "", ruim: false, avisoRodada: null };
const rodadaAtual = () => estado.rodadaInfo && estado.rodadaInfo.rodada;

const caminho = () => `/simulacoes/${estado.simId}/marketing`;

export async function carregarMarketing() {
  if (!estado.simId) return;
  const dados = await pedir(caminho());
  if (!dados) return;
  mk.dados = dados;
  renderMarketing();
}

function pct(atual, inicial) {
  if (!inicial) return 0;
  return (atual / inicial - 1) * 100;
}

function renderHubMarketing() {
  const d = mk.dados;
  $("hub-marketing").textContent = `${dinheiro(d.torcedores)} torcedores`;
  $("hub-marketing-info").textContent = d.disponivel
    ? `campanha disponível no ${d.turno}º turno`
    : `campanha do ${d.turno}º turno já feita`;
}

const centavos = (v) => `R$ ${v.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

function cardCampanha(c, maxNovos, maxCusto) {
  const barra = (classe, rotulo, v, max) => `<div class="mk-comp"><span>${rotulo}</span>
      <span class="mk-comp-trilho"><span class="${classe}" style="width:${((v / max) * 100).toFixed(1)}%"></span></span></div>`;
  const bloqueio = c.bloqueio
    ? `<small class="mk-bloqueio">${icone("cadeado")} ${c.bloqueio}</small>`
    : "";
  return `<article class="mk-campanha">
      <header><strong>${c.nome}</strong></header>
      <p>${c.descricao}</p>
      <div class="mk-comps">
        ${barra("mk-comp-ganho", "traz", c.torcedores_novos, maxNovos)}
        ${barra("mk-comp-custo", "custa", c.custo, maxCusto)}
        <small>${centavos(c.custo / (c.torcedores_novos || 1))} por torcedor novo</small>
      </div>
      <dl class="mk-ficha">
        <div><dt>Torcida</dt><dd>+${c.ganho_pct.toLocaleString("pt-BR")}% <small>(+${dinheiro(c.torcedores_novos)})</small></dd></div>
        <div><dt>Custo</dt><dd>${reais(c.custo)}</dd></div>
      </dl>
      ${bloqueio}
      <button class="mk-fazer secondary outline" data-tipo="${c.tipo}" ${c.bloqueio ? "disabled" : ""}>Lançar campanha</button>
    </article>`;
}

function renderMarketing() {
  const d = mk.dados;
  renderHubMarketing();

  const variacao = pct(d.torcedores, d.torcedores_inicial);
  const fmt = Math.abs(variacao).toLocaleString("pt-BR", { maximumFractionDigits: 1 });
  const detalhe = Math.abs(variacao) < 0.05
    ? "igual ao início da temporada"
    : `${variacao > 0 ? "▲ +" : "▼ −"}${fmt}% na temporada`;
  const mando = d.mando_de_campo.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

  const feitas = d.feitas.length
    ? tabela(
        d.feitas.map((f) => ({
          ...f,
          rod: `Rodada ${f.rodada}`,
          cst: dinheiro(f.custo),
          nov: `+${dinheiro(f.torcedores_novos)}`,
        })),
        [["rod", "Quando"], ["nome", "Campanha"], ["cst", "Custo"], ["nov", "Torcedores"]],
      )
    : `<p class="vazio">Nenhuma campanha nesta temporada.</p>`;

  const meu = estado.rodadaInfo && estado.rodadaInfo.clube_usuario;
  // a torcida cheia de bandeiras: é a tela dela
  const fundo = meu ? estadioNoturno({ mandante: meu, visitante: meu, ocupacao: 0.95, lotado: true, semente: "torcida" }) : "";
  const numero = (rotulo, valor, detalhe, cls = "") =>
    `<div class="es-numero"><span>${rotulo}</span><strong class="${cls}">${valor}</strong><small>${detalhe}</small></div>`;
  // os dois turnos: o selo diz se a campanha deste já foi feita
  const turnos = [1, 2].map((n) => {
    const estado_ = n < d.turno ? "passou" : n > d.turno ? "depois" : d.disponivel ? "livre" : "feita";
    const texto = { passou: "encerrado", depois: "ainda não", livre: "campanha disponível", feita: "campanha feita" }[estado_];
    return `<span class="mk-turno mk-turno-${estado_}">${n}º turno · ${texto}</span>`;
  }).join("");

  $("r-marketing").innerHTML = `
    <div class="cartaz es-capa">
      <div class="cartaz-fundo">${fundo}</div>
      <div class="es-capa-palco">
        <p class="es-capa-titulo">${meu ? escudo(meu, 34) : ""}<span><small>A torcida do</small><b>${meu || "clube"}</b></span></p>
        <p class="mk-turnos">${turnos}</p>
        <div class="es-numeros mk-numeros">
          ${numero("Torcedores", dinheiro(d.torcedores), detalhe, variacao < -0.05 ? "negativo" : "")}
          ${numero("Força em casa", `+${mando}`, "de overall no mando de campo")}
          ${numero("Caixa", reais(d.caixa), "para investir", d.caixa < 0 ? "negativo" : "")}
        </div>
      </div>
    </div>
    <p class="mk-intro">Uma campanha por turno. Torcida maior enche o estádio
      (bilheteria) e empurra o time em casa; vitórias e clássicos também a
      fazem crescer.</p>
    <p id="mk-msg" class="mk-msg${mk.ruim ? " ruim" : ""}" role="status">${mk.avisoRodada === rodadaAtual() ? mk.aviso : ""}</p>
    <div class="mk-campanhas">${d.campanhas.map((c) => cardCampanha(c,
      Math.max(...d.campanhas.map((x) => x.torcedores_novos), 1),
      Math.max(...d.campanhas.map((x) => x.custo), 1))).join("")}</div>
    <h3 class="secao">Campanhas da temporada</h3>
    ${feitas}`;

  $("r-marketing").querySelectorAll(".mk-fazer").forEach((b) =>
    b.addEventListener("click", () => cliqueCampanha(b))
  );
}

// POST com o motivo do 400 visível, aqui na seção (sem caixa, já fez...)
async function postar(corpo) {
  limparAviso();
  ocupado(true, "Lançando a campanha…");
  try {
    const resp = await fetch(api() + caminho(), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(corpo),
    });
    const dados = await resp.json().catch(() => ({}));
    if (!resp.ok) return { erro: dados.detail || `HTTP ${resp.status}` };
    return dados;
  } catch (e) {
    return { erro: e.message };
  } finally {
    ocupado(false);
  }
}

// dois cliques, como no mercado (sem confirm(), que trava a página)
async function cliqueCampanha(botao) {
  if (botao.dataset.confirmar !== "1") {
    botao.dataset.confirmar = "1";
    botao.textContent = "Confirmar?";
    return;
  }
  const dados = await postar({ tipo: botao.dataset.tipo });
  if (dados.erro) {
    mk.aviso = `${icone("nao")} Não deu: ${dados.erro}.`;
    mk.ruim = true;
    mk.avisoRodada = rodadaAtual();
    return carregarMarketing();
  }
  mk.dados = dados;
  const ultima = dados.feitas[0];
  mk.aviso = `${icone("ok")} ${ultima.nome} no ar: +${dinheiro(ultima.torcedores_novos)} torcedores.`;
  mk.ruim = false;
  mk.avisoRodada = rodadaAtual();
  renderMarketing();
  carregarCaixa();
  await carregarProximaRodada();   // caixa e finanças mudaram
}
