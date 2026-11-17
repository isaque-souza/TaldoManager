# Auditoria 03 — Correção das ferramentas de qualidade

Branch: `auditoria/01-concorrencia-rng` · Data: 17/11/2026

## Escopo e autorização

O responsável autorizou corrigir os 10 achados do `/code-review` da branch,
**só** em arquivos de auditoria, testes, scripts e configuração do Claude Code.
Sem tocar no motor, sem corrigir R1/R2/R10, sem `schema.sql`, migração,
produção, deploy, push ou merge. Commit só depois de apresentar diff e relatório.

Arquivos alterados (nenhum fora do escopo):

| Arquivo | O quê |
|---|---|
| `.claude/hooks/guarda.py` | achados 1–4 + bypasses da 2ª e 3ª revisões |
| `.claude/hooks/test_guarda.py` | suíte hermética: 12 → 41 testes |
| `.claude/hooks/README.md` | comportamento novo e limitações |
| `.claude/auditoria/REGRAS.md` | convenção `xfail(raises=DefeitoReproduzido)` e fixtures por SQL |
| `backend/tests/auditoria/roteiro.py` | `DefeitoReproduzido`, `RoteiroTravado`, `exigir`, `conferir_roteiro` |
| `backend/tests/auditoria/test_auditoria_r1_rng.py` | 4 xfail com `raises=`; asserções finais com `exigir` |
| `backend/tests/auditoria/test_auditoria_r2_concorrencia.py` | 3 xfail com `raises=`; roteiro travado vira falha |
| `backend/tests/auditoria/test_auditoria_diagnostico.py` | duplicatas por SQL; testes dos achados 8–10 |
| `backend/tests/auditoria/test_auditoria_ferramentas.py` | **novo**: semântica do xfail e do roteiro |
| `AUDITORIA/scripts/diagnostico_integridade.py` | achados 8–10 + 2ª/3ª revisões |

## Os 10 achados originais

| # | Prior. | Achado | Causa | Solução | Teste de regressão | Resultado |
|---|---|---|---|---|---|---|
| 2 | P0 | Exceção no hook liberava o comando | `main()` devolvia 0 em qualquer exceção; Docker ausente/lento levantava `FileNotFoundError`/`TimeoutExpired` | Falha nunca libera em silêncio: `_reserva` decide com checagem ampla (sensível → ask com o erro; comum como `ls`/`cat`/`grep` → passa com aviso). Erro na verificação do commit preserva os outros motivos (ex.: push). `_testes_de_auditoria` trata `OSError`/`SubprocessError`. Entrada inválida passa pela reserva | `FalhaInterna` (8 testes): sem Docker, Docker quebrado, falha simulada na análise e no commit, entrada inválida, `fim` | corrigido |
| 3 | P0 | Heredoc escondia comandos | `sem_mensagens` apagava **todo** heredoc | Só o heredoc de `git commit -F -` (com terminador encontrado) e o `-m` **de um git commit** saem da análise; mensagem com `$(...)`/crase fica | `Heredoc` (7 testes): `sqlite3 <<SQL DELETE`, `bash <<EOF git push`, `python3 - <<EOF os.system`, delimitador `END-MSG`, heredoc sem fim, `bash -cm '...'`, `-m "$(git push)"` | corrigido |
| 4 | P0 | Agente podia alterar a própria proteção | `.claude/` inteiro era livre; só `settings*` pedia aprovação | Arquivos de proteção: `.claude/hooks/`, `.claude/settings*`, `.claude/auditoria/`, `.claude/agents/`, `~/.claude/settings*`. Edit/Write → ask. Bash: caminhos **resolvidos** (cd com opções, `normpath`, glob, pasta-mãe em comandos destrutivos, `$(...)` aninhado, xargs); leitura e execução do próprio guarda passam | `Protecoes` (6 testes, ~45 comandos): `sed -i`, `>`, `tee`, `cp`, `rm`, `mv .claude`, `git checkout --`, `python -c`, `cd .claude && rm -r hooks`, `D=.claude; rm -r $D/hooks`, `.claude/./hooks`, `sed 'w ...'`, `git diff --output=`, `tree -o`, `find \| xargs rm`, `rm -r .[a-z]*`... e o que deve passar | corrigido (limites na seção de riscos) |
| 1 | P1 | `git add X && git commit` não via X | o hook roda antes do comando e lia só o índice | `_arquivos_do_commit`: índice + caminhos de cada `git add` do mesmo comando (`-A`, `.`, pastas, globs, `-C`, `:/`, `:(top)`, `--pathspec-from-file`, relativos à pasta do Bash) + `commit -a/-am` + `commit <caminho>` | `Commit` (8 testes) num repositório git temporário com `docker` falso (ausente/ok/falha) | corrigido |
| 5 | P1 | Testes do diagnóstico dependiam de o R2 existir | as duplicatas eram produzidas disparando a corrida real | duplicatas montadas **por SQL** no banco temporário (`_duplicar_rodada`, `_duplicar_virada`); `_como_backup_antigo` remove UNIQUE em índice **ou dentro da tabela** (reconstrução de 12 etapas) | `test_r2_corrigido_com_unique...[indice]` e `[tabela]` simulam a correção futura; `test_nenhum_teste_do_diagnostico_depende_da_corrida` | corrigido |
| 6 | P1 | xfail aceitava qualquer falha | `xfail(strict=True)` sem `raises=`; timeouts eram `AssertionError` | `raises=DefeitoReproduzido` nos 7 xfail; asserções finais com `exigir`; espera vencida, barreira quebrada e fio preso viram `RoteiroTravado` (não é `AssertionError`) | `test_auditoria_ferramentas.py` (8 testes), incluindo um pytest real que confere **qual** teste virou XFAIL e quais viraram FAILED | corrigido |
| 8 | P1 | Blob malformado derrubava o diagnóstico | `executar` só tratava `sqlite3.DatabaseError`; `len()`/`.items()` em tipos errados | checagem de tipo por save e **por clube** (o defeito de um clube não apaga os outros achados do save); último recurso por save (`blob inesperado`) e por checagem (`erro na checagem`) | `test_blob_malformado...` (topo em lista, `rng[1]` inteiro, `jogadores` lista + divergências reais preservadas), `test_clube_que_nao_e_objeto...`, `test_erro_inesperado_num_save...`, `test_checagem_que_quebra...` | corrigido |
| 7 | P2 | Roteiro de virada duplicado | `_viradas` copiava `_viradas_simultaneas` | o diagnóstico não usa mais corrida nenhuma (achado 5); a cópia foi removida | idem achado 5 | corrigido |
| 9 | P2 | Colunas por trecho de texto | `c in sql_do_create_table` | `SELECT * FROM t LIMIT 0` → `cursor.description` (o authorizer nega PRAGMA) | `test_colunas_pelo_esquema_real...` (`cidade`, `numero_camisa`, CHECK com 'idade') | corrigido |
| 10 | P2 | Homônimos confundidos | índice por nome | chave `(clube, nome)`; homônimos no mesmo clube viram `jogador ambíguo` e não são comparados (o C11 já acusa) | `test_jogadores_homonimos_em_clubes_diferentes...`, `test_homonimos_no_mesmo_clube...` | corrigido |

## Revisões independentes

| Rodada | Sobre | Achados | Destino |
|---|---|---|---|
| 1ª | a branch (commits `af89b71`..`554d8c4`) | 10 | os 10 acima |
| 2ª | as correções da 1ª | 10 (6 confirmados executando o hook): `git -P`, `cd .claude && rm -r hooks`, `D=.claude; rm -r $D`, `sed 'w ...'`, `git diff --output`/`tree -o`, `$()` aninhado, `.claude/./hooks`, assert fraco na semântica do xfail, UNIQUE dentro da tabela, achados do save perdidos, `fetchall` | todos corrigidos, com teste |
| 3ª | as correções da 2ª | confirmou **todos os da 2ª fechados**; 10 novos: git que descarta alterações (`stash`, `checkout -- .`, `restore --source`, `reset ... --hard`, `git rm -r .`), `bash -cm '...'`, `find \| xargs rm`, `cd -P/--`, heredoc `END-MSG`, pathspec `:/`, banco padrão com `cd`/`export`, clube não-objeto no blob, `--config-env`/`--exec-path`, `git apply`/`patch`/`tar` | 9 corrigidos com teste; `git apply`/`am`/`pull`/`patch`/`tar` documentados como limitação |

A 4ª rodada de revisão não foi feita (ver recomendações).

## Testes executados (resultado literal)

| Suíte | Comando | Resultado |
|---|---|---|
| Hook | `python3 .claude/hooks/test_guarda.py` | `Ran 41 tests ... OK` |
| Auditoria | `docker run ... taldo-auditoria:py312 python -m pytest tests/auditoria -q` | `35 passed, 7 xfailed in 16.16s` |
| Completa | `docker run ... taldo-auditoria:py312 python -m pytest tests -q` | `1029 passed, 7 xfailed in 513.55s` (antes: 1011 passed, 7 xfailed) |

**Contraprovas** (os testes novos contra as versões do HEAD, sem mudar o repositório):

| Alvo antigo | Resultado |
|---|---|
| `guarda.py` do HEAD | `Ran 41 tests ... FAILED (failures=25)` — os 16 que passam são comportamento preservado |
| `diagnostico_integridade.py` do HEAD (montado por cima no container) | `7 failed, 11 passed` — os 7 testes dos achados 8–10 |
| `roteiro.py` do HEAD | a coleta de `test_auditoria_ferramentas.py` falha (não existem `DefeitoReproduzido`/`RoteiroTravado`) |

Os 7 xfail continuam XFAIL **pela razão certa**: com `raises=DefeitoReproduzido`,
qualquer outra falha deixaria a suíte vermelha.

## Verificação das proteções em funcionamento

No repositório real, com o hook instalado: `git push origin main` → ask;
`sed -i '' 1d .claude/hooks/guarda.py` → ask; `bash <<EOF git push EOF` → ask;
`git commit -m "$(git push)"` → ask; Edit `.claude/settings.json` → ask;
`cat .claude/hooks/guarda.py`, `ls -la`, Edit `AUDITORIA/x.md` → passam.

Durante o trabalho, um erro meu (uma definição removida por engano) quebrou o
hook instalado: em vez de liberar, ele respondeu **ask** com
`não deu para verificar o commit (NameError ...)` — o achado 2 funcionando.

## Riscos restantes

1. **"ask" no auto mode não garante aprovação humana.** Nesta sessão, as
   edições em `.claude/hooks/*` e em `.claude/auditoria/REGRAS.md` foram
   marcadas "ask" pelo hook e aplicadas sem recusa. Não dá para saber, deste
   lado, se o responsável aprovou ou se o classificador do auto mode aprovou.
   Para a proteção valer como aprovação humana, o auto mode precisa estar
   desligado nas sessões que mexem em proteção ou em produção.
2. **Análise de texto tem cauda.** Cada revisão fechou uma classe de bypass e
   achou outra menor. Ofuscação deliberada (variável definida em outro
   comando, `eval`, base64, script em arquivo) e comandos que reescrevem
   arquivos sem citá-los (`git apply/am/pull/cherry-pick`, `patch`, `tar x`)
   escapam. O hook é rede contra acidente e contra o caminho óbvio.
3. **Proteção forte exige uma camada fora do texto**, por exemplo: regras de
   `permissions.deny`/`ask` do Claude Code para `Edit(.claude/hooks/**)` e
   `.claude/settings*` combinadas com o sandbox de Bash (que limita a escrita
   em disco), ou arquivos de proteção imutáveis no sistema (`chflags uchg`).
   Não implementado: é mudança de configuração que pede decisão do responsável
   e verificação prévia de como essas regras se comportam nesta versão.
4. **Produção pelo Bash** (`sed -i backend/app/...`) continua só com o aviso
   do hook `fim`, como antes.
5. **Exposição pública** (fora do escopo desta rodada): a branch pública
   contém os roteiros de reprodução de R1/R2. Decisão pendente do responsável
   antes do merge.

## Confirmação

Nenhum código de produção foi alterado: `backend/app/`, `frontend/`,
`backend/scripts/`, `backend/data/`, `Dockerfile`, `deploy/`,
`requirements.txt` e `schema.sql` estão intocados (`git status` só lista os
arquivos da tabela do início). R1, R2 e R10 não foram corrigidos. Nenhuma
migração, acesso a produção, deploy, push, merge ou commit.

## Recomendações

1. Revisar o diff e autorizar o commit desta rodada.
2. Rodar uma 4ª revisão independente antes do PR, já sabendo que o resultado
   esperado é cauda menor — e decidir se a camada fora do texto (risco 3) entra
   antes ou depois do PR.
3. Desligar o auto mode nas sessões de correção de R1/R2/R10.
4. Decidir sobre a exposição pública dos roteiros antes do merge.
