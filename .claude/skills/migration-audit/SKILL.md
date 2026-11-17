---
name: migration-audit
description: Auditar migrações de esquema do TaldoManager (init_db, _COLUNAS_NOVAS, _migrar, _refazer_transferencia, PRAGMA user_version) e propostas de mudança de banco (UNIQUE, índices, colunas). Use antes de qualquer alteração em schema.sql ou conexao.py, ou ao avaliar se uma mudança é segura para os saves existentes.
---

# migration-audit

Antes de tudo, leia `.claude/auditoria/REGRAS.md`. **Migrações exigem
autorização explícita.** Esta skill investiga e propõe; não aplica.

## Como o banco evolui hoje

- `app/db/schema.sql`: `CREATE TABLE IF NOT EXISTS` (banco novo).
- `app/db/conexao.py::init_db` roda a cada boot:
  - `_migrar`: `ALTER TABLE ADD COLUMN` para cada item de `_COLUNAS_NOVAS`
    (84 colunas) que falta;
  - `_refazer_transferencia`: recria a tabela quando o esquema antigo não serve;
  - `_renomear_jogadores`: troca de nomes, controlada por `PRAGMA user_version` (1).
- Não há framework de migração nem rollback. O deploy é automático (a `main`
  vai para a VPS em até 5 min) e o boot migra o banco de produção sozinho.
- Backup: `deploy/backup.sh`.

## Checklist para uma mudança proposta

1. **Idempotente?** Rodar `init_db()` duas vezes não pode falhar nem duplicar.
2. **Banco antigo**: testar a partir de um banco criado com o esquema da
   versão anterior (gerado num checkout antigo, em diretório temporário), não
   só de um banco novo.
3. **Dados existentes violam a regra nova?** Para `UNIQUE` ou `NOT NULL`, rodar
   antes a consulta equivalente do diagnóstico (ex.: C01 para
   `UNIQUE(simulacao_id, rodada, mandante_id)`) numa **cópia do backup**. Se
   houver violação, o `CREATE UNIQUE INDEX` falha no boot e **derruba a produção**.
4. **Tempo de execução** numa cópia do tamanho real (bloqueia o banco no boot).
5. **Reversão**: qual é o plano se der errado depois do deploy? Backup
   verificado antes; a migração pode ser revertida sem perder saves novos?
6. **Blob**: a mudança exige mexer em `estado_json`? Saves em andamento
   precisam continuar abrindo (`restaurar_estado` tolera chave ausente?).
7. **Teste**: `backend/tests/db/` tem os testes de `init_db`. Uma migração nova
   precisa de teste com banco antigo e banco novo.

## Saída

Documento `AUDITORIA/NN_MIGRACAO_*.md` com o checklist preenchido, a
evidência de cada item e a recomendação. Aguardar autorização.
