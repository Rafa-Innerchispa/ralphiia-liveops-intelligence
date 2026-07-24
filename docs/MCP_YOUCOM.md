# You.com MCP — workshop steps

## Step 1 — API key

https://you.com/platform/api-keys → `YDC_API_KEY` / `YOUCOM_API_KEY` in `.env`

## Step 2 — Cursor MCP (`~/.cursor/mcp.json`)

```json
"you-com": {
  "type": "streamable-http",
  "url": "https://api.you.com/mcp",
  "headers": { "Authorization": "Bearer <YDC_API_KEY>" }
}
```

Regenerar desde LiveOps `.env`:

```bash
python scripts/sync_cursor_youcom_mcp.py
```

Reinicia Cursor (Remote SSH) para cargar **you-com**.

## Step 3a — MCP CLI balance

```bash
./scripts/youcom_mcp_balance.sh
```

## LiveOps API (same MCP, on server .4)

| URL | Uso |
|-----|-----|
| `http://100.94.99.12:8788/health` | MCP status + **you-balance** credits |
| `http://100.94.99.12:8788/api/youcom/balance` | Solo créditos |
| `http://100.94.99.12:8788/api/youcom/probe` | Search + Contents + Research |

Tools: `you-search`, `you-contents`, `you-research`, `you-balance` — alineado con **agent-skills** / slide “All in one place”.
