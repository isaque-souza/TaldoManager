// Tela inicial (v1.0): continuar, novo jogo (escolha do clube) e carregar.

import { $, esconderTudo, limparAviso, pedir, pilhaVoltar } from "./nucleo.js";
import { carregarLista, lerSessao, preencherLista } from "./saves.js";
import { dinheiro } from "./tabelas.js";
import { camisa, escudo } from "./identidade.js";
import { icone } from "./icones.js";
import { abasLiga } from "./ligas.js";

let clubes = null;      // cache de GET /clubes (a seed não muda)
let escolhido = null;   // nome do clube marcado em "Novo jogo"
let ligaVista = "taldo"; // a liga cujos clubes aparecem em "Novo jogo" (v1.6)
let painel = null;      // "novo" | "carregar" (null = decide pelos saves)

export async function mostrarInicio() {
  limparAviso();
  esconderTudo();
  $("inicio").hidden = false;
  $("menu").hidden = true;
  pilhaVoltar.length = 0;

  const [sims, lista] = await Promise.all([pedir("/simulacoes"), clubes ?? pedir("/clubes")]);
  if (lista) clubes = lista;
  renderContinuar(sims || []);
  renderClubes();
  renderSaves(sims || []);
  preencherLista(sims || []);
  // primeira visita sem save nenhum: já abre em "Novo jogo"
  mostrarPainel(painel ?? (sims?.length ? "carregar" : "novo"));
}

// "Novo jogo" de fora do menu (ex.: fim de carreira)
export function novoJogo() {
  painel = "novo";
  mostrarInicio();
  window.scrollTo(0, 0);
}

function mostrarPainel(qual) {
  painel = qual;
  document.querySelectorAll("[data-inicio]").forEach((b) =>
    b.classList.toggle("ativa", b.dataset.inicio === qual)
  );
  document.querySelectorAll("[data-inicio-painel]").forEach((p) =>
    (p.hidden = p.dataset.inicioPainel !== qual)
  );
}

// abre um save no topo da página (a grade de clubes pode estar rolada)
async function abrir(id, abas) {
  await carregarLista(id, abas);
  window.scrollTo(0, 0);
}

// ---------- continuar ----------

function situacao(s) {
  const temporada = `temporada ${s.temporada}`;
  if (s.fim_de_carreira) return `${temporada} · fim de carreira (demitido)`;
  return s.estado === "em_andamento"
    ? `${temporada} · rodada ${s.rodada_atual}/${s.rodadas}`
    : `${temporada} encerrada · campeão: ${s.campeao}`;
}

function quando(s) {
  return new Date(s.atualizada_em || s.criada_em).toLocaleString("pt-BR", {
    dateStyle: "short", timeStyle: "short",
  });
}

function tituloSave(s) {
  return s.clube_usuario ? s.clube_usuario : `Simulação #${s.id}`;
}

function escudoSave(s, tamanho) {
  return s.clube_usuario ? escudo(s.clube_usuario, tamanho) : "";
}

function renderContinuar(sims) {
  // o save jogado por último (a lista já vem nessa ordem) — e não o
  // último aberto: olhar uma temporada antiga não muda onde você parou.
  // O navegador só lembra a aba. Demitido é fim de jogo: nada a continuar.
  const sessao = lerSessao();
  const ultimo = sims[0];
  const alvo = ultimo && !ultimo.fim_de_carreira ? ultimo : null;
  $("inicio-continuar").hidden = !alvo;
  if (!alvo) return;

  $("inicio-continuar-titulo").innerHTML =
    `<span class="com-escudo">${escudoSave(alvo, 40)}${tituloSave(alvo)}</span>`;
  $("inicio-continuar-info").textContent = `${situacao(alvo)} · jogado em ${quando(alvo)}`;
  $("continuar").onclick = () =>
    abrir(alvo.id, alvo.id === Number(sessao.simId) ? sessao : undefined);
}

// ---------- novo jogo ----------

// estrelas pelo ranking de força: dá a ideia do tamanho do desafio
function estrelas(ranking) {
  const n = ranking <= 2 ? 5 : ranking <= 6 ? 4 : ranking <= 12 ? 3 : ranking <= 16 ? 2 : 1;
  return "★".repeat(n) + "☆".repeat(5 - n);
}

function renderClubes() {
  if (!clubes) return;
  const ligas = [...new Set(clubes.map((c) => c.liga || "taldo"))];
  $("inicio-ligas").innerHTML = abasLiga(ligas, ligaVista);
  $("inicio-ligas").querySelectorAll("[data-liga]").forEach((b) =>
    b.addEventListener("click", () => { ligaVista = b.dataset.liga; renderClubes(); })
  );
  $("inicio-clubes").innerHTML = clubes
    .filter((c) => (c.liga || "taldo") === ligaVista)
    .sort((a, b) => a.ranking_forca - b.ranking_forca)
    .map((c) => `
      <button class="card-clube${c.nome === escolhido ? " escolhido" : ""}" data-clube="${c.nome}">
        <span class="card-clube-visual">${camisa(c.nome, { tamanho: 64 })}${escudo(c.nome, 34)}</span>
        <strong>${c.nome}</strong>
        <small>${c.pais} · <span class="estrelas" title="${c.ranking_forca}º elenco mais forte">${estrelas(c.ranking_forca)}</span></small>
        <dl class="ficha">
          <div><dt>Força</dt><dd>${c.forca.toLocaleString("pt-BR")} <small>${c.ranking_forca}º</small></dd></div>
          <div><dt>Caixa</dt><dd>${dinheiro(c.dinheiro)}</dd></div>
          <div><dt>Torcida</dt><dd>${dinheiro(c.torcedores)}</dd></div>
        </dl>
        <span class="card-meta"><span class="meta-rotulo">Meta</span> ${c.meta}</span>
      </button>`)
    .join("");
  $("inicio-clubes").querySelectorAll("[data-clube]").forEach((b) =>
    b.addEventListener("click", () => escolher(b.dataset.clube))
  );
  atualizarComecar();
}

function escolher(nome) {
  escolhido = nome;
  $("inicio-clubes").querySelectorAll("[data-clube]").forEach((b) =>
    b.classList.toggle("escolhido", b.dataset.clube === nome)
  );
  atualizarComecar();
}

function atualizarComecar() {
  $("barra-comecar").classList.toggle("visivel", !!escolhido);
  $("comecar").disabled = !escolhido;
  $("comecar").innerHTML = escolhido
    ? `${icone("play")} Começar com ${escolhido}`
    : "Escolha um clube";
}

async function comecar() {
  if (!escolhido) return;
  limparAviso();
  $("comecar").disabled = true;
  $("comecar").setAttribute("aria-busy", "true");
  // jogo de verdade é sempre rodada a rodada; a escalação se monta na
  // tela da rodada (e se salva sozinha)
  const criada = await pedir("/simulacoes", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ clube: escolhido, modo: "rodada_a_rodada" }),
  });
  $("comecar").removeAttribute("aria-busy");
  atualizarComecar();
  if (!criada) return;
  escolhido = null;
  painel = null;
  await abrir(criada.id);
}

// ---------- carregar ----------

function renderSaves(sims) {
  $("inicio-saves").innerHTML = sims.length
    ? sims.map((s) => `
        <article class="save">
          <div class="com-escudo">
            ${escudoSave(s, 28)}
            <span><strong>${tituloSave(s)}</strong>
            <small>${situacao(s)} · jogado em ${quando(s)}</small></span>
          </div>
          <div class="save-acoes">
            <button data-abrir="${s.id}">Abrir</button>
            <button data-apagar="${s.id}" class="secondary outline">Apagar</button>
          </div>
        </article>`).join("")
    : `<p class="vazio">Nenhum jogo salvo ainda — comece um em “Novo jogo”.</p>`;

  $("inicio-saves").querySelectorAll("[data-abrir]").forEach((b) =>
    b.addEventListener("click", () => abrir(Number(b.dataset.abrir)))
  );
  // apagar pede um segundo clique (sem confirm(), que trava a página)
  $("inicio-saves").querySelectorAll("[data-apagar]").forEach((b) =>
    b.addEventListener("click", async () => {
      if (!b.classList.contains("confirmar")) {
        b.classList.add("confirmar");
        b.textContent = "Apagar mesmo?";
        return;
      }
      if (await pedir(`/simulacoes/${b.dataset.apagar}`, { method: "DELETE" })) {
        await mostrarInicio();
      }
    })
  );
}

// ---------- ligações ----------

document.querySelectorAll("[data-inicio]").forEach((b) =>
  b.addEventListener("click", () => mostrarPainel(b.dataset.inicio))
);
$("comecar").addEventListener("click", comecar);
$("menu").addEventListener("click", mostrarInicio);
