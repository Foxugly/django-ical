#!/usr/bin/env bash
# Import cleaned prod data into the install.
# Usage: sudo bash deploy/import-data.sh /path/to/import-clean.tar.gz
#
# The tarball must contain at its top level:
#   db.sqlite3
#   media/
# Built locally from `scripts/clean_import.py` output:
#   python scripts/clean_import.py --src-dir <prod-backup> --dst-dir import-clean
#   tar czf import-clean.tar.gz -C import-clean .
set -euo pipefail

INSTALL_DIR=/var/www/django_websites/django-ical
RUN_USER=django
RUN_GROUP=www-data

if [ "$EUID" -ne 0 ]; then
    echo "error: run as root (sudo bash deploy/import-data.sh <tarball>)" >&2
    exit 1
fi

if [ $# -ne 1 ]; then
    echo "usage: sudo bash deploy/import-data.sh /path/to/import-clean.tar.gz" >&2
    exit 1
fi

TARBALL="$1"
if [ ! -f "$TARBALL" ]; then
    echo "error: $TARBALL not found" >&2
    exit 1
fi

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

echo "==> Extracting $TARBALL to $STAGE"
tar xzf "$TARBALL" -C "$STAGE"

if [ ! -f "$STAGE/db.sqlite3" ]; then
    echo "error: tarball does not contain db.sqlite3 at top level" >&2
    exit 1
fi
if [ ! -d "$STAGE/media" ]; then
    echo "error: tarball does not contain media/ at top level" >&2
    exit 1
fi

echo "==> Stopping django-ical service"
systemctl stop django-ical 2>/dev/null || true

if [ -f "$INSTALL_DIR/db.sqlite3" ]; then
    BACKUP="$INSTALL_DIR/db.sqlite3.before-import-$(date +%Y%m%d-%H%M%S)"
    echo "==> Backing up existing db.sqlite3 to $BACKUP"
    cp -p "$INSTALL_DIR/db.sqlite3" "$BACKUP"
fi

echo "==> Installing db.sqlite3 and media/"
mv "$STAGE/db.sqlite3" "$INSTALL_DIR/db.sqlite3"
rm -rf "$INSTALL_DIR/media"
mv "$STAGE/media" "$INSTALL_DIR/media"
chown "$RUN_USER:$RUN_GROUP" "$INSTALL_DIR/db.sqlite3"
chown -R "$RUN_USER:$RUN_GROUP" "$INSTALL_DIR/media"

echo "==> Running migrations against imported DB"
cd "$INSTALL_DIR"
sudo -u "$RUN_USER" "$INSTALL_DIR/.venv/bin/python" manage.py migrate --noinput

echo "==> Restarting django-ical"
systemctl start django-ical
systemctl --no-pager --quiet is-active django-ical && echo "    django-ical active"

echo
echo "==> import-data.sh done"
