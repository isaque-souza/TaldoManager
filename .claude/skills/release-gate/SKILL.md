---
name: release-gate
description: Portão de liberação do TaldoManager — checklist obrigatório antes de propor merge na main (que faz auto-deploy em produção em até 5 minutos). Use antes de abrir PR, pedir merge, ou declarar uma correção pronta.
---

# release-gate

Antes de tudo, leia `.claude/auditoria/REGRAS.md`. Esta skill **não** faz
merge, push nem deploy: produz o parecer para o responsável decidir.

## Por que existe

A `main` vai para a VPS automaticamente (`deploy/auto-atualizar.sh`, cron de
5 min), e o boot roda `init_db()`, que migra o banco de produção. Um merge é,
na prática, um deploy com migração.

## Checklist (cada item com evidência literal)

1. **Branch e escopo**: `git log main..HEAD --oneline` e `git diff main --stat`.
   Só o que foi autorizado? Nenhum arquivo inesperado?
2. **Suíte completa** no Docker: `N passed, M xfailed`, sem `failed`/`error`.
   Os `xfail` que deveriam virar `XPASS` com a correção viraram, e foram
   removidos conscientemente? Nenhum outro sumiu?
3. **Baseline de simulação** (quando o motor mudou): igual, ou a diferença é
   a esperada e está justificada (`AUDITORIA/02_BASELINE_SIMULACAO.md`).
4. **Migração** (quando `schema.sql`/`conexao.py` mudou): checklist da
   `migration-audit` completo, incluindo o diagnóstico numa cópia do backup.
5. **Diagnóstico de integridade** num banco gerado pela branch: zero achados fortes.
6. **Revisão independente**: `/code-review` (ou agente revisor) sobre o diff,
   e achados tratados ou justificados.
7. **Segurança**: sem segredos no diff; `security-guidance` sem achado alto pendente.
8. **Frontend** (quando mudou): carregou e o fluxo principal funciona
   (Playwright, na fase de frontend).
9. **Reversão**: como desfazer se der errado (revert do merge + backup de antes).
10. **Backup**: o responsável confirma um backup recente antes do merge.

## Saída

Parecer `APROVADO` / `APROVADO COM RESSALVAS` / `REPROVADO`, com a tabela
dos 10 itens e a evidência de cada um. O merge é decisão do responsável.
