#!/usr/bin/env bash
# Smoke tests for LiveOps bridge (no secret values printed).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source "$ROOT/venv/bin/activate" 2>/dev/null || true
set -a
# shellcheck disable=SC1091
[ -f "$ROOT/.env" ] && . "$ROOT/.env"
set +a
BASE="${LIVEOPS_BRIDGE_BASE:-http://127.0.0.1:8790}"
TOKEN="${RALFIA_STATUS_TOKEN:-${LIVEOPS_BRIDGE_TOKEN:-}}"

echo "== GET /health (no auth) =="
curl -sS -o /tmp/lb-health.json -w "HTTP %{http_code}\n" "$BASE/health"
python3 -c "import json; d=json.load(open('/tmp/lb-health.json')); assert d.get('ok') is True"

echo "== GET /liveops-bridge/status without token (expect 401) =="
code=$(curl -sS -o /dev/null -w "%{http_code}" "$BASE/liveops-bridge/status")
test "$code" = "401"

echo "== POST /liveops-bridge/status (expect 405) =="
code=$(curl -sS -o /dev/null -w "%{http_code}" -X POST "$BASE/liveops-bridge/status")
test "$code" = "405"

echo "== GET unknown (expect 404) =="
code=$(curl -sS -o /dev/null -w "%{http_code}" "$BASE/nope")
test "$code" = "404"

if [ -z "$TOKEN" ]; then
  echo "SKIP authenticated probe — set RALFIA_STATUS_TOKEN in .env"
  exit 0
fi

echo "== GET /liveops-bridge/status with bearer =="
curl -sS -o /tmp/lb-status.json -w "HTTP %{http_code}\n" \
  -H "Authorization: Bearer $TOKEN" \
  "$BASE/liveops-bridge/status"
python3 -c "import json; d=json.load(open('/tmp/lb-status.json')); assert d.get('source')=='live_ralfia_bridge'; assert 'verified_at' in d"

echo "== wrong token (expect 403) =="
code=$(curl -sS -o /dev/null -w "%{http_code}" -H "Authorization: Bearer wrong" "$BASE/liveops-bridge/status")
test "$code" = "403"

echo "PASS bridge smoke"
