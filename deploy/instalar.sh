#!/usr/bin/env bash
# Instala o Taldo Manager numa VPS Ubuntu (ex.: Hostinger KVM 1), do zero.
#
#   curl -fsSL https://raw.githubusercontent.com/isaque-souza/TaldoManager/main/deploy/instalar.sh | sudo bash
#   (ou, com domínio próprio: ... | sudo DOMINIO=taldo.seudominio.com bash)
#
# Sem DOMINIO, usa <ip-com-hífens>.sslip.io, que já aponta para o IP da VPS
# e ganha HTTPS do Caddy do mesmo jeito. Pode rodar de novo sem problema.
set -euo pipefail

REPO=https://github.com/isaque-souza/TaldoManager.git
APP=/opt/taldo           # código
DADOS=/var/lib/taldo     # banco e backups (fora do código: o git pull não toca)

if [ "$(id -u)" -ne 0 ]; then echo "Rode com sudo."; exit 1; fi

IP=$(curl -fsS4 https://api.ipify.org)
DOMINIO=${DOMINIO:-${IP//./-}.sslip.io}

echo "==> Pacotes"
apt-get update -q
apt-get install -y -q python3 python3-venv git sqlite3 curl debian-keyring \
  debian-archive-keyring apt-transport-https gnupg ufw
if ! command -v caddy >/dev/null; then
  curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/gpg.key \
    | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt \
    > /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -q && apt-get install -y -q caddy
fi

echo "==> Usuário e pastas"
id taldo >/dev/null 2>&1 || useradd --system --home "$APP" --shell /usr/sbin/nologin taldo
mkdir -p "$DADOS/backups"

echo "==> Código"
if [ -d "$APP/.git" ]; then
  sudo -u taldo git -C "$APP" pull --ff-only
else
  git clone "$REPO" "$APP"
fi
python3 -m venv "$APP/venv"
"$APP/venv/bin/pip" install -q -r "$APP/backend/requirements.txt"
chown -R taldo:taldo "$APP" "$DADOS"

echo "==> Serviço"
install -m 644 "$APP/deploy/taldo.service" /etc/systemd/system/taldo.service
systemctl daemon-reload
systemctl enable --now taldo
systemctl restart taldo

echo "==> HTTPS ($DOMINIO)"
sed "s/{DOMINIO}/$DOMINIO/" "$APP/deploy/Caddyfile" > /etc/caddy/Caddyfile
systemctl reload caddy || systemctl restart caddy

echo "==> Firewall (SSH, HTTP, HTTPS)"
ufw allow OpenSSH >/dev/null
ufw allow 80/tcp >/dev/null
ufw allow 443/tcp >/dev/null
ufw --force enable >/dev/null

echo "==> Backup diário do banco (guarda 14 dias)"
cat > /etc/cron.daily/taldo-backup <<CRON
#!/bin/sh
sqlite3 $DADOS/taldo_manager.db ".backup '$DADOS/backups/taldo-\$(date +%F).db'"
find $DADOS/backups -name 'taldo-*.db' -mtime +14 -delete
CRON
chmod 755 /etc/cron.daily/taldo-backup

echo
echo "Pronto! O jogo está em: https://$DOMINIO"
echo "(o certificado HTTPS pode levar até 1 minuto na primeira vez)"
