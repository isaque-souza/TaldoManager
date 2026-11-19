"""Nome de exibição na saída da API (v2.7, identidade do jogador).

Nos mundos da API o jogador é identificado pela chave "apif:<id>" — é ela
que o jogo inteiro usa (snapshot, escalação, mercado, mensagens gravadas).
O técnico nunca a vê: este middleware troca a chave pelo nome na resposta,
num lugar só, a partir dos nomes do mundo do save (imutável):

- campo cujo valor é uma chave: vira o nome, e a chave vai ao lado —
  `"nome"` ganha `"chave"`; qualquer outro campo `X` ganha `"X_chave"`;
- lista de chaves (um XI): vira a lista de nomes e ganha `"X_chaves"`;
- texto com chave dentro (mensagem, erro, narração): a chave vira o nome.

O frontend mostra `nome` e devolve a `chave` (sem ela, o próprio `nome` — o
v1, em que chave e nome são iguais). Resposta sem "apif:" — todo o v1 — sai
byte a byte igual.
"""

import json
import re

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from scripts import mundos

CHAVE = re.compile(r"apif:\d+")
_SAVE = re.compile(r"^/simulacoes/(\d+)")
_CARREIRA = re.compile(r"^/carreiras/(\d+)")


def chave_de(campo):
    return "chave" if campo == "nome" else f"{campo}_chave"


def para_exibicao(dado, nomes):
    """`dado` (já decodificado do JSON) com as chaves trocadas pelos nomes."""
    if isinstance(dado, dict):
        saida = {}
        for campo, valor in dado.items():
            if isinstance(valor, str) and valor in nomes:
                saida[campo] = nomes[valor]
                saida[chave_de(campo)] = valor
            elif (isinstance(valor, list) and valor
                  and all(isinstance(v, str) or v is None for v in valor)
                  and any(v in nomes for v in valor)):
                saida[campo] = [nomes.get(v, v) if v else v for v in valor]
                saida[f"{campo}_chaves"] = valor
            else:
                saida[campo] = para_exibicao(valor, nomes)
        return saida
    if isinstance(dado, list):
        return [para_exibicao(v, nomes) for v in dado]
    if isinstance(dado, str) and "apif:" in dado:
        return CHAVE.sub(lambda m: nomes.get(m.group(0), m.group(0)), dado)
    return dado


def _mundo_da_requisicao(scope):
    """O mundo cujos nomes valem para a resposta: o do save (ou da carreira)
    no caminho, o `?mundo=` pedido, ou o padrão de jogo novo."""
    from app.db.conexao import conectar
    caminho = scope.get("path", "")
    sql = None
    if m := _SAVE.match(caminho):
        sql, arg = "SELECT mundo FROM simulacao WHERE id = ?", int(m.group(1))
    elif m := _CARREIRA.match(caminho):
        sql = "SELECT mundo FROM simulacao WHERE carreira_id = ? ORDER BY temporada DESC LIMIT 1"
        arg = int(m.group(1))
    if sql:
        conn = conectar()
        try:
            linha = conn.execute(sql, (arg,)).fetchone()
        finally:
            conn.close()
        if linha and linha[0]:
            return linha[0]
    consulta = scope.get("query_string", b"").decode("latin-1")
    if m := re.search(r"(?:^|&)mundo=([^&]+)", consulta):
        return m.group(1)
    return mundos.MUNDO_PADRAO


def nomes_para(scope, corpo):
    """{chave: nome} das chaves que aparecem no corpo: do mundo da
    requisição e, para o que faltar, de qualquer mundo instalado."""
    usadas = set(CHAVE.findall(corpo))
    try:
        nomes = {k: v for k, v in mundos.exibicoes(_mundo_da_requisicao(scope)).items()
                 if k in usadas}
    except mundos.MundoIndisponivel:
        nomes = {}
    for mundo in reversed(mundos.ids()):
        if usadas <= set(nomes):
            break
        try:
            de_la = mundos.exibicoes(mundo)
        except mundos.MundoIndisponivel:
            continue
        nomes.update({k: de_la[k] for k in usadas - set(nomes) if k in de_la})
    return nomes


class ExibicaoMiddleware:
    """ASGI puro: só bufferiza respostas JSON; as outras passam direto."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        inicio = None
        partes = []
        json_resposta = False

        async def enviar(mensagem: Message):
            nonlocal inicio, json_resposta
            if mensagem["type"] == "http.response.start":
                tipo = dict(mensagem.get("headers", [])).get(b"content-type", b"")
                json_resposta = tipo.startswith(b"application/json")
                if not json_resposta:
                    await send(mensagem)
                    return
                inicio = mensagem
                return
            if not json_resposta:
                await send(mensagem)
                return
            partes.append(mensagem.get("body", b""))
            if mensagem.get("more_body"):
                return
            corpo = b"".join(partes)
            if b"apif:" in corpo:
                texto = corpo.decode("utf-8")
                novo = para_exibicao(json.loads(texto), nomes_para(scope, texto))
                corpo = json.dumps(novo, ensure_ascii=False).encode("utf-8")
            headers = [(k, v) for k, v in inicio.get("headers", []) if k != b"content-length"]
            headers.append((b"content-length", str(len(corpo)).encode()))
            await send({**inicio, "headers": headers})
            await send({"type": "http.response.body", "body": corpo})

        await self.app(scope, receive, enviar)
