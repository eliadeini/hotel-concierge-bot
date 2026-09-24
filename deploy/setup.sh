#!/usr/bin/env bash
# One-time server bootstrap. Safe to re-run (idempotent).
#
# Usage: deploy/setup.sh <domain> <email>
#   domain  e.g. concierge.example.com — must already resolve to this
#           server's public IP before you run the certbot command this
#           script prints at the end.
#   email   used by Let's Encrypt for renewal/expiry notices.
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 <domain> <email>" >&2
  exit 1
fi

DOMAIN="$1"
EMAIL="$2"
SERVICE_NAME="concierge"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$REPO_DIR/.venv"
EXPECTED_REPO_DIR="/home/ubuntu/hotel-concierge-bot"

echo "==> Repo: $REPO_DIR"
if [[ "$REPO_DIR" != "$EXPECTED_REPO_DIR" ]]; then
  echo "WARNING: deploy/concierge.service hardcodes $EXPECTED_REPO_DIR," >&2
  echo "but this repo lives at $REPO_DIR. Edit deploy/concierge.service to match" >&2
  echo "before continuing, or the service will fail to start." >&2
fi

if [[ ! -f "$REPO_DIR/.env" ]]; then
  echo "ERROR: $REPO_DIR/.env is missing." >&2
  echo "Copy .env.example to .env and fill in real values first:" >&2
  echo "    cp $REPO_DIR/.env.example $REPO_DIR/.env" >&2
  exit 1
fi

echo "==> Installing system packages"
sudo apt-get update
# build-essential/pkg-config/libssl-dev/libffi-dev/cargo/rustc: fallback in
# case cryptography/pydantic-core have no prebuilt aarch64 wheel yet for
# this Ubuntu release's Python — lets pip compile from source instead of
# failing outright.
sudo apt-get install -y \
  python3-venv python3-pip git \
  build-essential pkg-config libssl-dev libffi-dev cargo rustc \
  apache2 certbot python3-certbot-apache

echo "==> Creating virtualenv and installing Python dependencies"
if [[ ! -d "$VENV_DIR" ]]; then
  python3 -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -r "$REPO_DIR/requirements.txt"

echo "==> Installing systemd service"
sudo install -m 644 "$SCRIPT_DIR/concierge.service" "/etc/systemd/system/${SERVICE_NAME}.service"
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

echo "==> Enabling required Apache modules"
sudo a2enmod proxy proxy_http headers rewrite

echo "==> Installing Apache site config for $DOMAIN"
sed "s/DOMAIN/$DOMAIN/g" "$SCRIPT_DIR/apache-concierge.conf" | sudo tee "/etc/apache2/sites-available/${SERVICE_NAME}.conf" > /dev/null
sudo a2dissite 000-default >/dev/null 2>&1 || true
sudo a2ensite "$SERVICE_NAME"
sudo apache2ctl configtest
sudo systemctl reload apache2

echo
echo "==> Setup complete. Service status:"
sudo systemctl --no-pager status "$SERVICE_NAME" || true

echo
echo "==> Once DNS for $DOMAIN points at this server, issue the HTTPS certificate with:"
echo
echo "    sudo certbot --apache -d $DOMAIN -m $EMAIL --agree-tos --redirect"
echo
