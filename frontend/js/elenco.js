// Central do Elenco (v1.7): o elenco com filtros e a ficha do jogador
// escolhido, com as ações (renovar, lista de transferências, dispensar).
// Os dados vêm do mercado (contrato, valor, a temporada) e da próxima rodada
// (energia, lesão, suspensão).

import { $, estado, navegarPara } from "./nucleo.js";
import { dinheiro, tabela } from "./tabelas.js";
import { abrirSecaoRodada, carregarProximaRodada } from "./rodada.js";
import { avisoMercado, carregarMercado, mostrarOfertas, postarMercado } from "./mercado.js";
import { abrirContrato, MULTA_ROTULO } from "./contratos.js";
import { abrirJogador } from "./jogador.js";
import { carregarCaixa } from "./caixa.js";
import { icone, seloIdolo } from "./icones.js";
import { barrasAtributos } from "./atributos.js";
import { camisa } from "./identidade.js";
import { posicaoDe, sigla } from "./posicoes.js";

// setor: "" (todos), um setor do motor ou "venda" (a lista de transferências)
const FILTROS = [
  ["", "Todos"], ["Goleiro", "Goleiros"], ["Defesa", "Defesa"],
  ["Meio-Campo", "Meio-campo"], ["Atacante", "Ataque"], ["venda", "À venda"],
];
const filtro = { setor: "", selecionado: null };
let mercado = null;   // o último GET /mercado, para redesenhar sem pedir de novo

export function renderElenco(m) {
  mercado = m;
  if (!m.elenco.some((f) => f.jogador_id === filtro.selecionado)) {
    filtro.selecionado = m.elenco[0]?.jogador_id ?? null;
  }
  desenhar();
}

// energia e situação vêm da próxima rodada (o mercado não sabe delas)
function situacaoDe(nome) {
  const j = estado.rodadaInfo?.elenco.find((e) => e.nome === nome);
  if (!j) return { chip: "", energia: null };
  let chip = "";
  if (j.lesionado) chip = `<span class="chip chip-longe">Lesionado ${j.rodadas_lesao}r</span>`;
  else if (j.suspenso) chip = `<span class="chip chip-longe">Suspenso ${j.jogos_suspensao}j</span>`;
  else if (j.amarelos_ciclo === 4) chip = `<span class="chip chip-perto">Pendurado</span>`;
  return { chip, energia: j.energia };
}

// na lista, o contrato acabando vai no selo da coluna "Temp." (cabe melhor)
function selos(f, { acabando = true } = {}) {
  return [
    f.idolo ? seloIdolo() : "",
    f.a_venda ? `<span class="chip">À venda</span>` : "",
    acabando && f.contrato_anos <= 1 ? `<span class="chip chip-perto">Acabando</span>` : "",
  ].join(" ");
}

function lista() {
  const passa = (f) =>
    !filtro.setor || (filtro.setor === "venda" ? f.a_venda : f.posicao === filtro.setor);
  const linhas = mercado.elenco.filter(passa).map((f) => {
    const s = situacaoDe(f.nome);
    return {
      ...f,
      num: f.numero ?? "",
      // o nome é o botão que abre a ficha
      jogador: `<button type="button" class="el-nome" data-sel="${f.jogador_id}">${f.nome}</button> ${selos(f, { acabando: false })}`,
      pos: sigla(posicaoDe(f)),
      pot: f.potencial > f.overall ? `${f.potencial} ↑` : f.potencial,
      situacao: s.chip || (s.energia != null ? `${s.energia}%` : ""),
      contrato: f.contrato_anos <= 1
        ? `<span class="chip chip-perto" title="Contrato acabando">${f.contrato_anos}</span>`
        : f.contrato_anos,
      valor: dinheiro(f.valor_mercado),
    };
  });
  return tabela(linhas, [
    ["num", "Nº"], ["jogador", "Jogador"], ["pos", "Pos."], ["idade", "Idade"],
    ["overall", "OVR"], ["pot", "Pot."], ["situacao", "Energia"], ["contrato", "Temp."],
    ["valor", "Valor"],
  ], (f) => (f.jogador_id === filtro.selecionado ? "sel" : ""));
}

function ficha(f) {
  if (!f) return `<p class="vazio">Escolha um jogador na lista.</p>`;
  const s = situacaoDe(f.nome);
  const venda = mercado.janela_aberta && !f.bloqueio;
  const dispensa = f.dispensa_bloqueada
    ? `<small class="bloqueio">${icone("cadeado")} Dispensar: ${f.dispensa_bloqueada}</small>`
    : "";
  return `<article class="el-ficha">
    <header class="el-ficha-topo">
      ${camisa(mercado.clube_usuario, { numero: f.numero, tamanho: 56 })}
      <div>
        <h3>${f.nome}</h3>
        <small>${f.funcao || f.posicao} · ${f.idade} anos · OVR <b>${f.overall}</b> · POT <b>${f.potencial}</b></small>
        <div class="el-selos">${selos(f)} ${s.chip}</div>
      </div>
    </header>
    <div class="el-acoes">
      <button type="button" data-el="renovar">${icone("contrato")} Renovar</button>
      <button type="button" class="secondary" data-el="lista">
        ${f.a_venda ? "Tirar da lista" : "Pôr na lista de transferências"}</button>
      ${venda
        ? `<button type="button" class="secondary" data-el="ofertas">${icone("troca")} Ver ${f.ofertas} oferta${f.ofertas === 1 ? "" : "s"}</button>`
        : ""}
      <button type="button" class="secondary outline" data-el="dispensar"${f.dispensa_bloqueada ? " disabled" : ""}>
        ${icone("saiu")} Dispensar (${dinheiro(f.rescisao)})</button>
      <button type="button" class="secondary outline" data-el="pagina">Página completa</button>
    </div>
    ${dispensa}
    ${venda ? "" : `<small class="bloqueio">${icone("cadeado")} Vender: ${f.bloqueio || "janela fechada"}</small>`}
    <dl class="el-numeros">
      <div><dt>Jogos</dt><dd>${f.partidas}</dd></div>
      <div><dt>Gols</dt><dd>${f.gols}</dd></div>
      <div><dt>Assist.</dt><dd>${f.assistencias}</dd></div>
      <div><dt>Nota</dt><dd>${f.partidas ? f.nota_media.toFixed(2) : "—"}</dd></div>
    </dl>
    ${barrasAtributos(f.atributos)}
    <h3 class="secao">Contrato</h3>
    <dl class="el-contrato">
      <div><dt>Salário</dt><dd>${dinheiro(f.salario)}/temp.</dd></div>
      <div><dt>Mercado paga</dt><dd class="${f.salario_referencia > f.salario ? "negativo" : ""}">${dinheiro(f.salario_referencia)}</dd></div>
      <div><dt>Restam</dt><dd>${f.contrato_anos} temp.</dd></div>
      <div><dt>Multa</dt><dd>${f.multa_rescisoria ? dinheiro(f.multa_rescisoria) : MULTA_ROTULO.sem}</dd></div>
      <div><dt>Valor</dt><dd>${dinheiro(f.valor_mercado)}</dd></div>
      <div><dt>Fama</dt><dd>${f.fama}/100</dd></div>
    </dl>
    <div id="c-form"></div>
  </article>`;
}

function desenhar() {
  const m = mercado;
  const conta = (v) => m.elenco.filter((f) =>
    !v || (v === "venda" ? f.a_venda : f.posicao === v)).length;
  const abas = FILTROS.map(([v, rotulo]) =>
    `<button type="button" data-setor="${v}" class="${v === filtro.setor ? "ativa" : ""}">` +
    `${rotulo} <small>${conta(v)}</small></button>`).join("");
  const folha = m.elenco.reduce((t, f) => t + f.salario, 0);
  const sel = m.elenco.find((f) => f.jogador_id === filtro.selecionado);

  const box = $("el-central");
  box.innerHTML = `
    <p>${m.elenco.length} jogadores (mín. ${m.elenco_min}, máx. ${m.elenco_max}) ·
      folha ${dinheiro(folha)}/temp. · caixa <strong class="${m.caixa < 0 ? "negativo" : ""}">${dinheiro(m.caixa)}</strong></p>
    <nav class="abas el-abas">${abas}</nav>
    <div class="el-grade">
      <div class="el-lista">${lista()}</div>
      <div class="el-lado">${ficha(sel)}</div>
    </div>`;

  box.querySelectorAll("[data-setor]").forEach((b) =>
    b.addEventListener("click", () => { filtro.setor = b.dataset.setor; desenhar(); })
  );
  box.querySelectorAll("[data-sel]").forEach((b) =>
    b.addEventListener("click", () => {
      filtro.selecionado = Number(b.dataset.sel);
      desenhar();
      // no celular a ficha fica embaixo da lista
      box.querySelector(".el-ficha")?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    })
  );
  if (sel) ligarAcoes(box, sel);
}

function ligarAcoes(box, f) {
  const botao = (acao) => box.querySelector(`[data-el="${acao}"]`);
  botao("renovar").addEventListener("click", () => abrirContrato(f.jogador_id));
  botao("lista").addEventListener("click", () => marcarAVenda(f, !f.a_venda));
  botao("ofertas")?.addEventListener("click", async () => {
    abrirSecaoRodada("mercado");
    await mostrarOfertas(f.jogador_id);
  });
  botao("pagina").addEventListener("click", () => navegarPara(() => abrirJogador(f.jogador_id)));

  // dispensar pede dois cliques, como propor e vender (sem confirm())
  const dispensar = botao("dispensar");
  dispensar.addEventListener("click", () => {
    if (dispensar.dataset.confirmar !== "1") {
      dispensar.dataset.confirmar = "1";
      dispensar.textContent = `Confirmar? Paga ${dinheiro(f.rescisao)}`;
      return;
    }
    dispensarJogador(f);
  });
}

async function marcarAVenda(f, aVenda) {
  const r = await postarMercado(
    `/simulacoes/${estado.simId}/jogadores/${f.jogador_id}/a-venda`, { a_venda: aVenda },
    "Atualizando a lista…", { metodo: "PUT", onde: "r-contrato-msg" }
  );
  if (!r) return;
  $("r-contrato-msg").innerHTML = aVenda
    ? `${icone("ok")} ${r.jogador} está na lista de transferências.`
    : `${icone("ok")} ${r.jogador} saiu da lista de transferências.`;
  await carregarMercado();
}

async function dispensarJogador(f) {
  const r = await postarMercado(
    `/simulacoes/${estado.simId}/jogadores/${f.jogador_id}/dispensa`, {},
    "Rescindindo o contrato…", { onde: "r-contrato-msg" }
  );
  if (!r) return;
  avisoMercado(
    `${icone("saiu")} ${r.jogador} foi dispensado: ${dinheiro(r.rescisao)} de rescisão.`,
    false, "r-contrato-msg"
  );
  filtro.selecionado = null;
  carregarCaixa();
  await carregarProximaRodada();   // elenco e escalação mudaram
}
