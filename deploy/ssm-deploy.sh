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
# The venv must run on $PYTHON (deadsnakes python3.14, root-owned in /usr/bin).
# A venv on another version is rebuilt at its final path — never built
# elsewhere and moved, since console-script shebangs (.venv/bin/gunicorn, used
# by the unit) hard-code the venv path. The old one is kept as .venv.prev and
# put back if the rebuild fails.
PYTHON=/usr/bin/python3.14
PY_WANT="$("$PYTHON" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
PY_HAVE="$("$VENV/bin/python" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || echo none)"
if [ "$PY_HAVE" != "$PY_WANT" ]; then
  echo "  rebuilding the venv: Python $PY_HAVE -> $PY_WANT..."
  rm -rf "$VENV.prev"
  if [ -e "$VENV" ]; then mv "$VENV" "$VENV.prev"; fi
  if ! { "$PYTHON" -m venv "$VENV" \
         && "$VENV/bin/pip" install --quiet --no-input --require-hashes --no-deps -r requirements.txt \
         && "$VENV/bin/pip" check; }; then
    echo "ERROR: venv rebuild failed; restoring the previous venv." >&2
    rm -rf "$VENV"
    if [ -e "$VENV.prev" ]; then mv "$VENV.prev" "$VENV"; fi
    exit 1
  fi
fi
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
