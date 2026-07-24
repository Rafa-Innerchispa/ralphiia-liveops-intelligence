# Deploy on Render (keep ngrok as fallback)

Public URL goal: stable **Render Web Service** for judges. **ngrok** (`LIVEOPS_PUBLIC_URL`) stays documented as fallback until Render is verified.

## Human steps (≤5)

1. Open [dashboard.render.com](https://dashboard.render.com) → **New** → **Blueprint** (or **Web Service**).
2. Connect GitHub → select **`Rafa-Innerchispa/ralphiia-liveops-intelligence`** → branch **`hackathon/youcom-liveops-20260724`**.
3. If Blueprint: approve `render.yaml`. If Web Service: build `pip install -r requirements.txt`, start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, health `/health`.
4. **Environment** → add secrets (names only — paste values in dashboard, never in chat):

   | Variable | Required | Purpose |
   |----------|----------|---------|
   | `YOUCOM_API_KEY` | Yes (demo) | You.com MCP research |
   | `PARASAIL_API_KEY` | Yes (demo) | Security + Arbitrator |
   | `ONE_SECRET` | Yes (act 3) | One MCP → GitHub issue |
   | `GITHUB_REPO_OWNER` | Yes | e.g. `Rafa-Innerchispa` |
   | `GITHUB_REPO_NAME` | Yes | `ralphiia-liveops-intelligence` |
   | `GITHUB_TOKEN` | Fallback | If One MCP fails (PAT `repo` scope) |
   | `RALFIA_STATUS_URL` | Hybrid | Public HTTPS URL to **read-only** RalfIA `/status` (not LAN IP) |

5. Deploy → open `https://<service>.onrender.com/health` → run demo **1 · Check Live Status** then **2 · Investigate**.

## Hybrid honesty

- **On Render:** Observer is **live** only if `RALFIA_STATUS_URL` points to a reachable bridge; otherwise UI shows **Fallback fixture** (labeled).
- **Ollama** on home LAN is **not** reachable from Render unless you expose a secured endpoint; local/ngrok demo keeps full stack.

## Verify

```bash
curl -s https://YOUR-SERVICE.onrender.com/health | jq .ok
curl -s https://YOUR-SERVICE.onrender.com/api/deployment | jq .
```

SSE: POST `/api/analyze/stream` with `run_mode` `status_only` or `investigate`.
