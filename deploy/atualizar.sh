#!/usr/bin/env bash
# Põe a versão nova da main no ar:  sudo bash /opt/taldo/deploy/atualizar.sh
# O banco fica em /var/lib/taldo e não é tocado; as migrações rodam sozinhas
# quando o serviço sobe.
set -euo pipefail
APP=/opt/taldo
sqlite3 /var/lib/taldo/taldo_manager.db ".backup '/var/lib/taldo/backups/antes-de-atualizar.db'" 2>/dev/null || true
sudo -u taldo git -C "$APP" pull --ff-only
sudo -u taldo "$APP/venv/bin/pip" install -q -r "$APP/backend/requirements.txt"
systemctl restart taldo
echo "Atualizado: $(git -C "$APP" log --oneline -1)"
