// Ponto de entrada: liga os botões do topo e abre a tela inicial.

import { $ } from "./nucleo.js";
import { abrirSimulacao, apagarSelecionada, carregarClubes } from "./saves.js";
import { novaTemporada } from "./escalacao.js";
import { mostrarInicio } from "./inicio.js";
import { carregarIdentidades } from "./identidade.js";
import { preencherIcones } from "./icones.js";
import "./navegacao.js";

// modo dev (seed, simular tudo, lista crua de saves): só com ?dev no endereço
$("dev").hidden = !new URLSearchParams(location.search).has("dev");
$("nova").addEventListener("click", novaTemporada);
$("apagar").addEventListener("click", apagarSelecionada);
$("lista").addEventListener("change", (e) => {
  if (e.target.value) abrirSimulacao(e.target.value);
});
carregarClubes();

preencherIcones();

// escudos e camisas antes da primeira tela (os cards do menu já usam)
await carregarIdentidades();
mostrarInicio();
