#!/usr/bin/env bash
# Chamado pelo cron a cada 5 min: se a main andou no GitHub, atualiza.
#   */5 * * * * bash ~/taldo/deploy/auto-atualizar.sh >> ~/taldo-deploy.log 2>&1
set -euo pipefail
cd "$(dirname "$0")/.."
# um de cada vez: um build demorado não se sobrepõe ao próximo cron
exec 9>/tmp/taldo-deploy.lock
flock -n 9 || exit 0
git fetch -q origin main
[ "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)" ] && exit 0
echo "== $(date '+%F %T') atualizando para $(git log --oneline -1 origin/main)"
bash deploy/atualizar.sh
