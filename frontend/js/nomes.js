// Nomes curtos dos jogadores, onde o espaço é pouco (campo, linha do jogo,
// notas). O normal é o sobrenome ("Lima"); se dois da mesma lista têm o
// mesmo sobrenome, os dois ganham a inicial ("L. Lima" e "R. Lima"); se
// ainda empatar, o nome inteiro.

const PARTICULAS = new Set(["de", "da", "do", "das", "dos", "e"]);
const SUFIXOS = new Set(["júnior", "junior", "jr.", "filho", "neto", "sobrinho"]);

// "Lucas Lima" -> "Lima"; "Eduardo da Silva" -> "da Silva";
// "Jean Paulo Filho" -> "Paulo Filho"; "Jô" -> "Jô"
export function sobrenome(nome) {
  const partes = nome.trim().split(/\s+/);
  if (partes.length === 1) return partes[0];
  let i = partes.length - 1;
  if (SUFIXOS.has(partes[i].toLowerCase()) && i > 1) i -= 1;
  while (i > 1 && PARTICULAS.has(partes[i - 1].toLowerCase())) i -= 1;
  return partes.slice(i).join(" ");
}

// "Lucas Lima" -> "L. Lima"; "Jô" -> "Jô"
export function abreviado(nome) {
  const partes = nome.trim().split(/\s+/);
  if (partes.length === 1) return partes[0];
  return `${partes[0][0]}. ${sobrenome(nome)}`;
}

// a forma curta de cada nome, sem confundir quem está na mesma lista:
// devolve uma função nome -> curto
export function nomesCurtos(nomes) {
  const unicos = [...new Set(nomes.filter(Boolean))];
  const conta = (f) => unicos.reduce((m, n) => m.set(f(n), (m.get(f(n)) || 0) + 1), new Map());
  const porSobrenome = conta(sobrenome);
  const porAbreviado = conta(abreviado);
  const curto = new Map(unicos.map((n) => [n,
    porSobrenome.get(sobrenome(n)) === 1 ? sobrenome(n)
      : porAbreviado.get(abreviado(n)) === 1 ? abreviado(n)
      : n]));
  return (nome) => curto.get(nome) ?? sobrenome(nome);
}
