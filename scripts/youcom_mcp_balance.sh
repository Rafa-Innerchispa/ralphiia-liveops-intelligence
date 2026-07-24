#!/usr/bin/env bash
# You.com workshop Step 3a — MCP you-balance via CLI (reads YDC_API_KEY from env)
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -f .env ]]; then set -a; source .env; set +a; fi
: "${YDC_API_KEY:=${YOUCOM_API_KEY:-}}"
if [[ -z "$YDC_API_KEY" ]]; then
  echo "Set YDC_API_KEY in .env (https://you.com/platform/api-keys)" >&2
  exit 1
fi
curl -sS -X POST "https://api.you.com/mcp" \
  -H "Authorization: Bearer ${YDC_API_KEY}" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"you-balance","arguments":{}}}' \
  | python3 -m json.tool
