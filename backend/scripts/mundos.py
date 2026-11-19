"""Mundos versionados (v2.7): cada save joga para sempre no mundo em que
nasceu.

Um **mundo** é um conjunto congelado de seeds (as ligas, com clubes,
jogadores e livres) descrito por um manifesto em
`data/mundos/<id>/manifesto.json`: id, data, origem e temporada de cada liga,
contagens, o sha256 de cada arquivo e o que mudou em relação ao mundo base.

- O **v1** é o mundo de sempre: as 8 ligas da v2.6, nos lugares de sempre
  (`data/seeds/`). O manifesto dele só descreve esses arquivos.
- Mundos novos têm pasta própria (`data/mundos/<id>/ligas/<liga>/`), com
  cópia das ligas que não mudaram.
- Mundo é **imutável**: o jogo confere os hashes antes de carregar (arquivo
  diferente = erro, nunca carga silenciosa) e a suíte confere todos. Corrigir
  um dado é criar um mundo novo.

O hash ignora o fim de linha (CRLF/LF): o `.gitattributes` deixa CRLF no
Windows e LF no Linux, e o mesmo mundo tem de ter o mesmo hash nos dois.

Uso (a partir da pasta backend/):
    python -m scripts.mundos listar
    python -m scripts.mundos verificar [id]
"""

import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

DADOS = Path(__file__).resolve().parent.parent / "data"
MUNDOS_DIR = DADOS / "mundos"

FORMATO = 1                 # versão do formato do manifesto
MUNDO_INICIAL = "v1"        # o de todo save de antes da v2.7
MUNDO_PADRAO = "v1"         # o de jogo novo

ARQUIVOS_DA_LIGA = ("clubes.json", "jogadores.json", "livres.json")


class MundoIndisponivel(Exception):
    """O mundo não pode ser carregado (ausente ou alterado)."""


class MundoAusente(MundoIndisponivel):
    def __init__(self, mundo):
        super().__init__(f"O mundo '{mundo}' não está instalado")
        self.mundo = mundo


class MundoAlterado(MundoIndisponivel):
    def __init__(self, mundo, problemas):
        super().__init__(
            f"O mundo '{mundo}' não bate com o manifesto: " + "; ".join(problemas)
        )
        self.mundo = mundo
        self.problemas = problemas


# ---------------------------------------------------------------------------
# leitura
# ---------------------------------------------------------------------------

def hash_arquivo(caminho):
    """sha256 do conteúdo com o fim de linha normalizado para LF."""
    dados = Path(caminho).read_bytes().replace(b"\r\n", b"\n")
    return "sha256:" + hashlib.sha256(dados).hexdigest()


def _caminho_manifesto(mundo):
    return MUNDOS_DIR / mundo / "manifesto.json"


def ids():
    """Os mundos instalados, em ordem de id."""
    if not MUNDOS_DIR.is_dir():
        return []
    return sorted(p.parent.name for p in MUNDOS_DIR.glob("*/manifesto.json"))


def existe(mundo):
    return _caminho_manifesto(mundo).is_file()


@lru_cache(maxsize=None)
def manifesto(mundo):
    """O manifesto do mundo (dict; não alterar). MundoAusente se não houver."""
    caminho = _caminho_manifesto(mundo)
    if not caminho.is_file():
        raise MundoAusente(mundo)
    with open(caminho, encoding="utf-8") as arquivo:
        return json.load(arquivo)


def raiz(mundo):
    """A pasta de onde saem os caminhos do manifesto: relativa a `data/`
    (o v1 aponta para `seeds`) ou absoluta (mundos de teste)."""
    pasta = Path(manifesto(mundo)["raiz"])
    return pasta if pasta.is_absolute() else DADOS / pasta


def ligas(mundo):
    """{id da liga: nome}, na ordem das tabelas."""
    return {liga: dados["nome"] for liga, dados in manifesto(mundo)["ligas"].items()}


def pasta_da_liga(mundo, liga):
    return raiz(mundo) / manifesto(mundo)["ligas"][liga]["pasta"]


def problemas(mundo):
    """O que não bate entre os arquivos e o manifesto (lista vazia = íntegro)."""
    m = manifesto(mundo)
    achados = []
    base = raiz(mundo)
    for relativo, esperado in m["arquivos"].items():
        caminho = base / relativo
        if not caminho.is_file():
            achados.append(f"falta {relativo}")
        elif hash_arquivo(caminho) != esperado:
            achados.append(f"{relativo} foi alterado")
    # arquivo de liga que o jogo leria e o manifesto não conhece
    for liga in m["ligas"]:
        for nome in ARQUIVOS_DA_LIGA:
            caminho = pasta_da_liga(mundo, liga) / nome
            relativo = caminho.relative_to(base).as_posix()
            if caminho.is_file() and relativo not in m["arquivos"]:
                achados.append(f"{relativo} não está no manifesto")
    return achados


@lru_cache(maxsize=None)
def verificar(mundo):
    """Confere o mundo uma vez por processo. MundoAusente / MundoAlterado."""
    achados = problemas(mundo)
    if achados:
        raise MundoAlterado(mundo, achados)
    return True


def limpar_cache():
    """Para os testes, que montam mundos em pastas temporárias."""
    manifesto.cache_clear()
    verificar.cache_clear()


def exigir_fora_dos_mundos(destino):
    """Os scripts que geram seeds chamam antes de gravar: nenhum arquivo de
    um mundo instalado pode ser reescrito (gere numa pasta de trabalho e crie
    um mundo novo com ela)."""
    destino = Path(destino).resolve()
    for mundo in ids():
        pasta = raiz(mundo).resolve()
        if destino == pasta or pasta in destino.parents:
            raise PermissionError(
                f"{destino} é do mundo '{mundo}', que é imutável: grave numa "
                "pasta de trabalho e crie um mundo novo com scripts.mundos"
            )


# ---------------------------------------------------------------------------
# criação
# ---------------------------------------------------------------------------

def _ler(caminho):
    if not caminho.is_file():
        return []
    with open(caminho, encoding="utf-8") as arquivo:
        return json.load(arquivo)


def _contagem(pasta):
    return {
        "clubes": len(_ler(pasta / "clubes.json")),
        "jogadores": len(_ler(pasta / "jogadores.json")),
        "livres": len(_ler(pasta / "livres.json")),
    }


def _identidades(pasta):
    """Clubes e jogadores de uma liga: jogador por `ref` quando houver (mundos
    da API), senão pelo nome (o v1 não tem `ref`)."""
    clubes = {c["nome"] for c in _ler(pasta / "clubes.json")}
    jogadores = {
        j.get("ref") or j["nome"]
        for nome in ("jogadores.json", "livres.json")
        for j in _ler(pasta / nome)
    }
    return clubes, jogadores


def _alteracoes(base, pastas, resumo):
    """O que mudou do mundo `base` para as `pastas` ({liga: pasta}) novas.
    Mundo sem base (o v1) só tem o resumo: tudo nele é o começo."""
    if not base:
        return {"resumo": resumo}
    antes_ligas = set(manifesto(base)["ligas"])
    depois = {liga: _identidades(p) for liga, p in pastas.items()}
    antes = {liga: _identidades(pasta_da_liga(base, liga)) for liga in antes_ligas}
    clubes_a = set().union(*(c for c, _ in antes.values())) if antes else set()
    clubes_d = set().union(*(c for c, _ in depois.values()))
    jog_a = set().union(*(j for _, j in antes.values())) if antes else set()
    jog_d = set().union(*(j for _, j in depois.values()))
    return {
        "resumo": resumo,
        "ligas": {
            "entraram": sorted(set(pastas) - antes_ligas),
            "sairam": sorted(antes_ligas - set(pastas)),
        },
        "clubes": {
            "entraram": sorted(clubes_d - clubes_a),
            "sairam": sorted(clubes_a - clubes_d),
        },
        "jogadores": {
            "entraram": len(jog_d - jog_a),
            "sairam": len(jog_a - jog_d),
        },
    }


def montar_manifesto(mundo, nome, raiz_dados, ligas_info, base=None,
                     resumo="", criado_em=None, gerado_por=None):
    """O manifesto de um mundo cujos arquivos já estão no lugar.
    `ligas_info`: {liga: {"nome", "pasta" (relativa à raiz), "pais",
    "divisao", "origem", "temporada", ...}}, na ordem das tabelas."""
    raiz_abs = Path(raiz_dados)
    raiz_abs = raiz_abs if raiz_abs.is_absolute() else DADOS / raiz_abs
    ligas_m, arquivos = {}, {}
    totais = {"ligas": 0, "clubes": 0, "jogadores": 0, "livres": 0}
    pastas = {}
    for liga, info in ligas_info.items():
        pasta = raiz_abs / info["pasta"]
        if not (pasta / "clubes.json").is_file():
            raise FileNotFoundError(f"{pasta / 'clubes.json'} não existe")
        pastas[liga] = pasta
        contagem = _contagem(pasta)
        ligas_m[liga] = {**info, **contagem}
        totais["ligas"] += 1
        for chave, valor in contagem.items():
            totais[chave] += valor
        for arquivo in ARQUIVOS_DA_LIGA:
            if (pasta / arquivo).is_file():
                relativo = (pasta / arquivo).relative_to(raiz_abs).as_posix()
                arquivos[relativo] = hash_arquivo(pasta / arquivo)
    return {
        "id": mundo,
        "formato": FORMATO,
        "nome": nome,
        "criado_em": criado_em or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "base": base,
        "raiz": str(raiz_dados).replace("\\", "/"),
        "ligas": ligas_m,
        "totais": totais,
        "arquivos": dict(sorted(arquivos.items())),
        "gerado_por": gerado_por or {"script": "scripts.mundos"},
        # fotos e escudos (reservado; sem licença, nada por enquanto)
        "midia": {},
        "alteracoes": _alteracoes(base, pastas, resumo),
    }


def gravar_manifesto(dados):
    caminho = _caminho_manifesto(dados["id"])
    if caminho.exists():
        raise FileExistsError(f"o mundo '{dados['id']}' já existe e é imutável")
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    limpar_cache()
    return caminho


def criar_mundo(mundo, nome, base, trocar=None, tirar=(), resumo="",
                ligas_novas=None):
    """Cria o mundo `mundo` a partir do `base`: copia as ligas do base para
    `data/mundos/<mundo>/ligas/<liga>/`, trocando as de `trocar`
    ({liga: pasta com os arquivos novos}) e sem as de `tirar`.
    `ligas_novas`: {liga: info do manifesto} das ligas que o base não tem
    (com "pasta_origem"); as trocadas podem trazer info nova em
    `ligas_novas` também (ex.: outra temporada/origem). Nunca sobrescreve."""
    trocar = dict(trocar or {})
    ligas_novas = dict(ligas_novas or {})
    if existe(mundo):
        raise FileExistsError(f"o mundo '{mundo}' já existe e é imutável")
    destino = MUNDOS_DIR / mundo
    if (destino / "ligas").exists():
        raise FileExistsError(f"{destino / 'ligas'} já existe")

    info_base = manifesto(base)["ligas"]
    ordem = [l for l in info_base if l not in tirar]
    ordem += [l for l in ligas_novas if l not in ordem]
    ligas_info = {}
    for liga in ordem:
        info = dict(info_base.get(liga, {}))
        info.update({k: v for k, v in ligas_novas.get(liga, {}).items()
                     if k != "pasta_origem"})
        for chave in ("clubes", "jogadores", "livres"):
            info.pop(chave, None)
        origem = Path(trocar.get(liga) or ligas_novas.get(liga, {}).get("pasta_origem")
                      or pasta_da_liga(base, liga))
        alvo = destino / "ligas" / liga
        alvo.mkdir(parents=True)
        for arquivo in ARQUIVOS_DA_LIGA:
            if (origem / arquivo).is_file():
                shutil.copyfile(origem / arquivo, alvo / arquivo)
        info["pasta"] = f"ligas/{liga}"
        ligas_info[liga] = info

    try:
        relativo = destino.relative_to(DADOS).as_posix()
    except ValueError:
        relativo = destino.as_posix()     # mundos de teste, fora de data/
    dados = montar_manifesto(mundo, nome, relativo, ligas_info, base=base, resumo=resumo)
    gravar_manifesto(dados)
    return dados


# ---------------------------------------------------------------------------
# linha de comando
# ---------------------------------------------------------------------------

def _main(args):
    comando = args[0] if args else "listar"
    if comando == "listar":
        for mundo in ids():
            m = manifesto(mundo)
            t = m["totais"]
            padrao = " (padrão)" if mundo == MUNDO_PADRAO else ""
            print(f"{mundo}{padrao}: {m['nome']} — {t['ligas']} ligas, "
                  f"{t['clubes']} clubes, {t['jogadores']} jogadores, "
                  f"{t['livres']} livres")
        return 0
    if comando == "verificar":
        alvo = args[1:] or ids()
        erros = 0
        for mundo in alvo:
            achados = problemas(mundo)
            print(f"{mundo}: {'ok' if not achados else '; '.join(achados)}")
            erros += bool(achados)
        return 1 if erros else 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
