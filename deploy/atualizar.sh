#!/usr/bin/env bash
# Põe a versão nova da main no ar (na VPS):  bash ~/taldo/deploy/atualizar.sh
# Faz backup do banco antes; as migrações rodam sozinhas quando o container sobe.
set -euo pipefail
cd "$(dirname "$0")/.."
bash deploy/backup.sh antes-de-atualizar || true
git pull --ff-only
docker compose -f deploy/docker-compose.yml up -d --build
echo "Atualizado: $(git log --oneline -1)"
