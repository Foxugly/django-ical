#!/usr/bin/env bash
#
# django-ical — seed AWS SSM Parameter Store from a local .env
#
# Reads <env-file> line by line and creates/updates /ical/prod/<KEY> for each
# KEY=VALUE line. Keys in SECRET_KEYS are stored as SecureString (KMS); the rest
# as String. Idempotent (put-parameter --overwrite).
#
# Usage:   bash deploy/seed-parameter-store.sh [--dry-run] <env-file>
# Requires AWS creds with ssm:PutParameter on the prefix (the EC2 instance role
# is read-only, so run this from your workstation with admin/scoped creds).
set -euo pipefail

SECRET_KEYS=(
  SECRET_KEY
  DB_PASSWORD
  SENTRY_DSN
)

PREFIX="/ical/prod"
REGION="eu-west-1"
DRY_RUN=false
ENV_FILE=""

usage() { echo "Usage: $0 [--prefix /ical/prod] [--region eu-west-1] [--dry-run] <env-file>" >&2; exit 64; }

while [ $# -gt 0 ]; do
  case "$1" in
    --prefix)  PREFIX="$2"; shift 2 ;;
    --region)  REGION="$2"; shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    -h|--help) usage ;;
    -*)        echo "Unknown option: $1" >&2; usage ;;
    *)         ENV_FILE="$1"; shift ;;
  esac
done

[ -n "$ENV_FILE" ] || usage
[ -r "$ENV_FILE" ] || { echo "ERROR: env file '$ENV_FILE' not readable" >&2; exit 66; }

is_secret() { local k="$1"; for s in "${SECRET_KEYS[@]}"; do [ "$s" = "$k" ] && return 0; done; return 1; }

echo "=== Seeding $PREFIX/* from $ENV_FILE (region=$REGION, dry-run=$DRY_RUN) ==="
count=0; skipped=0
while IFS='' read -r line || [ -n "$line" ]; do
  line="${line#"${line%%[![:space:]]*}"}"
  line="${line%"${line##*[![:space:]]}"}"
  case "$line" in ""|\#*) continue ;; esac
  if [[ "$line" != *=* ]]; then echo "  WARN: skipping malformed: $line" >&2; skipped=$((skipped+1)); continue; fi
  KEY="${line%%=*}"; VALUE="${line#*=}"
  if [[ "$VALUE" =~ ^\"(.*)\"$ ]]; then VALUE="${BASH_REMATCH[1]}"; elif [[ "$VALUE" =~ ^\'(.*)\'$ ]]; then VALUE="${BASH_REMATCH[1]}"; fi
  TYPE="String"; is_secret "$KEY" && TYPE="SecureString"
  NAME="$PREFIX/$KEY"
  if [ "$DRY_RUN" = true ]; then
    [ "$TYPE" = "SecureString" ] && echo "  DRY: $NAME -> $TYPE (redacted)" || echo "  DRY: $NAME -> $TYPE = $VALUE"
  else
    aws ssm put-parameter --region "$REGION" --name "$NAME" --value "$VALUE" --type "$TYPE" --overwrite --output text >/dev/null
    echo "  OK : $NAME ($TYPE)"
  fi
  count=$((count+1))
done < "$ENV_FILE"
echo ""
echo "Done — $count parameter(s) processed, $skipped skipped."
