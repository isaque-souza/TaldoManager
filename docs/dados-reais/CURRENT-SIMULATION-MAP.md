# Mapa do motor de simulação atual

Auditoria de 2026-11-18, `main` em 8ec9dd0. Nada foi alterado.

## Pontos de entrada

| Entrada | Arquivo |
|---|---|
| API + site | `backend/app/main.py` (FastAPI; o frontend é servido em `/` pelo próprio app) |
| Rotas | `app/api/routes.py` (~1.300 linhas) + `app/api/contas.py`; schemas em `app/api/schemas.py` |
| CLI | `backend/scripts/simular.py` (temporada contínua no terminal) |
| Deploy | `Dockerfile` + `deploy/` — VPS, cron puxa a `main` e reconstrói em até 5 min |

## Camadas

```
frontend/ (JS puro)  →  app/api  →  app/services  →  app/domain  →  app/repositories  →  SQLite
                                         │
                                         └→ scripts/data_loader.py → data/seeds/*.json
```

O domínio (`app/domain`) não toca no banco nem em rede. Os serviços montam o
`Campeonato` (seed + snapshot), chamam o domínio e gravam pelos repositórios.

## Como o mundo é carregado

1. `data_loader.LIGAS`: 8 ligas → pasta de seed (`taldo`, `premier`, `taldo_b`,
   `championship`, `laliga`, `segunda`, `brasileirao`, `brasileirao_b`).
2. `carregar_jogadores(liga)` → `Jogador(nome, idade, posicao, overall,
   potencial, contrato, multa, funcao, secundarias, fama)`.
3. `carregar_clubes(jogadores, liga)` → `Clube(nome, pais, dinheiro,
   torcedores)` + titulares/reservas por id da seed, estádio, rivais,
   identidade, `posicao_anterior`.
4. `carregar_campeonato(ligas)` → `Campeonato("Taldo", clubes)` + livres +
   `vontade.completar` (formador/sonho).
5. Save em andamento: `carregar_campeonato_do_save(sim)` + 
   `temporada.restaurar_estado(campeonato, estado_json)` — casa **por nome**.

## O jogador para o motor

| Dado | Origem | O motor usa? |
|---|---|---|
| `overall` | seed (estimado nos importadores) | **sim — é o número central** |
| `posicao` (setor) | seed | sim (Goleiro/Defesa/Meio-Campo/Ataque) |
| `funcao`, `secundarias` | seed | sim (vagas da formação, rendimento fora de posição) |
| 6 atributos (VEL, FIN, PAS, DRI, MAR, FIS; goleiro REF, POS) | **calculados**: overall + perfil da função + "estilo" fixo tirado do hash do nome (`app/domain/atributos.py`) | o motor usa o **estilo** (o desvio), não o valor absoluto |
| idade, potencial | seed | evolução/envelhecimento na virada |
| energia, condição | estado do save | fadiga e recuperação |
| fama, contrato, salário | calculados / estado | mercado, finanças, humor |
| nacionalidade | existe na seed (`"BRA"`), **não é carregada** | não |
| foto | não existe | — |

Consequência importante: **o motor não precisa de atributos externos.** Ele
precisa de um `overall` bem calibrado, setor, função e secundárias. Hoje o
`overall` dos jogadores reais é estimado (força do clube na tabela real,
camisa, idade, ruído fixo por nome, teto, e "estrelas" corrigidas à mão em
`data/fontes/estrelas-*.json`).

## Fluxo de uma rodada

`temporada_service.avancar()` (rodada a rodada) / `calendario_service` (dia a dia):

1. carrega o campeonato do save (seed + `restaurar_estado`);
2. `Campeonato.jogar_rodada()` — para cada jogo da rodada de cada liga:
   - `Partida(clube1, clube2)` → `preparar_partida()` (escalação pela
     formação/XI/plano, suspensos e lesionados fora);
   - `simular_partida()` → 90 + acréscimos de `simular_minuto()`:
     ataque (`simular_ataque`, `duelo`, `fator_ataque`, `forca_em_campo`),
     finalização, defesa do goleiro, gol/assistência (`escolher_artilheiro`,
     `distribuir_assistencia`), pênalti (`simular_penalti_minuto`, cobrador,
     goleiro pega), drible/passe-chave/desarme/interceptação/corte, faltas →
     cartões (`_registrar_falta`, `_expulsar`), escanteios, lesões
     (`sortear_lesoes`), fadiga (`atualizar_fadiga`), substituições (CPU ou
     decisões ao vivo do técnico — `aplicar_decisoes`);
   - `finalizar_partida()`: posse, estatísticas, notas (`_nota`,
     `calcular_notas`), MVP, hat-tricks, clean sheet, classificação;
3. recuperação de energia, suspensões (vermelho = 1 jogo, 5 amarelos = 1),
   lesões contando rodadas;
4. copas na quarta (`jogar_copa`, `jogar_copa_adiada` para o jogo do técnico);
5. finanças da rodada (bilheteria, salários), torcida, mercado da CPU
   (`mercado_cpu`), ofertas (`ofertas.no_dia`), mensagens;
6. `snapshot_estado()` → `estado_json`; partidas/lances/atuações nas tabelas.

RNG: o estado do `random` vai no snapshot; calendário e mercado da CPU usam
sementes isoladas — com a mesma seed, a temporada se reproduz.

## Virada de temporada (carreira)

`carreira_service` (≈ linha 170): nova seed da temporada →
`divisoes.do_save_na_virada` (o mundo cresce com as ligas novas das seeds) →
`carregar_campeonato(ligas)` (seeds **atuais**) → `_sem_nomes_repetidos` →
acesso/rebaixamento (4 sobem, 4 caem) → `preparar_nova_temporada` aplica os
clubes/jogadores finais do save por cima → envelhecer/evoluir, aposentadorias,
contratos, base.

Ou seja, a carreira já é independente da seed para quem ela conhece (elencos,
overall, contratos vêm do save), mas a seed ainda entra: calendário,
identidade, rivais, ligas novas e qualquer jogador da seed que o save não
"cubra".

## Competições

- 8 ligas jogadas na mesma rodada, cada uma com tabela e calendário próprios
  (método do círculo, ordem sorteada por temporada).
- Séries A/B por país, 4 sobem e 4 caem (`app/domain/divisoes.py`).
- Copas (v2.6, `app/domain/copa.py`): uma entre as Séries A e uma nacional
  por país (A+B), pênaltis, jogo do técnico adiado para a quarta.

## Desempenho

8 ligas ≈ 3.900 jogadores: avançar uma rodada ~0,75 s (após #126; era ~3 s).
Os gargalos já vistos crescem com o tamanho do mundo (UPDATE por jogador,
`vontade.completar`, cálculo de atributos). 14 ligas ≈ 7.000 jogadores: espere
pelo menos ~1,4 s por rodada e um `estado_json` de ~6 MB regravado a cada dia
— tem de ser medido antes de prometer.

## Testes

- `backend/tests/` — 75 arquivos, 957 funções de teste (domain, services, api,
  db, repositories, seeds), pytest.
- `tests/conftest.py`: cada teste roda num SQLite temporário (`TALDO_DB` em
  `tmp_path`) e sem login.
- Já existem testes de regressão do motor por seed fixa (resultados
  reproduzíveis) e de seeds (`test_seed.py`, `test_seed_premier.py`).
- Suíte completa: ~12 min em série; **~3 min com `pytest -n auto`**
  (pytest-xdist, 12 núcleos) — 994 passando no baseline de 2026-11-18.
