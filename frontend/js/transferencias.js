// Central de Transferências (v1.7): buscar nas duas ligas (os filtros rodam
// aqui, sobre o mercado inteiro), os observados, as negociações da janela e
// o histórico da carreira. Fora da janela dá para buscar e observar; só a
// proposta trava. As ações (propor, contratar, o contrato, responder às
// ofertas da CPU) ficam em mercado.js; as ofertas aparecem também na ficha do
// jogador, na Central do Elenco.

import { $, estado, navegarPara, pedir } from "./nucleo.js";
import { dinheiro, tabela } from "./tabelas.js";
import {
  acaoCompra, acaoLivre, acoesOferta, detalheOferta, ligarBotoesMercado, postarMercado, STATUS_NEG,
} from "./mercado.js";
import { MULTA_ROTULO } from "./contratos.js";
import { abrirJogador } from "./jogador.js";
import { icone, seloIdolo } from "./icones.js";
import { barrasAtributos, destaques, linhaAtributos } from "./atributos.js";
import { camisa } from "./identidade.js";
import { nomeLiga } from "./ligas.js";
import { posicaoDe, sigla } from "./posicoes.js";

const ABAS = [
  ["buscar", "Buscar"], ["observados", "Observados"],
  ["negociacoes", "Negociações"], ["historico", "Histórico"],
];
const LIMITE_LINHAS = 40;   // linhas da busca (o resto pede filtro)
const SIGLA_LIGA = { taldo: "TAL", premier: "PL" };
const POSICOES = [["", "todas"], ["Goleiro", "Goleiro"], ["Defesa", "Defesa"],
                  ["Meio-Campo", "Meio-campo"], ["Atacante", "Atacante"]];
const IDADES = [["", "todas"], ["jovem", "até 21"], ["auge", "22 a 29"], ["veterano", "30 ou mais"]];
const NOTAS = [["", "qualquer"], ...[60, 65, 70, 75, 80, 85].map((n) => [String(n), `${n}+`])];
const TETOS = [["", "qualquer"], ["1000000", "até 1 mi"], ["5000000", "até 5 mi"],
               ["10000000", "até 10 mi"], ["20000000", "até 20 mi"], ["50000000", "até 50 mi"]];
const TIPO_MOV = {
  compra: ["chip-perto", "Compra"], venda: ["chip-batida", "Venda"],
  livre: ["", "Livre"], dispensa: ["chip-longe", "Dispensa"],
};

const tela = { aba: "buscar", selecionado: null, temporada: "" };   // selecionado: o nome
const busca = {
  origem: "clubes", liga: "", clube: "", posicao: "", idade: "", ovr: "", pot: "", valor: "",
};
let mercado = null;      // o último GET /mercado
let observados = null;   // o último GET /observados
let historico = null;    // GET /historico-transferencias, pedido ao abrir a aba

export function renderTransferencias(m, obs) {
  mercado = m;
  observados = obs || { limite: 25, observados: [] };
  historico = null;   // pode ter mudado (compra, venda, dispensa...)
  fecharContratoVencido(m);
  desenhar();
}

// o formulário do contrato (#m-negociacao) fica fora das abas; some quando
// a negociação dele não está mais aberta (assinou, desistiu, expirou)
function fecharContratoVencido(m) {
  const box = $("m-negociacao");
  const neg = Number(box.dataset.neg);
  if (neg && !m.negociacoes.some((n) => n.negociacao_id === neg && n.status === "aberta")) {
    box.innerHTML = "";
    delete box.dataset.neg;
  }
}

// ---------- pedaços comuns ----------

const passaIdade = (idade) =>
  !busca.idade ||
  (busca.idade === "jovem" ? idade <= 21 : busca.idade === "auge" ? idade >= 22 && idade <= 29 : idade >= 30);

function candidatos() {
  const livres = busca.origem === "livres";
  return (livres ? mercado.livres : mercado.disponiveis).filter((f) =>
    (livres || !busca.liga || f.liga === busca.liga) &&
    (livres || !busca.clube || f.clube === busca.clube) &&
    (!busca.posicao || f.posicao === busca.posicao) &&
    passaIdade(f.idade) &&
    (!busca.ovr || f.overall >= Number(busca.ovr)) &&
    (!busca.pot || f.potencial >= Number(busca.pot)) &&
    (!busca.valor || f.valor_mercado <= Number(busca.valor)));
}

// a ficha de compra pelo nome: na lista de compra, nos livres ou nos observados
function fichaDe(nome) {
  return mercado.disponiveis.find((f) => f.nome === nome) ||
    mercado.livres.find((f) => f.nome === nome) ||
    observados.observados.find((o) => o.nome === nome)?.jogador || null;
}

function estrela(f) {
  const rotulo = f.observado ? "Deixar de observar" : "Observar";
  return `<button type="button" class="tr-estrela${f.observado ? " ligada" : ""}" data-obs="${f.nome}" ` +
    `data-obs-on="${f.observado ? 0 : 1}" title="${rotulo}" aria-label="${rotulo} ${f.nome}" ` +
    `aria-pressed="${f.observado}">${icone("estrela")}</button>`;
}

const nomeBotao = (f) =>
  `<button type="button" class="el-nome" data-sel="${f.nome}">${f.nome}</button>` +
  (f.idolo ? ` ${seloIdolo()}` : "");

const clubeFmt = (f) => f.clube
  ? `${f.rival ? `${icone("rival", "rival")} ` : ""}${f.clube}`
  : "sem clube";

const potFmt = (f) =>
  f.potencial > f.overall ? `<span class="sobe" title="ainda cresce">${f.potencial}</span>` : f.potencial;

// a diferença desde que entrou na lista: +3, −1,2 mi...
function variacao(atual, antes, fmt = (v) => v) {
  const d = atual - antes;
  if (!d) return "";
  return ` <small class="${d > 0 ? "sobe" : "negativo"}">${d > 0 ? "+" : "−"}${fmt(Math.abs(d))}</small>`;
}

// ---------- a ficha (buscar e observados) ----------

function ficha(f, o = null) {
  if (o && !f) {
    return `<article class="el-ficha"><h3>${o.nome}</h3>
      <p class="vazio">${o.avisos.join(" · ")}. Estava no ${o.clube_inicial || "mercado de livres"}
        com OVR ${o.overall_inicial}.</p>
      <button type="button" class="secondary outline" data-obs="${o.nome}" data-obs-on="0">Tirar da lista</button>
    </article>`;
  }
  if (!f) return `<p class="vazio">Escolha um jogador na lista.</p>`;
  const livre = !f.clube;
  const proposta = f.clube === mercado.clube_usuario ? "" : livre ? acaoLivre(f) : acaoCompra(f);
  const desde = o
    ? `<p class="tr-desde">${icone("estrela")} Observado desde a ${o.desde_temporada}ª temporada, ` +
      `${o.desde_rodada === 1 ? "pré-temporada" : `rodada ${o.desde_rodada}`}: OVR ${o.overall_inicial} → ` +
      `<b>${f.overall}</b>, valor ${dinheiro(o.valor_inicial)} → <b>${dinheiro(f.valor_mercado)}</b>` +
      `${o.avisos.length ? ` · ${o.avisos.join(" · ")}` : ""}</p>`
    : "";
  return `<article class="el-ficha">
    <header class="el-ficha-topo">
      ${livre ? `<span class="tr-sem-clube">${icone("assinou")}</span>` : camisa(f.clube, { numero: f.numero, tamanho: 56 })}
      <div>
        <h3>${f.nome}</h3>
        <small>${f.funcao || f.posicao} · ${f.idade} anos · OVR <b>${f.overall}</b> · POT <b>${f.potencial}</b></small>
        <small class="tr-clube">${livre ? "Sem clube" : `${clubeFmt(f)} · ${nomeLiga(f.liga)}`}</small>
        <div class="el-selos">${f.idolo ? seloIdolo() : ""}${f.observado ? ` <span class="chip">Observado</span>` : ""}</div>
      </div>
    </header>
    ${desde}
    <div class="el-acoes">
      <button type="button" class="secondary" data-obs="${f.nome}" data-obs-on="${f.observado ? 0 : 1}">
        ${icone("estrela")} ${f.observado ? "Deixar de observar" : "Observar"}</button>
      ${f.jogador_id ? `<button type="button" class="secondary outline" data-pagina="${f.jogador_id}">Página completa</button>` : ""}
    </div>
    <div class="tr-compra">${proposta}</div>
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
      <div><dt>Mercado paga</dt><dd>${dinheiro(f.salario_referencia)}</dd></div>
      <div><dt>Restam</dt><dd>${livre ? "—" : `${f.contrato_anos} temp.`}</dd></div>
      <div><dt>Multa</dt><dd>${f.multa_rescisoria ? dinheiro(f.multa_rescisoria) : MULTA_ROTULO.sem}</dd></div>
      <div><dt>Valor</dt><dd>${dinheiro(f.valor_mercado)}</dd></div>
      <div>${livre ? `<dt>Luvas</dt><dd>${dinheiro(f.luvas)}</dd>` : `<dt>Fama</dt><dd>${f.fama}/100</dd>`}</div>
    </dl>
  </article>`;
}

// ---------- abas ----------

function opcoes(lista, atual) {
  return lista.map(([v, r]) => `<option value="${v}"${v === atual ? " selected" : ""}>${r}</option>`).join("");
}

function abaBuscar() {
  const m = mercado;
  const livres = busca.origem === "livres";
  const ligas = [...new Set(m.disponiveis.map((f) => f.liga))];
  const clubes = [...new Set(m.disponiveis.filter((f) => !busca.liga || f.liga === busca.liga).map((f) => f.clube))]
    .sort((a, b) => a.localeCompare(b, "pt-BR"));
  const filtro = (campo, rotulo, lista) =>
    `<label>${rotulo} <select data-busca="${campo}">${opcoes(lista, busca[campo])}</select></label>`;

  const lista = candidatos();
  if (!lista.some((f) => f.nome === tela.selecionado)) tela.selecionado = lista[0]?.nome ?? null;
  const linhas = lista.slice(0, LIMITE_LINHAS).map((f) => ({
    ...f,
    obs: estrela(f),
    jogador: nomeBotao(f),
    clube_fmt: clubeFmt(f),
    liga_fmt: `<span title="${nomeLiga(f.liga)}">${SIGLA_LIGA[f.liga] || f.liga}</span>`,
    pos: sigla(posicaoDe(f)),
    destaques: `<span title="${linhaAtributos(f.atributos)}">${destaques(f.atributos)}</span>`,
    pot: potFmt(f),
    valor: dinheiro(f.valor_mercado),
    multa: f.multa_rescisoria ? dinheiro(f.multa_rescisoria) : "—",
    luvas_fmt: dinheiro(f.luvas),
  }));
  const colunas = livres
    ? [["obs", ""], ["jogador", "Jogador"], ["pos", "Pos."], ["idade", "Idade"], ["overall", "OVR"],
       ["pot", "Pot."], ["destaques", "Destaques"], ["valor", "Valor"], ["luvas_fmt", "Luvas"]]
    : [["obs", ""], ["jogador", "Jogador"], ["clube_fmt", "Clube"], ["liga_fmt", "Liga"], ["pos", "Pos."],
       ["idade", "Idade"], ["overall", "OVR"], ["pot", "Pot."], ["valor", "Valor"], ["multa", "Multa"]];

  const explica = !m.janela_aberta ? "" : livres
    ? `<p class="vazio">Jogadores <strong>sem clube</strong>: não há transferência. O clube paga só as
      <strong>luvas</strong> (um bônus de assinatura) e acerta o contrato com o jogador.</p>`
    : `<p class="vazio">Contratar tem duas etapas. <strong>1.</strong> Proposta ao clube: ele aceita, pede mais
      (contraproposta) ou recusa — até ${m.max_propostas} propostas por jogador em cada janela; cobrindo a
      <strong>multa rescisória</strong>, o clube não pode recusar, e do rival (${icone("rival")}) tudo sai mais caro.
      <strong>2.</strong> Contrato com o jogador (salário, anos, multa e papel), antes de jogar a rodada.</p>`;

  return `<div class="mercado-filtros">
      ${filtro("origem", "Jogadores", [["clubes", "de outros clubes"], ["livres", `sem clube (${m.livres.length})`]])}
      ${!livres && ligas.length > 1 ? filtro("liga", "Liga", [["", "as duas"], ...ligas.map((l) => [l, nomeLiga(l)])]) : ""}
      ${livres ? "" : filtro("clube", "Clube", [["", "todos"], ...clubes.map((c) => [c, c])])}
      ${filtro("posicao", "Posição", POSICOES)}
      ${filtro("idade", "Idade", IDADES)}
      ${filtro("ovr", "OVR mín.", NOTAS)}
      ${filtro("pot", "Pot. mín.", NOTAS)}
      ${filtro("valor", "Valor", TETOS)}
    </div>
    ${explica}
    <div class="el-grade">
      <div class="el-lista">
        ${tabela(linhas, colunas, (f) => (f.nome === tela.selecionado ? "sel" : ""))}
        ${lista.length > LIMITE_LINHAS
          ? `<p class="vazio">Mostrando os ${LIMITE_LINHAS} melhores de ${lista.length} — use os filtros.</p>`
          : ""}
      </div>
      <div class="el-lado">${ficha(fichaDe(tela.selecionado))}</div>
    </div>`;
}

function abaObservados() {
  const lista = observados.observados;
  if (!lista.length) {
    return `<p class="vazio">Ninguém na lista. Na aba Buscar, toque na estrela ${icone("estrela")} ao lado do
      jogador para acompanhar o overall, o valor e o clube dele (a lista segue de uma temporada para a outra).</p>`;
  }
  if (!lista.some((o) => o.nome === tela.selecionado)) tela.selecionado = lista[0].nome;
  const SITUACAO = { livre: "sem clube", no_elenco: "seu elenco", aposentado: "—" };
  const linhas = lista.map((o) => {
    const f = o.jogador;
    return {
      ...o,
      obs: estrela({ nome: o.nome, observado: true }),
      jogador_fmt: `<button type="button" class="el-nome" data-sel="${o.nome}">${o.nome}</button>` +
        o.avisos.map((a) => ` <span class="chip ${a === "Aposentou" ? "chip-longe" : "chip-perto"}">${a}</span>`).join(""),
      onde: o.situacao === "clube"
        ? `${clubeFmt(f)} <small title="${nomeLiga(f.liga)}">${SIGLA_LIGA[f.liga] || f.liga}</small>`
        : SITUACAO[o.situacao],
      pos: f ? sigla(posicaoDe(f)) : "",
      idade: f ? f.idade : "",
      ovr: f ? `${f.overall}${variacao(f.overall, o.overall_inicial)}` : o.overall_inicial,
      valor: f ? `${dinheiro(f.valor_mercado)}${variacao(f.valor_mercado, o.valor_inicial, dinheiro)}` : "—",
      desde: `${o.desde_temporada}ª temp. · ${o.desde_rodada === 1 ? "pré" : `R${o.desde_rodada}`}`,
    };
  });
  const sel = lista.find((o) => o.nome === tela.selecionado);
  return `<p>${lista.length} de ${observados.limite} na lista · a diferença ao lado do OVR e do valor é desde que
      ele entrou nela.</p>
    <div class="el-grade">
      <div class="el-lista">${tabela(linhas, [
        ["obs", ""], ["jogador_fmt", "Jogador"], ["onde", "Onde está"], ["pos", "Pos."], ["idade", "Idade"],
        ["ovr", "OVR"], ["valor", "Valor"], ["desde", "Desde"],
      ], (o) => (o.nome === tela.selecionado ? "sel" : ""))}</div>
      <div class="el-lado">${ficha(sel.jogador, sel)}</div>
    </div>`;
}

// propostas ao clube que ainda pedem uma decisão (contraproposta) ou que já
// esgotaram, e os contratos com o jogador
function pendentes(m) {
  const propostas = m.disponiveis.filter((f) =>
    f.propostas_restantes < m.max_propostas && !f.negociacao);
  const contratos = m.negociacoes.filter((n) => n.status === "aberta").length;
  const ofertas = (m.ofertas_recebidas || []).filter((o) => o.status === "aberta");
  return {
    propostas, ofertas,
    alerta: contratos + ofertas.length + propostas.filter((f) => f.contraproposta).length,
  };
}

function abaNegociacoes() {
  const m = mercado;
  if (!m.janela_aberta) {
    const prox = m.janelas.find((r) => r > m.rodada);
    return `<p class="vazio">${icone("cadeado")} Janela fechada: as negociações voltam
      ${prox ? `antes da rodada ${prox}` : "na próxima temporada"}. Até lá, busque e observe.</p>`;
  }
  const { propostas } = pendentes(m);
  const STATUS_OFERTA = {
    aberta: ["chip-perto", "Esperando você"], aceita: ["chip-batida", "Vendido"],
    recusada: ["", "Recusada"], retirada: ["chip-longe", "Retirada"], expirada: ["", "Expirou"],
  };
  // as ofertas da CPU pelos seus jogadores (v1.7): as abertas primeiro
  const ofertas = [...m.ofertas_recebidas].sort((a, b) =>
    (a.status === "aberta" ? 0 : 1) - (b.status === "aberta" ? 0 : 1));
  let html = `<h3 class="secao">Ofertas pelos seus jogadores</h3>`;
  html += ofertas.length
    ? tabela(ofertas.map((o) => ({
      jogador: o.jogador + (o.espontanea ? ` <span class="chip chip-perto" title="Ele não estava à venda">Assédio</span>` : ""),
      clube_fmt: `${o.rival ? `${icone("rival", "rival")} ` : ""}${o.clube}`,
      valor_fmt: `${dinheiro(o.valor)}${o.pedido ? ` <small class="bloqueio">pedimos ${dinheiro(o.pedido)}</small>` : ""}`,
      detalhe: `<small>${detalheOferta(o)}</small>`,
      situacao: `<span class="chip ${STATUS_OFERTA[o.status][0]}">${STATUS_OFERTA[o.status][1]}</span>`,
      acao: o.status === "aberta" ? acoesOferta(o) : "",
    })), [["jogador", "Jogador"], ["clube_fmt", "Clube"], ["valor_fmt", "Oferta"], ["detalhe", ""],
          ["situacao", "Situação"], ["acao", ""]])
    : `<p class="vazio">Nenhuma oferta nesta janela. Ponha jogadores na lista de transferências (na Central
      do Elenco) e os clubes olham na hora.</p>`;

  html += `<h3 class="secao">Propostas aos clubes</h3>`;
  html += propostas.length
    ? tabela(propostas.map((f) => ({
      jogador: f.nome,
      clube_fmt: clubeFmt(f),
      feitas: `${m.max_propostas - f.propostas_restantes} de ${m.max_propostas}`,
      situacao: f.contraproposta
        ? `<span class="chip chip-perto">Pede ${dinheiro(f.contraproposta)}</span>`
        : `<span class="chip chip-longe">Recusada</span>`,
      acao: acaoCompra(f),
    })), [["jogador", "Jogador"], ["clube_fmt", "Clube"], ["feitas", "Propostas"],
          ["situacao", "Resposta"], ["acao", ""]])
    : `<p class="vazio">Nenhuma proposta recusada ou com contraproposta nesta janela.</p>`;

  html += `<h3 class="secao">Contratos com o jogador</h3>`;
  html += m.negociacoes.length
    ? tabela(m.negociacoes.map((n) => ({
      jogador: n.jogador,
      de: n.clube || "sem clube",
      valor_fmt: n.clube ? dinheiro(n.valor) : `${dinheiro(n.valor)} (luvas)`,
      status_fmt: `<span class="chip ${STATUS_NEG[n.status][0]}">${STATUS_NEG[n.status][1]}</span>`,
      acao: n.status === "aberta"
        ? `<button class="transf" data-acao="negociacao" data-neg="${n.negociacao_id}">Acertar contrato</button> ` +
          `<small class="bloqueio">${n.tentativas_restantes} tentativa${n.tentativas_restantes === 1 ? "" : "s"}</small>`
        : "",
    })), [["jogador", "Jogador"], ["de", "De"], ["valor_fmt", "Valor acertado"],
          ["status_fmt", "Situação"], ["acao", ""]])
    : `<p class="vazio">Quando um clube aceita a proposta (ou um livre topa conversar), o contrato aparece
      aqui. O acordo cai se a rodada for jogada sem ele assinar.</p>`;
  return html;
}

function abaHistorico() {
  if (!historico) {
    carregarHistorico();
    return `<p class="vazio">Carregando o histórico…</p>`;
  }
  const h = historico;
  if (!h.movimentos.length) {
    return `<p class="vazio">Nenhuma movimentação ainda: compras, vendas, livres contratados e dispensas
      aparecem aqui, temporada a temporada.</p>`;
  }
  const varias = h.temporadas.length > 1;
  const t = tela.temporada && h.temporadas.find((x) => String(x.temporada) === tela.temporada);
  const resumo = t || h.total;
  const movs = h.movimentos.filter((mv) => !t || mv.temporada === t.temporada);
  const sinal = (mv) => (mv.tipo === "venda" ? "+" : "−");
  const linhas = movs.map((mv) => ({
    quando: `${varias ? `${mv.temporada}ª · ` : ""}${mv.rodada === 1 ? "pré-temporada" : `antes da R${mv.rodada}`}`,
    tipo_fmt: `<span class="chip ${TIPO_MOV[mv.tipo][0]}">${TIPO_MOV[mv.tipo][1]}</span>`,
    jogador: mv.jogador,
    posicao: mv.posicao,
    de: mv.de_clube || "sem clube",
    para: mv.para_clube || "dispensado",
    valor_fmt: `<span class="${mv.tipo === "venda" ? "sobe" : ""}">${sinal(mv)}${dinheiro(mv.valor)}</span>`,
  }));
  const temporadas = [["", "a carreira toda"], ...h.temporadas.map((x) => [String(x.temporada), `${x.temporada}ª temporada`])];
  return `${varias
      ? `<div class="mercado-filtros"><label>Mostrar <select data-temporada>${opcoes(temporadas, tela.temporada)}</select></label></div>`
      : ""}
    <dl class="tr-resumo">
      <div><dt>Gasto</dt><dd>${dinheiro(resumo.gasto)}</dd></div>
      <div><dt>Arrecadado</dt><dd>${dinheiro(resumo.arrecadado)}</dd></div>
      <div><dt>Saldo</dt><dd class="${resumo.saldo < 0 ? "negativo" : "sobe"}">${resumo.saldo < 0 ? "−" : "+"}${dinheiro(Math.abs(resumo.saldo))}</dd></div>
    </dl>
    <small class="bloqueio">Gasto = compras, luvas dos livres e rescisões; arrecadado = vendas.</small>
    ${tabela(linhas, [
      ["quando", "Quando"], ["tipo_fmt", "Tipo"], ["jogador", "Jogador"], ["posicao", "Pos."],
      ["de", "De"], ["para", "Para"], ["valor_fmt", "Valor"],
    ])}`;
}

async function carregarHistorico() {
  const h = await pedir(`/simulacoes/${estado.simId}/historico-transferencias`);
  if (!h) return;
  historico = h;
  if (tela.aba === "historico") desenhar();
}

// ---------- desenho e eventos ----------

function desenhar() {
  const m = mercado;
  const prox = m.janelas.find((r) => r > m.rodada);
  const status = m.janela_aberta
    ? `<span class="luz-aberta"></span> Janela aberta`
    : `${icone("cadeado")} Janela fechada — ${prox ? `reabre antes da rodada ${prox}` : "só na próxima temporada"}`;
  const rivais = m.rivais.length ? ` · ${icone("rival")} rival: ${m.rivais.join(", ")}` : "";
  const alerta = pendentes(m).alerta;
  const conta = {
    observados: `${observados.observados.length}`,
    negociacoes: alerta ? `<span class="chip chip-perto">${alerta}</span>` : "",
  };
  const abas = ABAS.map(([v, rotulo]) =>
    `<button type="button" data-aba="${v}" class="${v === tela.aba ? "ativa" : ""}">` +
    `${rotulo}${conta[v] ? ` <small>${conta[v]}</small>` : ""}</button>`).join("");
  const corpo = { buscar: abaBuscar, observados: abaObservados,
                  negociacoes: abaNegociacoes, historico: abaHistorico }[tela.aba]();

  const box = $("r-mercado");
  box.innerHTML = `
    <p>${status} · caixa <strong class="${m.caixa < 0 ? "negativo" : ""}">${dinheiro(m.caixa)}</strong> ·
      elenco ${m.elenco.length} (mín. ${m.elenco_min}, máx. ${m.elenco_max})${rivais}</p>
    <nav class="abas el-abas">${abas}</nav>
    ${corpo}`;
  ligar(box);
}

function ligar(box) {
  box.querySelectorAll("[data-aba]").forEach((b) =>
    b.addEventListener("click", () => { tela.aba = b.dataset.aba; desenhar(); })
  );
  box.querySelectorAll("[data-busca]").forEach((s) =>
    s.addEventListener("change", () => {
      busca[s.dataset.busca] = s.value;
      if (s.dataset.busca === "liga") busca.clube = "";   // o clube pode ser da outra liga
      desenhar();
    })
  );
  box.querySelector("[data-temporada]")?.addEventListener("change", (e) => {
    tela.temporada = e.target.value;
    desenhar();
  });
  box.querySelectorAll("[data-sel]").forEach((b) =>
    b.addEventListener("click", () => {
      tela.selecionado = b.dataset.sel;
      desenhar();
      // no celular a ficha fica embaixo da lista
      $("r-mercado").querySelector(".el-ficha")?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    })
  );
  box.querySelectorAll("[data-obs]").forEach((b) =>
    b.addEventListener("click", () => observar(b.dataset.obs, b.dataset.obsOn === "1"))
  );
  box.querySelectorAll("[data-pagina]").forEach((b) =>
    b.addEventListener("click", () => navegarPara(() => abrirJogador(Number(b.dataset.pagina))))
  );
  ligarBotoesMercado(box);
}

// observar não mexe no mercado: só a lista de observados volta do servidor
async function observar(nome, entrar) {
  const r = await postarMercado(
    `/simulacoes/${estado.simId}/observados`, { nome, observar: entrar },
    entrar ? "Pondo na lista…" : "Tirando da lista…", { metodo: "PUT" }
  );
  if (!r) return;
  for (const f of [...mercado.disponiveis, ...mercado.livres]) {
    if (f.nome === nome) f.observado = r.observado;
  }
  const obs = await pedir(`/simulacoes/${estado.simId}/observados`);
  if (obs) observados = obs;
  // sem o link da caixa de entrada: observar não gera mensagem
  const aviso = $("r-mercado-msg");
  aviso.classList.remove("ruim");
  aviso.innerHTML = r.observado
    ? `${icone("estrela")} ${nome} está nos observados (${r.total} de ${r.limite}).`
    : `${icone("ok")} ${nome} saiu dos observados.`;
  desenhar();
}
