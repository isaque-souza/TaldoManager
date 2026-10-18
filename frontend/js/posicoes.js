// Posições específicas (v1.3): zagueiro, lateral, volante... O motor pensa
// por setor (`posicao`); a posição de cada um é `funcao`, e fora dela o
// jogador rende menos (o servidor manda o overall em cada posição).

export const SIGLA = {
  Goleiro: "GOL", Zagueiro: "ZAG", Lateral: "LAT", Volante: "VOL",
  "Meia central": "MC", "Meia-atacante": "MEI", Ponta: "PON",
  "Segundo atacante": "SA", Centroavante: "CA",
  Meia: "MC",   // nome antigo do meia central
  // setores, para dados de antes da v1.3
  Defesa: "DEF", "Meio-Campo": "MEI", Atacante: "ATA",
};

// a posição do jogador (a específica; o setor em dados antigos)
export const posicaoDe = (j) => j.funcao || j.posicao;

export const sigla = (pos) => SIGLA[pos] || pos;

export const ehGoleiro = (j) => j.posicao === "Goleiro";

export const SETOR = {
  Goleiro: "Goleiro", Zagueiro: "Defesa", Lateral: "Defesa",
  Volante: "Meio-Campo", "Meia central": "Meio-Campo", "Meia-atacante": "Meio-Campo",
  Ponta: "Atacante", "Segundo atacante": "Atacante", Centroavante: "Atacante",
};

// lugar no campo (desenho da formação, v1.3) → % da tela, com o time
// atacando para cima: x é a largura, y a profundidade (0 = a própria meta)
export const naTela = ({ x, y }) => ({ left: 6 + x * 0.88, top: 92 - y * 0.84 });

// goleiro só troca com goleiro; jogador de linha, com qualquer um de linha
export const podemTrocar = (a, b) => ehGoleiro(a) === ehGoleiro(b);
