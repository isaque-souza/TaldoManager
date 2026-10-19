# Premier League 2023/24 — OpenFootball

Dados abertos do projeto [OpenFootball](https://github.com/openfootball/england)
(pasta `2023-24/`), em **domínio público (CC0 1.0)** — podem ser copiados,
alterados e redistribuídos sem pedir licença.

- `squads/*.txt` — elencos dos 20 clubes (número, nome, nacionalidade,
  setor, ano de nascimento, clube anterior)
- `1-premierleague.txt` — os 380 jogos da temporada (dá a classificação final)

Baixados com `python -m scripts.baixar_openfootball` (a partir de `backend/`)
e lidos por `python -m scripts.importar_premier`, que gera
`data/seeds/premier/`. Ficam no repositório para o importador funcionar
offline e dar sempre o mesmo resultado.

Overall, potencial, contrato e posição específica **não** vêm daqui: são
calculados pelo importador (e ajustados à mão em `estrelas.json`).
