#!/usr/bin/env bash
# Idempotent installer for django-ical on Ubuntu.
# Run after `git clone -b master https://github.com/Foxugly/django-ical.git $INSTALL_DIR`.
# Re-run after `git pull` to apply updates.
# Run as root: sudo bash deploy/install.sh
set -euo pipefail

INSTALL_DIR=/var/www/django_websites/django-ical
RUN_USER=django
RUN_GROUP=www-data
PYTHON=python3.12
DOMAIN=ical.foxugly.com

if [ ! -d "$INSTALL_DIR" ]; then
    echo "error: $INSTALL_DIR does not exist. Clone the repo first:" >&2
    echo "       sudo -u $RUN_USER git clone -b master https://github.com/Foxugly/django-ical.git $INSTALL_DIR" >&2
    exit 1
fi

if [ "$EUID" -ne 0 ]; then
    echo "error: run as root (sudo bash deploy/install.sh)" >&2
    exit 1
fi

if ! id -u "$RUN_USER" >/dev/null 2>&1; then
    echo "error: user '$RUN_USER' does not exist on this host." >&2
    echo "       Create it first: sudo useradd --system --no-create-home --shell /usr/sbin/nologin $RUN_USER" >&2
    echo "       Then add it to the $RUN_GROUP group: sudo usermod -aG $RUN_GROUP $RUN_USER" >&2
    exit 1
fi

echo "==> Installing OS packages"
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y \
    "$PYTHON" "${PYTHON}-venv" \
    nginx certbot python3-certbot-nginx

echo "==> Setting ownership on $INSTALL_DIR"
chown -R "$RUN_USER:$RUN_GROUP" "$INSTALL_DIR"

echo "==> Creating venv at $INSTALL_DIR/.venv"
if [ ! -d "$INSTALL_DIR/.venv" ]; then
    sudo -u "$RUN_USER" "$PYTHON" -m venv "$INSTALL_DIR/.venv"
fi
sudo -u "$RUN_USER" "$INSTALL_DIR/.venv/bin/pip" install --upgrade pip
sudo -u "$RUN_USER" "$INSTALL_DIR/.venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"

echo "==> Generating .env (if missing)"
if [ ! -f "$INSTALL_DIR/.env" ]; then
    SECRET=$(sudo -u "$RUN_USER" "$INSTALL_DIR/.venv/bin/python" -c \
        "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")
    sudo -u "$RUN_USER" tee "$INSTALL_DIR/.env" > /dev/null <<EOF
DJANGO_SECRET_KEY=$SECRET
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=$DOMAIN
DJANGO_SITE_DOMAIN=$DOMAIN
DJANGO_STATE=PROD
DATABASE_URL=sqlite:///$INSTALL_DIR/db.sqlite3
DJANGO_CSRF_TRUSTED_ORIGINS=https://$DOMAIN
DJANGO_MAX_UPLOAD_BYTES=1048576
DJANGO_EVENT_DURATION_MINUTES=90
DJANGO_SITE_TIMEZONE=Europe/Brussels
DJANGO_HSTS_SECONDS=2592000
EOF
    chmod 600 "$INSTALL_DIR/.env"
    chown "$RUN_USER:$RUN_GROUP" "$INSTALL_DIR/.env"
    echo "    wrote $INSTALL_DIR/.env (SECRET_KEY generated)"
else
    echo "    .env already exists; leaving as-is"
fi

echo "==> Running migrations and collectstatic"
cd "$INSTALL_DIR"
sudo -u "$RUN_USER" "$INSTALL_DIR/.venv/bin/python" manage.py migrate --noinput
sudo -u "$RUN_USER" "$INSTALL_DIR/.venv/bin/python" manage.py collectstatic --noinput

echo "==> Installing systemd unit"
cp "$INSTALL_DIR/deploy/django-ical.service" /etc/systemd/system/django-ical.service
systemctl daemon-reload
systemctl enable django-ical
systemctl restart django-ical
systemctl --no-pager --quiet is-active django-ical && echo "    django-ical active"

echo "==> Installing nginx site"
cp "$INSTALL_DIR/deploy/nginx.conf" /etc/nginx/sites-available/django-ical
ln -sf /etc/nginx/sites-available/django-ical /etc/nginx/sites-enabled/django-ical
nginx -t
systemctl reload nginx

echo
echo "==> install.sh done"
echo
echo "Next steps:"
echo "  1. Point DNS A record $DOMAIN to this server's public IP."
echo "  2. Once propagated, run:"
echo "       sudo certbot --nginx -d $DOMAIN --redirect --non-interactive --agree-tos -m <your-email>"
echo "  3. Smoke-test: curl -I https://$DOMAIN/"
