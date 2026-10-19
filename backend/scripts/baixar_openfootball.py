"""Baixa do OpenFootball (domínio público, CC0) os arquivos da Premier
League 2023/24 para data/fontes/openfootball/premier-2023-24/ (v1.6).

Só precisa rodar de novo se quiser atualizar os arquivos: eles ficam no
repositório e o importador (scripts/importar_premier.py) lê do disco.

Uso (a partir da pasta backend/):
    python -m scripts.baixar_openfootball
"""

import json
from pathlib import Path
from urllib.request import urlopen

DESTINO = (Path(__file__).resolve().parent.parent
           / "data" / "fontes" / "openfootball" / "premier-2023-24")
REPO = "openfootball/england"
PASTA = "2023-24"
BRUTO = f"https://raw.githubusercontent.com/{REPO}/master/{PASTA}"
API = f"https://api.github.com/repos/{REPO}/contents/{PASTA}/squads"


def _baixar(url):
    with urlopen(url, timeout=30) as resp:
        return resp.read()


def main():
    (DESTINO / "squads").mkdir(parents=True, exist_ok=True)
    elencos = [a["name"] for a in json.loads(_baixar(API)) if a["name"].endswith(".txt")]
    for nome in elencos:
        (DESTINO / "squads" / nome).write_bytes(_baixar(f"{BRUTO}/squads/{nome}"))
    (DESTINO / "1-premierleague.txt").write_bytes(_baixar(f"{BRUTO}/1-premierleague.txt"))
    print(f"{len(elencos)} elencos + 1-premierleague.txt em {DESTINO}")


if __name__ == "__main__":
    main()
