// Ponto de entrada: liga os botões do topo e carrega os dados.

import { $ } from "./nucleo.js";
import { abrirSimulacao, apagarSelecionada, carregarClubes, continuarDeOndeParou } from "./saves.js";
import { novaTemporada } from "./escalacao.js";

$("nova").addEventListener("click", novaTemporada);
$("apagar").addEventListener("click", apagarSelecionada);
$("lista").addEventListener("change", (e) => {
  if (e.target.value) abrirSimulacao(e.target.value);
});

carregarClubes();
continuarDeOndeParou();
