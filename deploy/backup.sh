#!/usr/bin/env bash
# Cópia consistente do banco para ~/taldo-backups (guarda 14 dias).
#   bash ~/taldo/deploy/backup.sh [nome]     (o cron diário chama sem nome)
set -euo pipefail
DESTINO=~/taldo-backups
NOME=${1:-taldo-$(date +%F)}
mkdir -p "$DESTINO"
docker exec taldo-app python -c "
import sqlite3
origem = sqlite3.connect('/dados/taldo_manager.db')
origem.backup(sqlite3.connect('/dados/backup.db'))
"
docker cp taldo-app:/dados/backup.db "$DESTINO/$NOME.db"
docker exec taldo-app rm -f /dados/backup.db
find "$DESTINO" -name 'taldo-*.db' -mtime +14 -delete
echo "Backup: $DESTINO/$NOME.db"
