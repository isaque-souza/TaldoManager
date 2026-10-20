// Navegação do jogo (v1.8): a barra lateral com as seções do clube, o
// botão de ação da faixa da rodada e o "Voltar" do navegador.
//
// As telas continuam se mostrando como antes (esconderTudo + hidden); a
// barra só observa o DOM e se ajusta — nenhuma tela precisa avisá-la.

import { $, estado, pilhaVoltar, secaoVisivel } from "./nucleo.js";
import { abrirSecaoRodada, carregarProximaRodada, mostrarRodadaTela } from "./rodada.js";
import { mostrarTemporada, visaoDoTecnico } from "./temporada.js";
import { mostrarInicio } from "./inicio.js";
import { escudo } from "./identidade.js";
import { icone } from "./icones.js";

// [seção, rótulo, ícone] — a seção é a do hub (data-abrir), "hub" é o menu
const ITENS = [
  ["hub", "Início", "casa"],
  ["partida", "Escalação", "camisa"],
  ["elenco", "Elenco", "prancheta"],
  ["mercado", "Transferências", "troca"],
  ["caixa", "Caixa de entrada", "email"],
  ["tabela", "Tabela", "lista"],
  ["copa", "Copa", "trofeu"],
  ["financas", "Finanças", "carteira"],
  ["estadio", "Estádio", "ingresso"],
  ["marketing", "Marketing", "torcida"],
];

// telas de foco: o jogo (pré-jogo e ao vivo) e o menu inicial ficam sem barra
const SEM_BARRA = ["inicio", "prejogo", "aovivo"];

$("lateral-nav").innerHTML = ITENS.map(([secao, rotulo, ic]) =>
  `<button type="button" data-ir="${secao}">${icone(ic)}<span>${rotulo}</span>` +
  `<b class="lateral-selo" hidden></b></button>`
).join("");

// ---------- mostrar / esconder e marcar a seção atual ----------

function emJogo() {
  const info = estado.rodadaInfo;
  return estado.simId !== null && estado.temporada?.estado === "em_andamento" &&
    !!info && !info.concluida;
}

function secaoAtual(tela) {
  if (tela === "temporada") return "tabela";
  if (tela === "rodada" && estado.faseRodada === "antes") return estado.abaRodada;
  return null;
}

// abas que não cabem rolam para o lado (v1.8): um esmaecido na borda
// direita avisa que há mais, até chegar ao fim
function marcarAbasQueRolam(nav) {
  const navs = nav ? [nav] : document.querySelectorAll(".abas");
  navs.forEach((n) =>
    n.classList.toggle("tem-mais", n.scrollWidth - n.scrollLeft - n.clientWidth > 4)
  );
}
document.addEventListener("scroll", (e) => {
  if (e.target instanceof Element && e.target.classList.contains("abas")) marcarAbasQueRolam(e.target);
}, true);
window.addEventListener("resize", () => marcarAbasQueRolam());

function atualizar() {
  marcarAbasQueRolam();
  const tela = secaoVisivel();
  const visivel = emJogo() && !SEM_BARRA.includes(tela);
  document.body.classList.toggle("com-lateral", visivel);
  $("lateral").hidden = !visivel;
  $("abrir-lateral").hidden = !visivel;
  if (!visivel) {
    fecharGaveta();
    return;
  }
  // voltou ao jogo depois de o Voltar ter gasto a guarda: repõe
  if (history.state?.taldo === "base") history.pushState({ taldo: "guarda" }, "");

  const clube = estado.rodadaInfo.clube_usuario;
  const t = estado.temporada;
  $("lateral-clube").innerHTML = `${escudo(clube, 36)}<span><strong>${clube}</strong>` +
    `<small>${t.carreira_id ? `Temporada ${t.temporada} · ` : ""}rodada ${estado.rodadaInfo.rodada}</small></span>`;

  const atual = secaoAtual(tela);
  document.querySelectorAll("#lateral-nav [data-ir]").forEach((b) => {
    const ativo = b.dataset.ir === atual;
    b.classList.toggle("ativa", ativo);
    if (ativo) b.setAttribute("aria-current", "page");
    else b.removeAttribute("aria-current");
  });

  // a copa só aparece com o clube nela; caixa e elenco herdam o alerta do hub
  const card = (secao) => document.querySelector(`#r-hub [data-abrir="${secao}"]`);
  item("copa").hidden = card("copa").hidden;
  const naoLidas = parseInt($("hub-caixa").textContent, 10);
  selo("caixa", naoLidas > 0 ? String(naoLidas) : "");
  selo("elenco", card("elenco").classList.contains("hub-alerta") ? "!" : "");

  atualizarAcao();
}

const item = (secao) => document.querySelector(`#lateral-nav [data-ir="${secao}"]`);

function selo(secao, texto) {
  const b = item(secao).querySelector(".lateral-selo");
  b.textContent = texto;
  b.hidden = !texto;
}

// o botão da faixa repete a ação principal da tela: jogar a rodada (fora do
// menu do clube, que já tem o card grande) ou seguir para a próxima
function atualizarAcao() {
  const acao = $("r-acao");
  const alvo = alvoDaAcao();
  acao.hidden = !alvo;
  if (!alvo) return;
  acao.innerHTML = alvo.innerHTML;
  acao.disabled = alvo.disabled;
}

function alvoDaAcao() {
  if (secaoVisivel() !== "rodada") return null;
  if (estado.faseRodada === "depois") return $("r-proxima");
  return estado.abaRodada === "hub" ? null : $("r-jogar");
}

$("r-acao").addEventListener("click", () => alvoDaAcao()?.click());

// tudo que muda a barra passa por atributos (hidden, class, disabled) ou
// pelo texto dos botões e do card da caixa: um observador, um quadro
let agendado = false;
function agendar() {
  if (agendado) return;
  agendado = true;
  requestAnimationFrame(() => {
    agendado = false;
    atualizar();
  });
}
const observador = new MutationObserver(agendar);
observador.observe(document.body, {
  subtree: true, attributes: true, attributeFilter: ["hidden", "class", "disabled"],
});
["r-jogar", "r-proxima", "hub-caixa"].forEach((id) =>
  observador.observe($(id), { childList: true, characterData: true, subtree: true })
);

// ---------- ir para uma seção ----------

async function ir(secao) {
  fecharGaveta();
  const tela = secaoVisivel();
  if (secao === "tabela") {
    if (tela !== "temporada") {
      pilhaVoltar.length = 0;
      pilhaVoltar.push(() => mostrarRodadaTela());
      mostrarTemporada();
    }
    return;
  }
  // depois dos resultados, qualquer seção já abre a rodada seguinte
  if (estado.faseRodada === "depois") {
    estado.abaRodada = secao;
    await carregarProximaRodada();
    window.scrollTo(0, 0);
    return;
  }
  if (tela === "rodada") {
    abrirSecaoRodada(secao);
    return;
  }
  // vindo da tabela, de um clube, jogador ou partida: volta para a rodada
  if (tela === "temporada") await visaoDoTecnico();
  pilhaVoltar.length = 0;
  estado.abaRodada = secao;
  mostrarRodadaTela();
  abrirSecaoRodada(secao);
}

$("lateral-nav").addEventListener("click", (e) => {
  const b = e.target.closest("[data-ir]");
  if (b) ir(b.dataset.ir);
});
$("lateral-menu").addEventListener("click", () => {
  fecharGaveta();
  mostrarInicio();
});

// ---------- celular: a barra vira gaveta ----------

function fecharGaveta() {
  document.body.classList.remove("gaveta-aberta");
  $("abrir-lateral").setAttribute("aria-expanded", "false");
}

$("abrir-lateral").addEventListener("click", () => {
  const aberta = document.body.classList.toggle("gaveta-aberta");
  $("abrir-lateral").setAttribute("aria-expanded", String(aberta));
});
$("lateral-fundo").addEventListener("click", fecharGaveta);
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") fecharGaveta();
});

// ---------- o "Voltar" do navegador ----------
// O jogo é uma página só: sem isto, o Voltar sai do site. Uma entrada
// "guarda" no histórico segura o Voltar; ele faz o "← Voltar" do jogo e a
// guarda é reposta. Na tela inicial não há para onde voltar: aí sai mesmo.

function voltarNoJogo() {
  if (document.body.classList.contains("gaveta-aberta")) {
    fecharGaveta();
    return true;
  }
  const tela = secaoVisivel();
  if (!tela || tela === "inicio") return false;
  if (tela === "aovivo") return true;   // a partida segue: não se sai no meio
  if (tela === "prejogo") {
    $("pj-voltar").click();
    return true;
  }
  // uma tela dentro da tela (a ficha do elenco no celular): fecha ela antes
  const local = [...$(tela).querySelectorAll("[data-voltar-local]")].find((b) => b.offsetParent);
  if (local) {
    local.click();
    return true;
  }
  if (tela === "rodada") {
    if (estado.faseRodada === "antes" && estado.abaRodada !== "hub") abrirSecaoRodada("hub");
    else mostrarInicio();
    return true;
  }
  // tabela, clube, jogador, partida, carreira: o "← Voltar" da própria tela
  const botao = [...$(tela).querySelectorAll(".voltar")].find((b) => !b.hidden);
  if (botao) botao.click();
  else mostrarInicio();
  return true;
}

if (history.state?.taldo !== "guarda") {
  history.replaceState({ taldo: "base" }, "");
  history.pushState({ taldo: "guarda" }, "");
}
window.addEventListener("popstate", () => {
  if (voltarNoJogo()) history.pushState({ taldo: "guarda" }, "");
  else history.back();
});
