// Página do clube: finanças, jogos e elenco.

import { $, esconderTudo, estado, limparAviso, pedir } from "./nucleo.js";
import { dinheiro, ligarLinks, tabela } from "./tabelas.js";

// ---------- visão clube ----------

export const COLS_JOGOS = [
  ["rodada", "R"], ["adversario", "Adversário"], ["mando", "Local"],
  ["placar", "Placar"], ["resultado", "Res."],
];
export const COLS_ELENCO = [
  ["nome", "Jogador"], ["posicao", "Posição"], ["overall", "OVR"],
  ["partidas", "Jogos"], ["gols", "Gols"], ["assistencias", "Assist."],
  ["nota_media", "Nota"], ["melhor_em_campo", "MVPs"], ["valor", "Valor"],
];

// card de finanças do clube; saves anteriores à v0.7 vêm zerados
export function cardFinancas(cl) {
  if (!cl.dinheiro_inicial) return "";
  const saldo = cl.dinheiro - cl.dinheiro_inicial;
  const linha = (rotulo, v) =>
    `<tr><td>${rotulo}</td><td class="num${v < 0 ? " negativo" : ""}">${dinheiro(v)}</td></tr>`;
  return `
    <article class="financas">
      <header><strong>💰 Finanças da temporada</strong></header>
      <table>
        <tbody>
          ${linha("Caixa inicial", cl.dinheiro_inicial)}
          ${linha("📺 Cota de TV", cl.receita_tv)}
          ${linha("🎟️ Bilheteria", cl.receita_bilheteria)}
          ${linha("🏆 Premiação", cl.receita_premiacao)}
          ${linha("💸 Salários", -cl.despesa_salarios)}
          ${cl.receita_vendas ? linha("🔁 Vendas", cl.receita_vendas) : ""}
          ${cl.despesa_compras ? linha("🔁 Compras", -cl.despesa_compras) : ""}
        </tbody>
        <tfoot>
          ${linha("Caixa atual", cl.dinheiro)}
          ${linha("Saldo da temporada", saldo)}
        </tfoot>
      </table>
    </article>`;
}

export async function abrirClube(clubeId) {
  limparAviso();
  const c = await pedir(`/simulacoes/${estado.simId}/clubes/${clubeId}`);
  if (!c) return;

  estado.clubeAtualId = Number(clubeId);
  esconderTudo();
  $("clube").hidden = false;

  const cl = c.clube;
  $("clube-nome").textContent = cl.nome;
  $("clube-info").textContent =
    `${cl.posicao_final}º lugar · ${cl.pontos} pts · ${cl.vitorias}V ${cl.empates}E ${cl.derrotas}D · ` +
    `${cl.gols_marcados}-${cl.gols_sofridos} (saldo ${cl.saldo_gols})`;
  $("clube-financas").innerHTML = cardFinancas(cl);

  const jogos = c.jogos.map((j) => ({
    ...j,
    mando: j.mando === "casa" ? "Casa" : "Fora",
    placar: `${j.gols_pro} x ${j.gols_contra}`,
  }));
  $("clube-jogos").innerHTML = tabela(jogos, COLS_JOGOS);
  $("clube-elenco").innerHTML = tabela(
    c.elenco.map((j) => ({ ...j, valor: j.valor_mercado ? dinheiro(j.valor_mercado) : "—" })),
    COLS_ELENCO,
  );
  ligarLinks($("clube-jogos"));
  ligarLinks($("clube-elenco"));
}
