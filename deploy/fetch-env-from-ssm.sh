#!/usr/bin/env bash
#
# django-ical — fetch env vars from SSM Parameter Store into a tmpfs .env
#
# Invoked at boot by django-ical-env-fetch.service. Pulls every parameter
# under $PREFIX (default /ical/prod) into a fresh $OUT_FILE
# (default /run/ical/.env), then hands ownership to the django service user.
#
# /run is tmpfs → the file never lands on EBS and is re-fetched each boot.
# Atomic: writes to $OUT_FILE.tmp then `mv -f`. Auth: EC2 instance role via
# IMDS (ssm:GetParametersByPath on the prefix) — no credentials on disk.
set -euo pipefail

PREFIX="${ICAL_SSM_PREFIX:-/ical/prod}"
REGION="${ICAL_SSM_REGION:-eu-west-1}"
OUT_DIR="${ICAL_ENV_DIR:-/run/ical}"
OUT_FILE="${ICAL_ENV_FILE:-$OUT_DIR/.env}"
OWNER="${ICAL_ENV_OWNER:-django:www-data}"

echo "[fetch-env] prefix=$PREFIX region=$REGION out=$OUT_FILE"

mkdir -p "$OUT_DIR"
chmod 750 "$OUT_DIR"
chown root:www-data "$OUT_DIR"

TMP_FILE="$OUT_FILE.tmp"
: > "$TMP_FILE"
chmod 640 "$TMP_FILE"

OUT=$(aws ssm get-parameters-by-path \
  --region "$REGION" \
  --path "$PREFIX" \
  --recursive \
  --with-decryption \
  --output json)

python3 -c '
import json, sys
prefix, out_path, payload = sys.argv[1], sys.argv[2], sys.argv[3]
data = json.loads(payload)
n = 0
with open(out_path, "a", encoding="utf-8") as f:
    for p in data.get("Parameters", []):
        name = p["Name"]
        key = name[len(prefix) + 1:] if name.startswith(prefix + "/") else name.rsplit("/", 1)[-1]
        value = p["Value"]
        if "\n" in value or "\r" in value:
            print(f"ERROR: value of {key} contains a newline character", file=sys.stderr)
            sys.exit(2)
        f.write(f"{key}={value}\n")
        n += 1
print(f"[fetch-env] wrote {n} entries to staging file", file=sys.stderr)
' "$PREFIX" "$TMP_FILE" "$OUT"

# Refuse to swap in an empty file (likely IAM regression / wrong prefix);
# keep the previous .env so downstream services keep last-known-good config.
COUNT=$(grep -c '=' "$TMP_FILE" || true)
if [ "$COUNT" -eq 0 ]; then
  echo "ERROR: no parameters found under $PREFIX — refusing to overwrite live .env" >&2
  rm -f "$TMP_FILE"
  exit 3
fi

chown "$OWNER" "$TMP_FILE"
chmod 640 "$TMP_FILE"
mv -f "$TMP_FILE" "$OUT_FILE"
echo "[fetch-env] $OUT_FILE ready ($COUNT entries, owner=$OWNER, mode=0640)"
