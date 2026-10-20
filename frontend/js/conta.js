// Conta (v2.1): entrar / criar conta. O login vive num cookie HttpOnly que
// o navegador manda sozinho em todo fetch; aqui só cuidamos da tela.

import { $, esconderTudo } from "./nucleo.js";

let modo = "entrar";      // "entrar" | "registrar"
let aoEntrar = null;      // o que fazer depois de entrar (abrir o menu)

// sessão vencida no meio do jogo: qualquer 401 da API volta para o login
const fetchOriginal = window.fetch.bind(window);
window.fetch = async (...args) => {
  const resp = await fetchOriginal(...args);
  const url = String(args[0]?.url ?? args[0]);
  if (resp.status === 401 && !url.includes("/conta/")) pedirLogin();
  return resp;
};

export async function quemSou() {
  const resp = await fetchOriginal("/conta/eu");
  return resp.ok ? resp.json() : null;   // null = ninguém logado
}

export function iniciarConta(depois) {
  aoEntrar = depois;
  $("conta-abas").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-conta]");
    if (b) trocarModo(b.dataset.conta);
  });
  $("conta-form").addEventListener("submit", enviar);
  $("sair").addEventListener("click", sair);
}

export function mostrarUsuario(usuario) {
  $("usuario").hidden = !usuario;
  $("usuario-nome").textContent = usuario ? usuario.nome : "";
}

export function pedirLogin() {
  if (!$("conta").hidden) return;
  mostrarUsuario(null);
  document.body.classList.remove("com-lateral");
  $("lateral").hidden = true;
  esconderTudo();
  $("menu").hidden = true;
  $("abrir-lateral").hidden = true;
  $("conta").hidden = false;
  trocarModo("entrar");
  $("conta-senha").value = "";
  $("conta-nome").focus();
}

function trocarModo(novo) {
  modo = novo;
  document.querySelectorAll("#conta-abas button").forEach((b) =>
    b.classList.toggle("ativa", b.dataset.conta === modo));
  const registrar = modo === "registrar";
  $("conta-enviar").textContent = registrar ? "Criar conta" : "Entrar";
  $("conta-dica").hidden = !registrar;
  $("conta-senha").autocomplete = registrar ? "new-password" : "current-password";
  $("conta-erro").textContent = "";
}

async function enviar(e) {
  e.preventDefault();
  const botao = $("conta-enviar");
  botao.setAttribute("aria-busy", "true");
  botao.disabled = true;
  try {
    const resp = await fetchOriginal(`/conta/${modo}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nome: $("conta-nome").value, senha: $("conta-senha").value }),
    });
    const dados = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      $("conta-erro").textContent = typeof dados.detail === "string"
        ? dados.detail : "Preencha o nome e a senha";
      return;
    }
    $("conta").hidden = true;
    mostrarUsuario(dados);
    aoEntrar?.();
  } catch {
    $("conta-erro").textContent = "Sem conexão com o servidor. Tente de novo.";
  } finally {
    botao.removeAttribute("aria-busy");
    botao.disabled = false;
  }
}

async function sair() {
  await fetchOriginal("/conta/sair", { method: "POST" });
  pedirLogin();
}
