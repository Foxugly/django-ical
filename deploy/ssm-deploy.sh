#!/usr/bin/env bash
#
# django-ical — SSM deploy step (backend-only, run as the django user).
#
# Called from the deploy workflow via:
#   aws ssm send-command --document-name AWS-RunShellScript \
#     --parameters 'commands=["sudo -u django bash .../deploy/ssm-deploy.sh"]'
#
# The git reset to origin/main and the root-side install of units / nginx /
# env-fetch restart already happened (earlier ordered steps of the deploy job in ci.yml).
# Here we only: refresh deps, migrate, collectstatic, restart the app service.
set -euo pipefail
umask 027

REPO_DIR=/var/www/django_websites/django-ical
VENV="$REPO_DIR/.venv"
cd "$REPO_DIR"

# Load runtime secrets so manage.py (migrate) sees DATABASE_URL / SECRET_KEY.
# In prod there is no on-disk .env anymore — the env lives in tmpfs, written by
# ical-env-fetch.service. The file is 640 django:www-data, so the django
# user (owner) can read it.
# Read as KEY=VALUE lines, like systemd's EnvironmentFile, never executed as shell:
# a value with ( ) ; $ or spaces (SECRET_KEY) made `. /run/ical/.env` abort the
# script before pip install (deploys then silently kept the old dependencies).
if [ -r /run/ical/.env ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in ''|'#'*) continue ;; esac
    if [[ "$line" == [A-Za-z_]*=* ]]; then export "$line"; fi
  done < /run/ical/.env
fi

echo "[1/4] pip install"
# requirements.txt is a hash-pinned lock (uv pip compile from requirements.in),
# the exact set CI tested. A plain `pip install -r` of version ranges never
# upgraded what was already installed, so prod silently missed patch/security
# releases. --require-hashes refuses anything not in the lock, --no-deps refuses
# to resolve anything missing from it, and pip check fails on an incoherent set.
"$VENV/bin/pip" install --quiet --no-input --require-hashes --no-deps -r requirements.txt
"$VENV/bin/pip" check

echo "[2/4] migrate"
"$VENV/bin/python" manage.py migrate --noinput

echo "[3/4] collectstatic"
"$VENV/bin/python" manage.py collectstatic --noinput

echo "[4/4] restart ical-gunicorn"
# Absolute /bin/systemctl so the sudoers Cmnd match is literal (usrmerge).
sudo /bin/systemctl restart ical-gunicorn

echo "=== django-ical deploy complete ==="
