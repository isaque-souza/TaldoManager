# 02 — Preservação e integridade histórica

**Data:** 17/11/2026 · **Branch:** `auditoria/01-concorrencia-rng`
**Objetivo:** saber, **sem tocar em nada**, se um banco já tem as marcas do R2
(rodada e virada em dobro) ou outras inconsistências, antes de escolher uma
correção, e principalmente antes de qualquer constraint `UNIQUE`.

Ferramenta: [`scripts/diagnostico_integridade.py`](scripts/diagnostico_integridade.py).
Testes: `backend/tests/auditoria/test_auditoria_diagnostico.py`.

---

## Como rodar (numa cópia, nunca na produção)

```bash
cp /caminho/do/backup/taldo_manager.db ~/auditoria/copia.db   # cópia local do backup
python3 -I AUDITORIA/scripts/diagnostico_integridade.py ~/auditoria/copia.db --json ~/auditoria/relatorio.json
```

Usa só a biblioteca padrão e não importa o código do jogo. Python 3.9 ou mais novo.

### Por que é seguro

| Camada | O que faz |
|---|---|
| Caminho explícito | sem argumento, o script não roda. Recusa arquivo inexistente, o banco padrão do projeto (`backend/data/database/taldo_manager.db`) e qualquer caminho em `/dados/` (o volume de produção do container). |
| `mode=ro&immutable=1` | o SQLite abre só para leitura e não cria `-journal`/`-wal` nem trava o arquivo. |
| `PRAGMA query_only = ON` | o motor recusa qualquer escrita. |
| Authorizer | só libera `SELECT`, leitura de coluna, função e CTE recursiva. `INSERT`, `UPDATE`, `DELETE`, `CREATE` (inclusive índice), `DROP`, `ALTER`, `ATTACH` e `PRAGMA` são negados. As tabelas `usuario` e `sessao` (hash de senha e de sessão) não são lidas. |
| SHA-256 antes e depois | se o arquivo mudar, o script aborta. O hash sai no relatório para provar que a cópia ficou intacta. |

Um teste (`test_authorizer_nega_toda_escrita_e_as_tabelas_de_conta`) tenta 10
operações proibidas, e as 10 são negadas. Outro (`test_o_arquivo_nao_muda`)
confere o hash.

### Como ler o resultado

- **forte:** não deveria existir em nenhum fluxo do jogo. Um achado forte é
  forte candidato a dano real, mas **ainda não é veredito**: confira os falsos
  positivos da checagem.
- **sinal:** pode ter explicação legítima. Investigue caso a caso.
- **não rodou:** o banco é de um esquema antigo sem aquela tabela ou coluna.
  Não é falha.
- Cada checagem mostra a contagem e até 20 linhas de exemplo (5 no terminal,
  20 no JSON).

**Não corrija nada a partir daqui.** O relatório é insumo para decidir a
correção (soluções R2-D/E em `01_CONCORRENCIA_RNG.md`).

---

## As checagens

Legenda da coluna "Validação": **R2** = o teste reproduz a duplicata e a
checagem acusa; **limpo** = zero achados numa base feita pelos fluxos normais.
"Base limpa" nos testes cobre: temporada em andamento (3 rodadas), venda
aceita seguida de rodada, temporada inteira, virada de carreira seguida de
2 rodadas.

### Rodada em dobro (R2)

| ID | Força | Detecta | Tabelas e colunas | Falsos positivos | Validação |
|---|---|---|---|---|---|
| C01 | forte | o mesmo mandante duas vezes na mesma rodada | `partida(simulacao_id, rodada, mandante_id)` | nenhum conhecido: cada clube manda um jogo por rodada | R2: 10 achados; limpo |
| C02 | forte | um clube em mais de um jogo na rodada, como mandante ou visitante | `partida(simulacao_id, rodada, mandante_id, visitante_id)` | nenhum: a copa não grava em `partida` | R2: 20; limpo |
| C03 | forte | rodadas distintas gravadas ≠ `rodada_atual − 1` (em andamento) ou ≠ `rodadas` (concluída) | `simulacao(estado, rodada_atual, rodadas)`, `partida(rodada)` | saves muito antigos que não gravavam partidas. **Não pega** a rodada dupla (as rodadas distintas batem); pega rodada pulada ou faltando. | R2: 0 (esperado); limpo |
| C04 | forte | rodada com número de jogos ≠ clubes/2 | `clube(simulacao_id)`, `partida(simulacao_id, rodada)` | liga com número ímpar de clubes (hoje todas têm 20) | R2: 1; limpo |
| C17 | forte | `clube.jogos`/`pontos` ≠ o recalculado a partir de `partida` | `clube(jogos, pontos)`, `partida(gols_*)` | regra de pontos antiga; a tabela `clube` só conta a liga | R2: 20; limpo |

Na rodada dupla, as estatísticas acumuladas **não** dobram (o último `UPDATE`
vence). Por isso C17 acusa: a tabela diz 1 jogo, mas há 2 gravados.

### Virada em dobro (R2) e carreira

| ID | Força | Detecta | Tabelas e colunas | Falsos positivos | Validação |
|---|---|---|---|---|---|
| C05 | forte | duas temporadas com o mesmo número na mesma carreira | `simulacao(carreira_id, temporada)` | nenhum: `sucessora()` supõe uma | R2 (dentro da carreira): 1; limpo |
| C06 | sinal | carreira sem a temporada 1 ou com buraco na sequência | `simulacao(carreira_id, temporada)` | o técnico apagou uma temporada (permitido) | R2 (temporada 1 sem carreira): 1; limpo |
| C07 | forte | mais de uma temporada em andamento na mesma carreira | `simulacao(carreira_id, estado)` | nenhum conhecido | R2: 1; limpo |
| C08 | sinal | carreira sem nenhuma temporada | `carreira`, `simulacao(carreira_id)` | todas apagadas (`ON DELETE SET NULL`) | limpo |
| C09 | sinal | clube da temporada ≠ clube da carreira | `simulacao(clube_usuario)`, `carreira(clube_usuario)` | clube renomeado numa migração | limpo |

Na virada dupla de um save **sem** carreira, cada thread cria a sua carreira,
e C05 não vê nada. Quem acusa é C06: a carreira "perdedora" fica com uma
temporada 2 e sem temporada 1, porque o save original aponta só para a outra.

### Estado do save

| ID | Força | Detecta | Tabelas e colunas | Falsos positivos | Validação |
|---|---|---|---|---|---|
| C10 | forte | em andamento sem blob, sem rodada ou com campeão; concluída com blob ou sem campeão; estado desconhecido | `simulacao(estado, estado_json, rodada_atual, campeao)` | temporada neutra antiga concluída sem campeão | limpo |
| B01 | forte | blob × tabelas nos saves em andamento: `rodada` × `rodada_atual`; RNG malformado; conjunto de clubes; elenco por clube; 11 campos de clube e 10 de jogador | `simulacao.estado_json` × `clube`, `jogador` | saves antigos sem algumas chaves (são puladas); campos ausentes no esquema antigo (pulados) | R2: 0 (esperado); limpo, inclusive depois de venda e de virada |

B01 é feito em Python sobre o resultado de `SELECT`s, não em SQL. O blob é
lido como texto e decodificado com `json.loads`.

### Duplicidade por nome (R4: jogador identificado por nome)

| ID | Força | Detecta | Tabelas e colunas | Falsos positivos | Validação |
|---|---|---|---|---|---|
| C11 | forte | dois jogadores com o mesmo nome no save | `jogador(simulacao_id, nome, livre)` | nenhum: o `UPDATE ... WHERE nome=?` atinge os dois | limpo |
| C12 | forte | dois clubes com o mesmo nome no save | `clube(simulacao_id, nome)` | nenhum conhecido | limpo |
| C13 | sinal | jovem da base com nome de jogador do save, ou repetido na base | `jovem_base(nome)`, `jogador(nome)` | nenhum; ao promover, viraria C11 | limpo |

### Filhos da partida e referências cruzadas

| ID | Força | Detecta | Tabelas e colunas | Falsos positivos | Validação |
|---|---|---|---|---|---|
| C14 | forte | duas atuações do mesmo jogador no mesmo jogo | `atuacao(partida_id, jogador_id)` | nenhum conhecido | limpo |
| C15 | sinal | lance idêntico repetido (minuto, tipo, jogador, detalhe) | `lance` | dois amarelos ao mesmo jogador no mesmo minuto: o motor faz isso e a checagem já exclui (ver nota abaixo) | limpo |
| C16 | forte | partida com clube de outro save; atuação ou lance com jogador de outro save | `partida`, `clube`, `atuacao`, `lance`, `jogador` | nenhum conhecido | limpo |
| C18 | sinal | `jogador.gols` ≠ soma de `atuacao.gols` | `jogador(gols)`, `atuacao(gols)` | saves anteriores à tabela `atuacao` | limpo |

> **Nota sobre C15.** Na primeira versão, C15 acusou na base limpa: dois
> `cartao_amarelo` do mesmo jogador no mesmo minuto. Investiguei e é
> comportamento do motor, não gravação dupla: `partida.py:682-685` dá o 2º
> amarelo e só expulsa em 60% dos casos ("o juiz às vezes releva"). Numa
> temporada de seed 5: 93 jogadores com 2 amarelos no jogo, 36 sem expulsão
> (seguem em campo), 2 no mesmo minuto. `lance` e `jogador.amarelos` batem
> (1165 = 1165). Não é bug de integridade. É uma regra de jogo que o
> responsável pelo design pode querer rever. A checagem passou a ignorar o
> par de amarelos.

### Outras tabelas que podem duplicar

| ID | Força | Detecta | Tabelas e colunas | Falsos positivos | Validação |
|---|---|---|---|---|---|
| C19 | sinal | transferência idêntica repetida | `transferencia(simulacao_id, rodada, jogador_id, de_clube_id, para_clube_id, tipo)` | ida e volta do mesmo jogador com os mesmos clubes na mesma janela | limpo |
| C20 | sinal | duas ofertas abertas do mesmo clube pelo mesmo jogador | `oferta_recebida(jogador_id, clube, status)` | nenhum conhecido | limpo |
| C21 | sinal | duas negociações abertas pelo mesmo jogador | `negociacao(jogador, status)` | compra e empréstimo abertos juntos, se a regra permitir | limpo |
| C22 | forte | mais de um plano padrão no save | `plano(padrao)` | nenhum conhecido | limpo |
| C23 | sinal | movimento de virada repetido | `movimento_virada(tipo, jogador, clube)` | nenhum conhecido | limpo |
| C24 | sinal | mensagem idêntica repetida na mesma rodada | `mensagem(rodada, setor, assunto, corpo)` | dois avisos legítimos com o mesmo texto | limpo |

`observado` e `relatorio` já têm `UNIQUE(simulacao_id, nome)` e não precisam de
checagem.

---

## Resultado dos testes

`backend/tests/auditoria/test_auditoria_diagnostico.py`, todos passando:

| Teste | Prova |
|---|---|
| `test_base_limpa_nao_tem_achado_forte` | zero achados fortes e zero erros nos fluxos normais |
| `test_base_limpa_sinais` | zero achados "sinal" nos fluxos normais |
| `test_rodada_dupla_e_acusada` | C01 = 10, C02 = 20, C04 = 1, C17 = 20; C03 e B01 = 0 |
| `test_virada_dupla_dentro_da_carreira_e_acusada` | C05 = 1, C07 = 1 |
| `test_virada_dupla_sem_carreira_e_acusada` | C05 = 0, C06 = 1 |
| `test_recusa_caminho_vazio_inexistente_padrao_e_producao` | as recusas e o código de saída 2 |
| `test_authorizer_nega_toda_escrita_e_as_tabelas_de_conta` | 10 de 10 operações proibidas negadas; os dados seguem iguais |
| `test_o_arquivo_nao_muda` | o SHA-256 bate antes e depois |

Também rodei o script pela linha de comando, no container, numa cópia
temporária: 25 checagens "ok" e saída 0. `/dados/taldo_manager.db` foi
recusado com saída 2. Sem argumento, saída 2.

## Limitações

- **Produção não verificada.** Nenhuma cópia do backup foi usada. O script
  está pronto para isso, mas a decisão e a cópia são do responsável.
- A base limpa dos testes cobre só a Liga Taldo e os fluxos listados acima.
  Copa, empréstimo, base, missões e saves de versões antigas podem gerar
  falsos positivos que não apareceram aqui. Num banco real, comece pelas
  checagens **fortes**.
- B01 compara uma seleção de campos, não o blob inteiro. Campos de humor,
  moral e obras ficam fora.
- A rodada dupla com placares **diferentes** entre as cópias (R1 + R2 juntos)
  é acusada por C01, C02, C04 e C17 do mesmo jeito. O script não diz qual
  cópia é a "certa".
- O script não descobre **quando** a duplicata aconteceu. `partida` não tem
  carimbo de hora.
- Em banco muito grande, C16 e C17 fazem varreduras completas. Numa cópia
  local isso não incomoda ninguém.
