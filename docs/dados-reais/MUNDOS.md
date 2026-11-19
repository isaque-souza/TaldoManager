# Mundos versionados (Fase 1, v2.7)

Um **mundo** é uma versão congelada das seeds. Cada save grava o mundo em que
nasceu (`simulacao.mundo`) e carrega **só** esse mundo, para sempre — nas
rodadas, na transmissão, no mercado, no pós-jogo e na virada de temporada.

## Onde fica

```
backend/data/
  seeds/                         ← o mundo v1, nos lugares de sempre (não muda)
  mundos/
    v1/manifesto.json            ← descreve data/seeds/ (raiz "seeds")
    <id>/manifesto.json          ← mundos novos
    <id>/ligas/<liga>/{clubes,jogadores,livres}.json
```

| Mundo | O que é |
|---|---|
| `v1` | as 8 ligas da v2.6 (Premier 23/24, Brasileirão 2017...). Todo save de antes da v2.7 é dele |

O mundo de jogo novo é `scripts.mundos.MUNDO_PADRAO` (hoje `v1`).

## O manifesto

`id`, `formato`, `nome`, `criado_em`, `base` (o mundo de onde veio), `raiz`,
`ligas` (por liga: nome, pasta, país, divisão, origem, temporada e contagens),
`totais`, `arquivos` (sha256 de cada arquivo), `gerado_por`, `midia`
(reservado para fotos/escudos, vazio) e `alteracoes` (o que mudou em relação
ao `base`: ligas, clubes e jogadores que entraram e saíram).

O hash normaliza o fim de linha (CRLF → LF): o `.gitattributes` deixa CRLF no
Windows e LF no Linux, e o mesmo mundo tem o mesmo hash nos dois.

## Imutabilidade

- O jogo confere os hashes antes de carregar um mundo (uma vez por processo).
  Arquivo diferente ou faltando → `MundoAlterado`; mundo que não existe →
  `MundoAusente`. A API responde **503** com a mensagem, nunca carrega outro
  mundo no lugar.
- Na subida, o app registra no log os mundos usados por algum save que não
  estão íntegros (`app.main.conferir_mundos`).
- `tests/test_mundos.py` confere todo mundo instalado contra o manifesto:
  **editar qualquer arquivo de mundo quebra a suíte.**
- Os scripts que geravam seeds (`gerar_dados`, `gerar_funcoes`,
  `gerar_livres`, `ampliar_elencos`, `gerar_ligas`, `importar_premier`,
  `importar_brasileirao`) recusam gravar dentro de um mundo
  (`mundos.exigir_fora_dos_mundos`).
- Corrigir um dado = criar um mundo novo. Mundo nunca é apagado.

## Comandos (pasta `backend/`)

```
python -m scripts.mundos listar         # mundos instalados e totais
python -m scripts.mundos verificar      # confere todos os hashes
```

Criar um mundo (Fase 4 em diante), a partir de uma pasta de trabalho:

```python
from scripts import mundos
mundos.criar_mundo(
    "v2", "Premier League atual", base="v1",
    trocar={"premier": "caminho/da/pasta/de/trabalho/premier"},
    ligas_novas={"premier": {"origem": "API-Football v3", "temporada": "2025/26"}},
    resumo="Premier 23/24 → 2025/26",
)
```

As ligas que não mudaram são copiadas do base (mesmo hash).

## No código

| Onde | O quê |
|---|---|
| `scripts/mundos.py` | manifesto, hashes, verificação, criação |
| `scripts/data_loader.py` | `carregar_*(…, mundo)`, `mundo_do_save(sim)`, `todas_as_ligas(mundo)`, `nome_da_liga`, `rivais_do_seed(mundo)`. Sem `mundo`, é o v1 |
| `simulacao.mundo` | `TEXT NOT NULL DEFAULT 'v1'` (migração aditiva) |
| `temporada_service.iniciar`, `simulacao_service.salvar_temporada` | `mundo=` (padrão: `MUNDO_PADRAO`) |
| `carreira_service.proxima_temporada` | a temporada nova herda o mundo; só ganha ligas do mesmo mundo |
| API | `GET /mundos`; `mundo` opcional em `POST /simulacoes`, `GET /clubes`, `GET /clubes/{nome}` (400 se não existir) |

## Ainda depende do v1

Os módulos de regra (`divisoes`, `copa`, pesos de economia) conhecem as ligas
pelo id (`premier`, `laliga`...). Um mundo com os mesmos ids funciona sem
mudança; ligas novas (Itália, Alemanha, França) vão exigir levar essas regras
para o manifesto — Fase 5.
