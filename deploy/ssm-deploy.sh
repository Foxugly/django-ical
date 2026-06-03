#!/usr/bin/env bash
#
# django-ical — SSM deploy step (backend-only, run as the django user).
#
# Called from the deploy workflow via:
#   aws ssm send-command --document-name AWS-RunShellScript \
#     --parameters 'commands=["sudo -u django bash .../deploy/ssm-deploy.sh"]'
#
# The git reset to origin/main and the root-side install of units / nginx /
# env-fetch restart already happened (earlier ordered steps in deploy.yml).
# Here we only: refresh deps, migrate, collectstatic, restart the app service.
set -euo pipefail
umask 027

REPO_DIR=/var/www/django_websites/django-ical
VENV="$REPO_DIR/.venv"
cd "$REPO_DIR"

# Load runtime secrets so manage.py (migrate) sees DATABASE_URL / SECRET_KEY.
# In prod there is no on-disk .env anymore — the env lives in tmpfs, written by
# django-ical-env-fetch.service. The file is 640 django:www-data, so the django
# user (owner) can read it.
if [ -r /run/ical/.env ]; then
  set -a
  . /run/ical/.env
  set +a
fi

echo "[1/4] pip install"
"$VENV/bin/pip" install --quiet --no-input -r requirements.txt

echo "[2/4] migrate"
"$VENV/bin/python" manage.py migrate --noinput

echo "[3/4] collectstatic"
"$VENV/bin/python" manage.py collectstatic --noinput

echo "[4/4] restart django-ical"
# Absolute /bin/systemctl so the sudoers Cmnd match is literal (usrmerge).
sudo /bin/systemctl restart django-ical

echo "=== django-ical deploy complete ==="
