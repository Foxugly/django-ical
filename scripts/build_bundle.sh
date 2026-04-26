#!/usr/bin/env bash
# Build django-ical-deploy.tar.gz: source code + cleaned data + install scripts.
# Run from repo root with the venv active.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [ ! -d "import-clean" ]; then
    echo "error: import-clean/ not found. Run scripts/clean_import.py first." >&2
    exit 1
fi
if [ ! -f "import-clean/db.sqlite3" ]; then
    echo "error: import-clean/db.sqlite3 not found." >&2
    exit 1
fi

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

echo "==> Staging in $STAGE"
mkdir -p "$STAGE/django-ical"

# Source files (use rsync if available, else cp + find-prune).
RSYNC_OPTS=(
    -a
    --exclude=".git/"
    --exclude=".venv/"
    --exclude="venv/"
    --exclude="__pycache__/"
    --exclude="*.pyc"
    --exclude=".idea/"
    --exclude=".pytest_cache/"
    --exclude="import/"
    --exclude="import-clean/"
    --exclude="staticfiles/"
    --exclude="media/"
    --exclude="db.sqlite3"
    --exclude="db.sqlite3-*"
    --exclude=".env"
    --exclude="*.tar.gz"
)
if command -v rsync >/dev/null 2>&1; then
    rsync "${RSYNC_OPTS[@]}" ./ "$STAGE/django-ical/"
else
    # Fallback for environments without rsync (e.g. plain Git for Windows).
    # Selectively copy only the dirs/files we want, skipping problematic ones.
    INCLUDE_DIRS=(django_myical mycalendar deploy scripts static templates)
    INCLUDE_FILES=(manage.py requirements.txt requirements-dev.txt requirements.in requirements-dev.in common_tags.py .python-version .env.example pytest.ini conftest.py CLAUDE.md LICENSE)
    for d in "${INCLUDE_DIRS[@]}"; do
        [ -d "$d" ] && cp -r "$d" "$STAGE/django-ical/$d"
    done
    for f in "${INCLUDE_FILES[@]}"; do
        [ -f "$f" ] && cp "$f" "$STAGE/django-ical/$f"
    done
    # Prune pycache and pyc files
    find "$STAGE/django-ical" -type d -name "__pycache__" -prune -exec rm -rf {} +
    find "$STAGE/django-ical" -type f -name "*.pyc" -delete
fi

echo "==> Bundling cleaned data"
cp "import-clean/db.sqlite3" "$STAGE/django-ical/db.sqlite3"
cp -r "import-clean/media" "$STAGE/django-ical/media"

echo "==> Verifying install script is executable"
chmod +x "$STAGE/django-ical/deploy/install.sh"

OUT="$REPO_ROOT/django-ical-deploy.tar.gz"
echo "==> Creating $OUT"
tar -C "$STAGE" -czf "$OUT" django-ical/

# Strip the leading directory so users extract into /var/www/django_websites/django-ical/ directly.
# Re-pack with the contents at the top level instead of under django-ical/.
echo "==> Repacking without top-level dir (so tar xzf -C /var/www/django_websites/django-ical/ works)"
tar -C "$STAGE/django-ical" -czf "$OUT" .

echo
ls -la "$OUT"
echo "Done."
