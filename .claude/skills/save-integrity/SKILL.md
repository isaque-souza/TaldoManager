---
name: save-integrity
description: Verificar a integridade dos saves do TaldoManager — duplicatas, estado_json × tabelas, carreira e temporadas, registros órfãos. Use ao analisar uma cópia de backup, ao validar que um teste ou correção não corrompe dados, ou ao investigar um save "estranho".
---

# save-integrity

Antes de tudo, leia `.claude/auditoria/REGRAS.md`.

## Modelo de dados

- `simulacao` = um save/temporada: `estado` (`em_andamento`|`concluida`),
  `rodada_atual`, `estado_json` (blob), `carreira_id`, `temporada`, `copa_pendente`.
- Blob (`app/domain/temporada.py::snapshot_estado`): `rodada`, `calendario`,
  `semente_calendario`, `rng`, `clubes{nome: {campos, elenco, jogadores{nome: campos}}}`,
  `livres`, `copa`. As tabelas `clube`/`jogador` são a **projeção** do blob.
- Partida: `partida` → `lance`, `atuacao`. Só a liga grava em `partida`; a copa não.
- Contas: `usuario`, `sessao` — **não ler** em auditoria de dados.

## Ferramenta

`AUDITORIA/scripts/diagnostico_integridade.py` — 25 checagens (C01–C24 em SQL,
B01 blob × tabelas), só leitura, documentadas em
`AUDITORIA/02_INTEGRIDADE_HISTORICA.md`.

```bash
python3 -I AUDITORIA/scripts/diagnostico_integridade.py /caminho/COPIA.db --json relatorio.json
```

Recusa o banco padrão e `/dados/`. Confere o SHA-256 antes e depois.

## Procedimento

1. **Nunca** no servidor. O responsável fornece uma cópia local do backup.
2. Rodar o diagnóstico; começar pelas checagens **fortes**.
3. Para cada achado: consultar a coluna de falsos positivos; olhar 2 ou 3
   exemplos em detalhe (SELECT na mesma cópia); classificar como
   corrupção confirmada, explicação legítima ou indeterminado.
4. Relatório em `AUDITORIA/NN_*.md`: contagens, exemplos **sem dados pessoais**
   (ids de save, não nomes de usuários), classificação.
5. **Não corrigir registros.** Propor o plano de saneamento e aguardar.

## Ao criar checagem nova

- Só `SELECT`; adicionar a `SQL` ou `FUNCOES` em `diagnostico_integridade.py`.
- Validar nos dois sentidos em `test_auditoria_diagnostico.py`: zero achados na
  base limpa e acusação na base com o defeito reproduzido.
- Documentar: o que detecta, tabelas, interpretação, falsos positivos.
