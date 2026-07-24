# LiveOps read-only bridge (8790)

Minimal service for **Render → home lab** without LAN IPs or full RalfIA payloads.

## Endpoints (Bearer required except `/health`)

| Method | Path | Auth |
|--------|------|------|
| GET | `/health` | none |
| GET | `/liveops-bridge/status` | `Authorization: Bearer $RALFIA_STATUS_TOKEN` |

Responses are sanitized (`source: live_ralfia_bridge`). No mutations, no arbitrary paths.

## Local run

```bash
systemctl --user enable --now ralfia-liveops-bridge.service
./scripts/smoke_bridge.sh
```

Tokens: set **`LIVEOPS_BRIDGE_TOKEN`** and **`RALFIA_STATUS_TOKEN`** to the same value in `.env` (never commit).

## Cloudflare (primary)

Ingress on **opportunityops** tunnel (`~/.cloudflared/opportunityops.yml`):

- `liveops-bridge.pcdoctor.ai` → `http://127.0.0.1:8790`

Service: `systemctl --user restart opportunityops-cloudflared`

## ngrok (fallback)

Public gateway `:5188` proxies `/liveops-bridge/*` → `:8790`:

- `https://<ngrok-host>/liveops-bridge/health`
- `https://<ngrok-host>/liveops-bridge/liveops-bridge/status` (note path prefix)

After editing `public_gateway.py`, restart **`swarm-public-gateway`** (requires sudo on this host).

## Render

Set in Dashboard:

- `RALFIA_STATUS_URL=https://liveops-bridge.pcdoctor.ai/liveops-bridge/status`
- `RALFIA_STATUS_TOKEN=<same as bridge .env>`

UI shows **`Live · RalfIA bridge`** only when authenticated probe + schema validate. Failures show **`Unavailable`**, not silent fixture.

## Act 3 (GitHub)

**One MCP** if `ONE_SECRET` is set; else **GitHub API** if `GITHUB_TOKEN` is set (ngrok/local demo path unchanged).
