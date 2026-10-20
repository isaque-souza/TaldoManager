// Caixa de entrada (v1.3): os setores do clube escrevem para o técnico,
// como no Football Manager e no modo carreira do FIFA. O diretor de futebol
// responde as propostas (e diz o que faltou), o departamento médico avisa
// das lesões, o auxiliar técnico das suspensões e do cansaço, a diretoria da
// meta. Abrir uma mensagem marca como lida.

import { $, estado, pedir } from "./nucleo.js";
import { icone } from "./icones.js";
import { dataCurta } from "./calendario.js";

const ICONE_SETOR = {
  "Olheiro": "alvo",
  "Diretor de futebol": "troca",
  "Departamento médico": "lesao",
  "Auxiliar técnico": "prancheta",
  Diretoria: "alvo",
  "Categorias de base": "base",
  Marketing: "torcida",
};

const cx = { dados: null, filtro: "todos", aberta: null };

const base = () => `/simulacoes/${estado.simId}/mensagens`;

export async function carregarCaixa() {
  if (!estado.simId) return;
  const dados = await pedir(base());
  if (!dados) return;
  cx.dados = dados;
  renderCaixa();
}

function quando(m) {
  const rodada = m.rodada == null ? "Pré-temporada" : `Rodada ${m.rodada}`;
  return m.data ? `${dataCurta(m.data)} · ${rodada}` : rodada;   // a data (v2.0)
}

function renderHubCaixa() {
  const { mensagens, nao_lidas } = cx.dados;
  $("hub-caixa").textContent = nao_lidas
    ? `${nao_lidas} ${nao_lidas === 1 ? "nova" : "novas"}`
    : "Tudo lido";
  const ultima = mensagens[0];
  $("hub-caixa-info").textContent = ultima ? `${ultima.setor}: ${ultima.assunto}` : "nenhuma mensagem ainda";
  $("hub-caixa").closest(".hub-card").classList.toggle("hub-alerta", nao_lidas > 0);
}

function renderCaixa() {
  renderHubCaixa();
  const { mensagens, nao_lidas, setores } = cx.dados;
  const naoLidasDo = (s) => mensagens.filter((m) => m.setor === s && !m.lida).length;
  const chip = (valor, rotulo, novas) =>
    `<button class="cx-filtro ${cx.filtro === valor ? "ativo" : ""}" data-filtro="${valor}"
       aria-pressed="${cx.filtro === valor}">${rotulo}${novas ? ` <b>${novas}</b>` : ""}</button>`;

  const visiveis = cx.filtro === "todos" ? mensagens : mensagens.filter((m) => m.setor === cx.filtro);
  const item = (m) => {
    const aberta = cx.aberta === m.id;
    return `<li class="cx-msg ${m.lida ? "" : "nova"} ${aberta ? "aberta" : ""}">
      <button class="cx-topo" data-abrir="${m.id}" aria-expanded="${aberta}">
        <span class="cx-icone" aria-hidden="true">${icone(ICONE_SETOR[m.setor] || "contrato")}</span>
        <span class="cx-texto"><small>${m.setor} · ${quando(m)}</small><b>${m.assunto}</b></span>
        ${m.lida ? "" : `<span class="cx-ponto" aria-label="não lida"></span>`}
      </button>
      ${aberta ? `<p class="cx-corpo">${m.corpo}</p>` : ""}
    </li>`;
  };

  $("r-caixa").innerHTML = `
    <div class="cx-barra">
      <div class="cx-filtros" role="group" aria-label="Filtrar por setor">
        ${chip("todos", "Todas", nao_lidas)}
        ${setores.map((s) => chip(s, s, naoLidasDo(s))).join("")}
      </div>
      ${nao_lidas ? `<button class="secondary outline cx-todas" id="cx-todas">${icone("ok")} Marcar todas como lidas</button>` : ""}
    </div>
    <ul class="cx-lista">${visiveis.length ? visiveis.map(item).join("")
      : `<li class="vazio">Nenhuma mensagem${cx.filtro === "todos" ? "" : " deste setor"}.</li>`}</ul>`;

  $("r-caixa").querySelectorAll("[data-filtro]").forEach((b) =>
    b.addEventListener("click", () => { cx.filtro = b.dataset.filtro; renderCaixa(); })
  );
  $("r-caixa").querySelectorAll("[data-abrir]").forEach((b) =>
    b.addEventListener("click", () => abrir(Number(b.dataset.abrir)))
  );
  const todas = $("cx-todas");
  if (todas) todas.addEventListener("click", lerTodas);
}

async function abrir(id) {
  cx.aberta = cx.aberta === id ? null : id;
  const m = cx.dados.mensagens.find((x) => x.id === id);
  renderCaixa();
  if (cx.aberta && m && !m.lida) {
    const dados = await pedir(`${base()}/${id}/lida`, { method: "POST" });
    if (dados) { cx.dados = dados; renderCaixa(); }
  }
}

async function lerTodas() {
  const dados = await pedir(`${base()}/lidas`, { method: "POST" });
  if (dados) { cx.dados = dados; renderCaixa(); }
}
