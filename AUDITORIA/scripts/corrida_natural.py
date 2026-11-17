"""Auditoria 01 — corrida natural, sem roteiro e sem ganchos.

Fala HTTP com um uvicorn de verdade (o mesmo comando do Dockerfile) que
roda com um banco TEMPORÁRIO (`TALDO_DB` aponta para /tmp no container).
Nada aqui importa o código do jogo: só a biblioteca padrão.

Uso (dentro do container, com o servidor no ar):
    python corrida_natural.py http://127.0.0.1:8000 /tmp/auditoria.db 10

Mede:
- R1: a mesma rodada (mesma seed) jogada sozinha × jogada enquanto outro
  "técnico" abre a tela da rodada de outro save em laço. Controle: a mesma
  coisa sem o outro técnico.
- R2: dois POST /rodadas no mesmo save soltos juntos (barreira no cliente).
"""

import http.cookiejar
import json
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.request

BASE, DB, TENTATIVAS = sys.argv[1], sys.argv[2], int(sys.argv[3])

jar = http.cookiejar.CookieJar()
abrir = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar)).open


def pedir(metodo, caminho, corpo=None):
    dados = json.dumps(corpo).encode() if corpo is not None else None
    req = urllib.request.Request(
        BASE + caminho, data=dados, method=metodo,
        headers={"Content-Type": "application/json"},
    )
    try:
        with abrir(req, timeout=300) as r:
            txt = r.read()
            return r.status, (json.loads(txt) if txt else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")[:200]


def novo_save(seed, clube):
    st, r = pedir("POST", "/simulacoes", {"modo": "rodada_a_rodada", "seed": seed, "clube": clube})
    assert st == 201, (st, r)
    return r["id"]


def placares(res):
    return [(p["mandante"], p["visitante"], p["gols_mandante"], p["gols_visitante"])
            for p in res["resultados"]]


def apagar(*ids):
    for i in ids:
        pedir("DELETE", f"/simulacoes/{i}")


def rodada_com_vizinho(seed, meu, outro, com_vizinho):
    """Joga a rodada 1 de um save novo; com_vizinho: outro save tem a tela
    da rodada aberta em laço enquanto isso. Devolve os placares."""
    x = novo_save(seed, meu)
    y = novo_save(seed + 1000, outro)
    fim = threading.Event()
    leituras = [0]

    def vizinho():
        while not fim.is_set():
            pedir("GET", f"/simulacoes/{y}/rodadas/proxima")
            leituras[0] += 1

    t = threading.Thread(target=vizinho)
    if com_vizinho:
        t.start()
    st, res = pedir("POST", f"/simulacoes/{x}/rodadas")
    fim.set()
    if com_vizinho:
        t.join()
    apagar(x, y)
    assert st == 200, (st, res)
    return placares(res), leituras[0]


def r1():
    clubes = [c["nome"] for c in pedir("GET", "/clubes")[1]]
    meu, outro = clubes[0], clubes[1]
    saida = []
    for i in range(TENTATIVAS):
        seed = 100 + i
        ref, _ = rodada_com_vizinho(seed, meu, outro, com_vizinho=False)
        controle, _ = rodada_com_vizinho(seed, meu, outro, com_vizinho=False)
        teste, leituras = rodada_com_vizinho(seed, meu, outro, com_vizinho=True)
        saida.append({
            "seed": seed,
            "jogos": len(ref),
            "controle_diferentes": sum(a != b for a, b in zip(ref, controle)),
            "com_vizinho_diferentes": sum(a != b for a, b in zip(ref, teste)),
            "leituras_do_vizinho": leituras,
        })
        print("R1", saida[-1], flush=True)
    return saida


def contar(sid):
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        por_rodada = dict(conn.execute(
            "SELECT rodada, COUNT(*) FROM partida WHERE simulacao_id = ? GROUP BY rodada", (sid,)))
        rodada_atual = conn.execute(
            "SELECT rodada_atual FROM simulacao WHERE id = ?", (sid,)).fetchone()[0]
        return por_rodada, rodada_atual
    finally:
        conn.close()


def r2():
    clube = pedir("GET", "/clubes")[1][0]["nome"]
    saida = []
    for i in range(TENTATIVAS):
        sid = novo_save(200 + i, clube)
        barreira = threading.Barrier(2)
        status = []

        def jogar():
            barreira.wait()
            st, res = pedir("POST", f"/simulacoes/{sid}/rodadas")
            status.append((st, res.get("rodada_jogada") if isinstance(res, dict) else res))

        fios = [threading.Thread(target=jogar) for _ in range(2)]
        for f in fios:
            f.start()
        for f in fios:
            f.join()
        por_rodada, rodada_atual = contar(sid)
        apagar(sid)
        saida.append({"tentativa": i, "respostas": status,
                      "partidas_por_rodada": por_rodada, "rodada_atual": rodada_atual})
        print("R2", saida[-1], flush=True)
    return saida


if __name__ == "__main__":
    for _ in range(60):   # espera o servidor subir
        try:
            if pedir("GET", "/conta/eu")[0] == 200:
                break
        except OSError:
            time.sleep(1)
    st, r = pedir("POST", "/conta/registrar", {"nome": "auditoria", "senha": "auditoria01"})
    assert st == 201, (st, r)
    resultado = {"r1": r1(), "r2": r2()}
    print("JSON", json.dumps(resultado, ensure_ascii=False))
