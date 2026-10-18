// Atributos do jogador (v1.3), como os seis do FIFA/EA FC: Velocidade,
// Finalização, Passe, Drible, Marcação e Físico; goleiro tem Reflexos e
// Posicionamento. Vêm prontos do servidor (overall + perfil da posição +
// estilo do jogador).

export const NOME = {
  velocidade: "Velocidade", finalizacao: "Finalização", passe: "Passe",
  drible: "Drible", marcacao: "Marcação", fisico: "Físico",
  reflexos: "Reflexos", posicionamento: "Posicionamento",
};

export const SIGLA = {
  velocidade: "VEL", finalizacao: "FIN", passe: "PAS", drible: "DRI",
  marcacao: "MAR", fisico: "FIS", reflexos: "REF", posicionamento: "POS",
};

// faixa de cor como no FIFA: verde forte, verde, âmbar, vermelho
const faixa = (v) => (v >= 85 ? "otimo" : v >= 75 ? "bom" : v >= 65 ? "medio" : "fraco");

// "VEL 91 · DRI 88": os dois melhores, para listas (mercado)
export function destaques(atributos, quantos = 2) {
  return Object.entries(atributos || {})
    .sort((a, b) => b[1] - a[1])
    .slice(0, quantos)
    .map(([a, v]) => `${SIGLA[a]} ${v}`)
    .join(" · ");
}

// "VEL 91 · FIN 80 · ..." completo, para dicas (title)
export function linhaAtributos(atributos) {
  return Object.entries(atributos || {}).map(([a, v]) => `${SIGLA[a]} ${v}`).join(" · ");
}

// barras da ficha do jogador
export function barrasAtributos(atributos) {
  const linhas = Object.entries(atributos || {}).map(([a, v]) => `
    <li class="atr ${faixa(v)}">
      <span class="atr-nome"><b>${SIGLA[a]}</b> ${NOME[a]}</span>
      <span class="atr-barra" aria-hidden="true"><i style="width:${v}%"></i></span>
      <b class="atr-valor">${v}</b>
    </li>`).join("");
  return linhas ? `<ul class="atributos" aria-label="Atributos">${linhas}</ul>` : "";
}
