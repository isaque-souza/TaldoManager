// Posições específicas (v1.3): zagueiro, lateral, volante... O motor pensa
// por setor (`posicao`); a posição de cada um é `funcao`, e fora dela o
// jogador rende menos (o servidor manda o overall em cada posição).

export const SIGLA = {
  Goleiro: "GOL", Zagueiro: "ZAG", Lateral: "LAT", Volante: "VOL",
  Meia: "MEI", Ponta: "PON", Centroavante: "CA",
  // setores, para dados de antes da v1.3
  Defesa: "DEF", "Meio-Campo": "MEI", Atacante: "ATA",
};

// a posição do jogador (a específica; o setor em dados antigos)
export const posicaoDe = (j) => j.funcao || j.posicao;

export const sigla = (pos) => SIGLA[pos] || pos;

export const ehGoleiro = (j) => j.posicao === "Goleiro";

// goleiro só troca com goleiro; jogador de linha, com qualquer um de linha
export const podemTrocar = (a, b) => ehGoleiro(a) === ehGoleiro(b);
