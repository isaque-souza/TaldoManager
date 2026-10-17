// Modo carreira (v0.8): a tela da carreira (temporadas, títulos, líderes
// históricos e Hall da Fama) e a aba "Virada" da visão da temporada.

import { $, esconderTudo, estado, pedir } from "./nucleo.js";
import { carregarLista } from "./saves.js";
import { tabela } from "./tabelas.js";

// ---------- tela da carreira ----------

const LIDERES = {
  gols: ["Gols", [["nome", "Jogador"], ["clube", "Clube"], ["gols", "Gols"],
    ["assistencias", "Assist."], ["temporadas", "Temp."]]],
  assistencias: ["Assistências", [["nome", "Jogador"], ["clube", "Clube"],
    ["assistencias", "Assist."], ["gols", "Gols"], ["temporadas", "Temp."]]],
  partidas: ["Partidas", [["nome", "Jogador"], ["clube", "Clube"],
    ["posicao", "Posição"], ["partidas", "Jogos"], ["temporadas", "Temp."]]],
  premios: ["Prêmios", [["nome", "Jogador"], ["clube", "Clube"],
    ["artilharias", "Artilharias"], ["mvps", "MVPs"], ["titulos", "Títulos"]]],
};

let abaLideres = "gols";

export async function abrirCarreira(carreiraId) {
  const c = await pedir(`/carreiras/${carreiraId}`);
  if (!c) return;
  estado.carreira = c;
  mostrarCarreira();
}

export function mostrarCarreira() {
  const c = estado.carreira;
  esconderTudo();
  $("carreira").hidden = false;

  const meus = c.titulos.find((t) => t.clube === c.clube_usuario)?.titulos ?? 0;
  $("carreira-titulo").textContent = `📜 Carreira — ${c.clube_usuario}`;
  $("carreira-info").textContent =
    `${c.temporadas.length} temporada${c.temporadas.length > 1 ? "s" : ""} · ` +
    `${meus} título${meus === 1 ? "" : "s"} seu${meus === 1 ? "" : "s"} · ` +
    `seed ${c.seed ?? "aleatório"}`;

  renderTemporadas(c);
  renderTitulos(c);
  renderLideres(c);
  renderHall(c);
}

function destaque(d) {
  return d ? `${d.nome} <small>(${d.clube}) · ${d.valor}</small>` : "—";
}

function renderTemporadas(c) {
  const linhas = c.temporadas.map((t) => ({
    ...t,
    t: `<a class="temporada" data-sim="${t.simulacao_id}">T${t.temporada}</a>`,
    camp: t.estado === "em_andamento"
      ? `<span class="vazio">em andamento · rodada ${t.rodada_atual}</span>`
      : `🏆 ${t.campeao}`,
    vice: t.vice ?? "",
    art: t.estado === "em_andamento" ? "" : destaque(t.artilheiro),
    mvpd: t.estado === "em_andamento" ? "" : destaque(t.mvp),
    voce: t.posicao_usuario ? `${t.posicao_usuario}º` : "",
  }));
  $("carreira-temporadas").innerHTML = tabela(
    linhas,
    [["t", "Temp."], ["camp", "Campeão"], ["vice", "Vice"],
      ["art", "Artilheiro (gols)"], ["mvpd", "MVP (melhor em campo)"], ["voce", "Você"]],
    (t) => (t.campeao === c.clube_usuario ? "eu" : "")
  );
  $("carreira-temporadas").querySelectorAll("a.temporada").forEach((a) =>
    a.addEventListener("click", () => carregarLista(Number(a.dataset.sim)))
  );
}

function renderTitulos(c) {
  const linhas = c.titulos.map((t) => ({
    ...t,
    anos: t.temporadas.map((n) => `T${n}`).join(", "),
  }));
  $("carreira-titulos").innerHTML = tabela(
    linhas,
    [["clube", "Clube"], ["titulos", "Títulos"], ["anos", "Temporadas"]],
    (t) => (t.clube === c.clube_usuario ? "eu" : "")
  );
}

function renderLideres(c) {
  $("carreira-lideres-abas").innerHTML = Object.entries(LIDERES)
    .map(([k, [rot]]) =>
      `<button data-aba="${k}" class="${k === abaLideres ? "ativa" : ""}">${rot}</button>`)
    .join("");
  $("carreira-lideres-abas").querySelectorAll("button").forEach((b) =>
    b.addEventListener("click", () => {
      abaLideres = b.dataset.aba;
      renderLideres(c);
    })
  );
  const [, colunas] = LIDERES[abaLideres];
  $("carreira-lideres").innerHTML = tabela(
    c.lideres[abaLideres],
    colunas,
    (j) => (j.clube === c.clube_usuario ? "eu" : "")
  );
}

function renderHall(c) {
  const hall = c.hall_da_fama;
  $("carreira-hall").innerHTML = hall.length
    ? `<div class="hall">${hall.map((l) => `
        <article class="${l.clube === c.clube_usuario ? "eu" : ""}">
          <header><strong>${l.nome}</strong> <small>${l.posicao}</small>
            <span class="pontos">${l.pontos} pts</span></header>
          <p>${l.motivo}</p>
          <small>${l.clube} · aposentou aos ${l.idade}, após a temporada
            ${l.ultima_temporada} · ${l.temporadas} temp. · ${l.partidas} jogos</small>
        </article>`).join("")}</div>`
    : `<p class="vazio">Ninguém ainda. Os aposentados entram com 5 ou mais
        pontos de lenda.</p>`;
}

// ---------- aba "Virada" (temporada 2 em diante) ----------

const TIPOS = {
  saiu_livre: "🚪 Saiu de graça",
  chegou_livre: "✍️ Chegou de graça",
  renovou: "🔁 Renovou",
  subiu_da_base: "🌱 Subiu da base",
  aposentou: "🧓 Aposentou",
  adiou: "⏳ Adiou a aposentadoria",
};

// "potencial 85" -> 85 (o detalhe do jovem da base)
const potencial = (m) => Number(m.detalhe.replace(/\D/g, "")) || 0;

function listaMovimentos(movs, mostrarClube) {
  if (!movs.length) return `<p class="vazio">Nada.</p>`;
  return `<ul class="movimentos">${movs.map((m) => `
    <li><span class="tipo">${TIPOS[m.tipo] ?? m.tipo}</span>
      <strong>${m.jogador}</strong>
      <small>${m.posicao} · ${m.idade} anos · ${m.overall}${mostrarClube ? ` · ${m.clube}` : ""}
      ${m.detalhe ? ` · ${m.detalhe}` : ""}</small></li>`).join("")}</ul>`;
}

function tabelaEvolucao(evo) {
  if (!evo.length) return `<p class="vazio">Nada.</p>`;
  const linhas = evo.map((l) => {
    if (l.overall_antes == null) {
      return { ...l, ovr: `${l.overall}`, delta: `<span class="vazio">novo · base</span>`,
        pot: `${l.potencial}` };
    }
    const d = l.overall - l.overall_antes;
    const seta = d > 0 ? `<span class="sobe">▲${d}</span>`
      : d < 0 ? `<span class="cai">▼${-d}</span>` : `<span class="vazio">=</span>`;
    const veio = l.clube_antes !== estado.temporada.clube_usuario
      ? ` <small class="vazio">veio do ${l.clube_antes}</small>` : "";
    return {
      ...l,
      ovr: `${l.overall_antes} → <strong>${l.overall}</strong>`,
      delta: seta + veio,
      pot: l.potencial_antes === l.potencial ? `${l.potencial}`
        : `${l.potencial_antes} → ${l.potencial}`,
    };
  });
  return tabela(linhas, [["nome", "Jogador"], ["posicao", "Posição"], ["idade", "Idade"],
    ["ovr", "Overall"], ["delta", "Variação"], ["pot", "Potencial"]]);
}

export function renderVirada() {
  const t = estado.temporada;
  const meu = t.clube_usuario;
  const movs = t.movimentos_virada;
  const meus = movs.filter((m) => m.clube === meu && m.tipo !== "adiou");
  const outros = movs.filter((m) => m.clube !== meu);

  const aposentados = outros.filter((m) => m.tipo === "aposentou")
    .sort((a, b) => b.overall - a.overall);
  const saidas = outros.filter((m) => m.tipo === "saiu_livre");
  const joias = outros.filter((m) => m.tipo === "subiu_da_base")
    .sort((a, b) => potencial(b) - potencial(a)).slice(0, 5);
  const renovacoes = outros.filter((m) => m.tipo === "renovou").length;
  const jovens = outros.filter((m) => m.tipo === "subiu_da_base").length;

  return `
    <p class="vazio">O que mudou entre a temporada ${t.temporada - 1} e a ${t.temporada}.</p>
    <h4>Seu clube — ${meu}</h4>
    ${listaMovimentos(meus, false)}
    <h4>Seu elenco: quem subiu e quem caiu</h4>
    ${tabelaEvolucao(t.evolucao_virada)}
    <h4>Na liga</h4>
    <p><small>${renovacoes} renovações automáticas da CPU · ${jovens} jovens
      subiram da base nos outros clubes.</small></p>
    <h5>Aposentadorias</h5>
    ${listaMovimentos(aposentados, true)}
    <h5>Saídas de graça</h5>
    ${listaMovimentos(saidas, true)}
    <h5>Maiores joias da base</h5>
    ${listaMovimentos(joias, true)}`;
}
