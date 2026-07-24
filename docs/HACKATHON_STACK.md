# Hackathon stack — You.com + Parasail

The event expects **both** sponsor APIs:

| Sponsor | Role in LiveOps | Endpoint |
|---------|-----------------|----------|
| **You.com** | Live web: Search, Contents, Research, Balance | MCP `https://api.you.com/mcp` |
| **Parasail** | GPU inference for Security + Arbitrator agents | OpenAI-compatible `https://api.parasail.io/v1` |

## You.com (Step 1–3 workshop)

- Key: https://you.com/platform/api-keys → `YDC_API_KEY` / `YOUCOM_API_KEY`
- MCP in Cursor: `~/.cursor/mcp.json` → `you-com`

## Parasail (partner slide — inference cloud)

- Key: https://www.saas.parasail.io/keys → `PARASAIL_API_KEY`
- Base URL: `https://api.parasail.io/v1`
- Default model: `meta-llama/Meta-Llama-3.1-8B-Instruct` (override with `PARASAIL_MODEL`)

```bash
# .env
PARASAIL_API_KEY=...
PARASAIL_MODEL=meta-llama/Meta-Llama-3.1-8B-Instruct
```

Probe:

```bash
curl -s http://100.94.99.12:8788/api/parasail/probe | jq .
```

## Agent map

1. **Observer** — RalfIA read-only (no LLM)
2. **Research** — **You.com** MCP/API
3. **Security Reviewer** — **Parasail** chat (rules fallback if no key)
4. **Arbitrator** — **Parasail** chat + You.com citations

Demo line: *“You.com grounds agents in live web data; Parasail runs the multi-agent reasoning on open models.”*
