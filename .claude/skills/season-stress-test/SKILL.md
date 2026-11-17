---
name: season-stress-test
description: Rodar temporadas e carreiras longas do TaldoManager em ambiente descartável para achar inconsistências e medir desempenho — várias seeds, 8 ligas, viradas sucessivas, ações do técnico. Use para provar que temporadas completas terminam sem inconsistência ou para benchmark.
---

# season-stress-test

Antes de tudo, leia `.claude/auditoria/REGRAS.md`. Sempre num banco
temporário dentro do container; nunca com dados reais.

## Ingredientes disponíveis

- Serviços: `temporada_service.iniciar(seed, clube_usuario, ligas=...)`,
  `temporada_service.avancar(sid)`, `temporada_service.proxima_rodada(sid)`
  (tem `concluida`), `simulacao_service.salvar_temporada(seed, clube_usuario)`
  (temporada inteira), `carreira_service.proxima_temporada(sid)` (virada;
  em teste, `cargo_garantido` evita a demissão).
- Todas as ligas: `scripts.data_loader.TODAS_AS_LIGAS`.
- Validação ao fim: `AUDITORIA/scripts/diagnostico_integridade.py` sobre o
  banco temporário (espera-se **zero** achados fortes).
- HTTP real: `AUDITORIA/scripts/corrida_natural.py` (modelo de cliente stdlib).

## Roteiro padrão

1. Script em `AUDITORIA/scripts/` (não em `backend/tests`, para não pesar na
   suíte), executado no container com `TALDO_DB=/tmp/<nome>.db`.
2. Matriz mínima: seeds {1, 5, 7, 42, 99} × {Liga Taldo, 8 ligas} × 3
   temporadas seguidas (2 viradas), com ações do técnico entre rodadas (venda,
   escalação, tática).
3. A cada rodada, invariantes baratos: rodada_atual sobe 1; 10 jogos por liga;
   ninguém expulso volta no mesmo jogo; caixa não vira NaN; nenhum jogador em
   dois clubes.
4. Ao fim de cada temporada: o diagnóstico completo.
5. Desempenho: tempo por rodada (mediana e p95), por virada, e tamanho do
   `estado_json`; memória pico (`resource.getrusage`).
6. Relatório em `AUDITORIA/NN_STRESS_*.md` com a tabela de resultados, a
   versão (`git rev-parse HEAD`) e a máquina.

## Cuidados

- Execuções longas: rodar em segundo plano e avisar o responsável.
- Comparar desempenho só entre execuções na mesma máquina e imagem.
- Um achado vira reprodução mínima (ver `concurrency-audit`/`football-engine-audit`),
  não fica só no log do stress.
