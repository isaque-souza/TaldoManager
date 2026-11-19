# Identidade do jogador (Fase 2, v2.7) — caminho A

| Mundo | Chave interna (`Jogador.nome`) | Nome exibido |
|---|---|---|
| v1 | João Silva | João Silva |
| mundos da API | apif:12345 | João Silva |
| mundos da API | apif:67890 | João Silva |

- O jogo inteiro continua achando o jogador pelo campo de sempre (`nome`),
  que agora é a **chave**. No v1 a chave é o próprio nome: nenhum save, snapshot
  ou tabela do v1 muda (`exibicao` fica NULL e nem entra no snapshot).
- Nos mundos da API, a seed traz `ref` ("apif:<id>", a chave, determinística e
  independente do nome) e `nome` (só exibição). O `Jogador` ganha `exibicao`
  e a propriedade `nome_exibicao`; a tabela `jogador` ganha a coluna `exibicao`
  (aditiva); o snapshot leva `exibicao` só quando existe.
- Trocar o nome num mundo novo não troca a chave: o histórico do mundo conta
  0 entradas/0 saídas.

## A chave nunca aparece para o técnico

`app/api/exibicao.py` (middleware): toda resposta JSON com "apif:" é
traduzida num lugar só, com os nomes do mundo do save (`mundos.exibicoes`):

- campo com chave → nome, e a chave ao lado (`nome` → `chave`; `X` → `X_chave`);
- lista de chaves (XI) → lista de nomes + `X_chaves`;
- texto (mensagem, erro, narração) → a chave vira o nome.

Resposta sem "apif:" (todo o v1) sai byte a byte igual. As mensagens ficam
gravadas com a chave e são traduzidas na saída — o nome certo mesmo se o
mundo trocar o nome de exibição.

Requisição: o backend recebe a **chave** nos mesmos campos de sempre (XI,
sai/entra, livre, observado, relatório). Um nome de exibição sozinho não acha
ninguém (erro), nunca o "João Silva" errado.

## Testes (`tests/services/test_identidade.py`)

v1 sem chave nem exibição; dois "João Silva"; XI e substituição na
transmissão pela chave (o nome ambíguo é recusado); observado, relatório,
livre e proposta; troca de nome com a mesma chave; virada e snapshot; e o
passeio por todas as telas (GET) do save procurando "apif:" fora dos campos de
chave — também nas mensagens gravadas pelo motor.

## Pendente antes do piloto

- **Frontend**: mandar `j.chave ?? j.nome` onde hoje manda o nome (escalação
  e planos em `editor.js`, substituições em `aovivo.js`, livre/observado/
  relatório em `transferencias.js`/`mercado.js`) e usar a chave nos mapas
  internos por jogador. No v1 nada muda (chave = nome); conferir no navegador
  com um mundo de teste com homônimos.
- O CLI (`scripts/simular.py`) imprime `nome`; só roda o v1.
