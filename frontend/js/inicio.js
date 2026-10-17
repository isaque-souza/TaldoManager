// Tela inicial (v1.0): continuar, novo jogo (escolha do clube) e carregar.

import { $, esconderTudo, limparAviso, pedir, pilhaVoltar } from "./nucleo.js";
import { carregarLista, lerSessao, preencherLista } from "./saves.js";
import { dinheiro } from "./tabelas.js";

let clubes = null;      // cache de GET /clubes (a seed não muda)
let escolhido = null;   // nome do clube marcado em "Novo jogo"
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
  return s.estado === "em_andamento"
    ? `${temporada} · rodada ${s.rodada_atual}/${s.rodadas}`
    : `${temporada} encerrada · 🏆 ${s.campeao}`;
}

function quando(s) {
  return new Date(s.atualizada_em || s.criada_em).toLocaleString("pt-BR", {
    dateStyle: "short", timeStyle: "short",
  });
}

function tituloSave(s) {
  return s.clube_usuario ? `🎮 ${s.clube_usuario}` : `Simulação #${s.id}`;
}

function renderContinuar(sims) {
  // o save aberto por último (lembrado no navegador) ou, sem isso, o
  // jogado por último — a lista já vem nessa ordem
  const sessao = lerSessao();
  const alvo = sims.find((s) => s.id === Number(sessao.simId)) || sims[0];
  $("inicio-continuar").hidden = !alvo;
  if (!alvo) return;

  $("inicio-continuar-titulo").textContent = tituloSave(alvo);
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
  $("inicio-clubes").innerHTML = [...clubes]
    .sort((a, b) => a.ranking_forca - b.ranking_forca)
    .map((c) => `
      <button class="card-clube${c.nome === escolhido ? " escolhido" : ""}" data-clube="${c.nome}">
        <strong>${c.nome}</strong>
        <small>${c.pais}</small>
        <span class="estrelas" title="${c.ranking_forca}º elenco mais forte">${estrelas(c.ranking_forca)}</span>
        <span>💪 ${c.forca.toLocaleString("pt-BR")} · ${c.ranking_forca}º em força</span>
        <span>💰 ${dinheiro(c.dinheiro)} · 👥 ${dinheiro(c.torcedores)}</span>
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
  $("comecar").disabled = !escolhido;
  $("comecar").textContent = escolhido ? `▶ Começar com ${escolhido}` : "Escolha um clube";
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
          <div>
            <strong>${tituloSave(s)}</strong>
            <small>${situacao(s)} · jogado em ${quando(s)}</small>
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
