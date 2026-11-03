"""Baixa da Wikipédia (inglês, CC BY-SA) os elencos do Brasileirão 2017
(v2.5) para data/fontes/wikipedia/brasileirao-2017/elencos.json.

O elenco de cada clube é o da página do clube como ela estava em
`DATA` (a revisão daquele dia, pela API); o nascimento de cada jogador
vem do Wikidata (P569), pelo artigo ligado no elenco. Só precisa rodar de
novo para atualizar: o arquivo fica no repositório e o importador
(scripts/importar_brasileirao.py) lê do disco.

Uso (a partir da pasta backend/):
    python -m scripts.baixar_brasileirao
"""

import json
import re
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.error import HTTPError
from urllib.request import Request, urlopen

DESTINO = (Path(__file__).resolve().parent.parent
           / "data" / "fontes" / "wikipedia" / "brasileirao-2017")
DATA = "2017-11-15T00:00:00Z"     # a três rodadas do fim, antes das contratações de 2018
API = "https://en.wikipedia.org/w/api.php"
WIKIDATA = "https://www.wikidata.org/w/api.php"
AGENTE = "TaldoManager-dados/1.0 (projeto pessoal; elencos de 2017)"

# na ordem da tabela final de 2017: nome no jogo -> título na Wikipédia
CLUBES = {
    "Corinthians": "Sport Club Corinthians Paulista",
    "Palmeiras": "Sociedade Esportiva Palmeiras",
    "Santos": "Santos FC",
    "Grêmio": "Grêmio Foot-Ball Porto Alegrense",
    "Cruzeiro": "Cruzeiro Esporte Clube",
    "Flamengo": "Clube de Regatas do Flamengo",
    "Vasco": "CR Vasco da Gama",
    "Chapecoense": "Associação Chapecoense de Futebol",
    "Atlético Mineiro": "Clube Atlético Mineiro",
    "Botafogo": "Botafogo de Futebol e Regatas",
    "Atlético Paranaense": "Club Athletico Paranaense",
    "Bahia": "Esporte Clube Bahia",
    "São Paulo": "São Paulo FC",
    "Fluminense": "Fluminense FC",
    "Sport": "Sport Club do Recife",
    "Vitória": "Esporte Clube Vitória",
    "Coritiba": "Coritiba Foot Ball Club",
    "Avaí": "Avaí FC",
    "Ponte Preta": "Associação Atlética Ponte Preta",
    "Atlético Goianiense": "Atlético Clube Goianiense",
}

_JOGADOR = re.compile(r"\{\{\s*Fs player\s*\|(.*?)\}\}\s*$", re.IGNORECASE)
_LINK = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")


def _abrir(url):
    """GET com paciência: a Wikipédia responde 429 a quem pede rápido."""
    for tentativa in range(6):
        try:
            with urlopen(Request(url, headers={"User-Agent": AGENTE}), timeout=30) as resp:
                return resp.read()
        except HTTPError as e:
            if e.code != 429 or tentativa == 5:
                raise
            time.sleep(10 * (tentativa + 1))


def _get(url, params):
    return json.loads(_abrir(f"{url}?{urlencode(params)}"))


def _raw(revid):
    return _abrir(f"https://en.wikipedia.org/w/index.php?oldid={revid}&action=raw").decode("utf-8")


def revisao(titulo):
    dados = _get(API, {
        "action": "query", "prop": "revisions", "titles": titulo, "rvlimit": 1,
        "rvstart": DATA, "rvdir": "older", "rvprop": "ids|timestamp",
        "format": "json", "redirects": 1,
    })
    pagina = next(iter(dados["query"]["pages"].values()))
    rev = pagina["revisions"][0]
    return rev["revid"], rev["timestamp"]


def _campos(corpo):
    campos = {}
    # os | dentro de [[...]] não separam campos
    partes, nivel, atual = [], 0, ""
    for ch in corpo:
        if ch == "[":
            nivel += 1
        elif ch == "]":
            nivel -= 1
        if ch == "|" and nivel == 0:
            partes.append(atual)
            atual = ""
        else:
            atual += ch
    partes.append(atual)
    for p in partes:
        if "=" in p:
            k, v = p.split("=", 1)
            campos[k.strip()] = v.strip()
    return campos


def elenco(texto):
    """Os jogadores do elenco principal: as linhas {{Fs player}} da seção do
    elenco atual, até a próxima seção (emprestados, base...)."""
    linhas = texto.splitlines()
    inicio = next(
        (i for i, l in enumerate(linhas)
         if re.match(r"^=+\s*(Current squad|First[- ]team squad|Players|Squad)\s*=+", l, re.I)),
        None,
    )
    if inicio is None:
        inicio = next(i for i, l in enumerate(linhas) if "Fs start" in l) - 1
    jogadores = []
    for linha in linhas[inicio + 1:]:
        if re.match(r"^=+[^=]", linha) and jogadores:
            break
        m = _JOGADOR.search(linha)
        if not m:
            continue
        c = _campos(m.group(1))
        link = _LINK.search(c.get("name", ""))
        if link:
            artigo, nome = link.group(1), link.group(2) or link.group(1)
        else:
            artigo, nome = None, c.get("name", "")
        nome = re.sub(r"\s*\(.*?\)\s*$", "", nome).strip()
        numero = c.get("no", "")
        jogadores.append({
            "numero": int(numero) if numero.isdigit() else None,
            "nome": nome,
            "artigo": artigo,
            "nacionalidade": c.get("nat", ""),
            "setor": c.get("pos", "").upper(),
            "emprestado": "loan" in c.get("other", "").lower(),
        })
    return jogadores


def nascimentos(artigos):
    """{artigo: "AAAA-MM-DD"} pelo Wikidata, de 50 em 50."""
    artigos = [a for a in dict.fromkeys(artigos) if a]
    item = {}
    for i in range(0, len(artigos), 50):
        lote = artigos[i:i + 50]
        dados = _get(API, {
            "action": "query", "prop": "pageprops", "ppprop": "wikibase_item",
            "titles": "|".join(lote), "format": "json", "redirects": 1,
        })
        # títulos normalizados e redirecionados voltam ao do elenco
        volta = {}
        for chave in ("normalized", "redirects"):
            for r in dados["query"].get(chave, []):
                volta[r["to"]] = volta.get(r["from"], r["from"])
        for p in dados["query"]["pages"].values():
            if "pageprops" in p:
                item[volta.get(p["title"], p["title"])] = p["pageprops"]["wikibase_item"]
        time.sleep(0.5)
    datas = {}
    ids = list(dict.fromkeys(item.values()))
    por_id = {}
    for i in range(0, len(ids), 50):
        dados = _get(WIKIDATA, {
            "action": "wbgetentities", "ids": "|".join(ids[i:i + 50]),
            "props": "claims", "format": "json",
        })
        for qid, ent in dados["entities"].items():
            p569 = ent.get("claims", {}).get("P569")
            if p569:
                valor = p569[0]["mainsnak"].get("datavalue", {}).get("value", {})
                if valor.get("time"):
                    por_id[qid] = valor["time"][1:11]
        time.sleep(0.5)
    for artigo, qid in item.items():
        if qid in por_id:
            datas[artigo] = por_id[qid]
    return datas


def main():
    DESTINO.mkdir(parents=True, exist_ok=True)
    clubes = {}
    for nome, titulo in CLUBES.items():
        revid, quando = revisao(titulo)
        jogadores = elenco(_raw(revid))
        clubes[nome] = {"titulo": titulo, "revisao": revid, "data": quando,
                        "jogadores": jogadores}
        print(f"{nome:22} rev {revid} ({quando[:10]}): {len(jogadores)} jogadores", flush=True)
        time.sleep(2)
    datas = nascimentos([j["artigo"] for c in clubes.values() for j in c["jogadores"]])
    sem = 0
    for c in clubes.values():
        for j in c["jogadores"]:
            j["nascimento"] = datas.get(j["artigo"])
            sem += j["nascimento"] is None
    (DESTINO / "elencos.json").write_text(
        json.dumps({"fonte": "en.wikipedia.org (revisões de 15/11/2017) e Wikidata",
                    "licenca": "CC BY-SA 4.0 (Wikipédia) / CC0 (Wikidata)",
                    "clubes": clubes}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"{sum(len(c['jogadores']) for c in clubes.values())} jogadores, {sem} sem nascimento")


if __name__ == "__main__":
    main()
