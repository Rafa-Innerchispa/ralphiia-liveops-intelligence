# RalphiIA LiveOps Intelligence

**Ask your infrastructure. Get evidence, not guesses.**

Evidence-first LiveOps for distributed ops teams: live read-only probes, web-backed research with citations, independent security review, human approval, and optional incident tracking on GitHub via **One MCP** — **no production mutations** (`dry_run=true`).

| | |
|---|---|
| **Hackathon** | You.com Agentic Hackathon · San Francisco · July 2026 |
| **Track** | **Multi-Agent Systems** / Best Use of You.com API |
| **Public app (Render)** | https://ralphiia-liveops-intelligence.onrender.com |
| **Repository** | https://github.com/Rafa-Innerchispa/ralphiia-liveops-intelligence |
| **Branch** | `hackathon/youcom-liveops-20260724` |
| **Local port** | **8788** (isolated from production `raphiia-openai`) |

---

## Purpose

Operators describe incidents in natural language. The pipeline separates:

- **Observed live facts** (RalfIA bridge / status API)
- **Web evidence** (You.com MCP with citations)
- **Model hypotheses** (local + research agents — not verified facts)
- **Reviewed recommendations** (Parasail security + arbitrator)
- **Human-approved actions** (checkpoint only until GitHub issue creation)

The UI is a single-page command center with chat, SSE timeline, citation cards, and three demo acts (status → investigate → incident).

---

## Architecture

```
Operator prompt
       │
       ▼
┌──────────────┐     read-only GET      ┌─────────────────────────┐
│   Observer   │ ─────────────────────► │ RalfIA bridge / :8101   │
└──────────────┘                        └─────────────────────────┘
       │
       ▼
┌──────────────┐     Ollama (optional)    ┌─────────────────────────┐
│ Local Analyst│ ─────────────────────► │ phi3.5 / catalog models │
└──────────────┘                        └─────────────────────────┘
       │
       ▼
┌──────────────┐     You.com MCP          ┌─────────────────────────┐
│   Research   │ ─────────────────────► │ you-search / contents / │
│              │                        │ you-research            │
└──────────────┘                        └─────────────────────────┘
       │
       ▼
┌──────────────┐     Parasail API         ┌─────────────────────────┐
│   Security   │ ─────────────────────► │ parasail-ui-tars-1p5-7b │
│   Reviewer   │                        │ (blocks unsafe actions) │
└──────────────┘                        └─────────────────────────┘
       │
       ▼
┌──────────────┐     Parasail API         structured JSON answer
│  Arbitrator  │ ─────────────────────► (parsed → clean markdown)
└──────────────┘
       │
       ▼
┌──────────────┐     UI only              Approve / Reject / Deeper
│    Human     │ ─────────────────────► (no restart/recover/delete)
└──────────────┘
       │
       ▼ (after Approve)
┌──────────────┐     One MCP              ┌─────────────────────────┐
│  One → GH    │ ─────────────────────► │ create issue (OAuth     │
│  Issue       │                        │ connection in One)      │
└──────────────┘                        └─────────────────────────┘
```

**Stack:** Python 3.12 · **FastAPI** · **Server-Sent Events** (`/api/analyze/stream`) · static HTML/JS UI · optional **Render** deploy via `render.yaml`.

---

## Integrations (what we use in the hackathon)

### RalfIA live bridge (operational truth)

Render cannot reach private lab IPs directly. A **read-only HTTPS bridge** exposes sanitized status:

- Typical URL path: `https://liveops-bridge.pcdoctor.ai/liveops-bridge/status`
- Auth: bearer token via env (see table below)
- Optional **Cloudflare Access** headers for server-to-server calls from Render
- Labels in UI: live bridge vs unavailable vs explicit fixture — never mixed with stale demo narratives

### You.com MCP (web evidence)

- **Transport:** `YOUCOM_TRANSPORT=mcp` (authenticated MCP at `https://api.you.com/mcp`)
- **Tools used:** `you-search`, `you-contents`, `you-research` (via project adapter)
- **API key:** `YDC_API_KEY` or `YOUCOM_API_KEY` from [You.com Platform](https://you.com/platform/api-keys)
- **Act 1 (Live Status):** may skip You.com when the question is status-only
- **Act 2 (Investigate):** runs research; citations appear in cards, metrics, and GitHub issue preview

### Parasail (independent review)

- **Roles:** Security Reviewer (blocks restart/recover/delete) + Arbitrator (final recommendation)
- **Default model:** `parasail-ui-tars-1p5-7b`
- **Base URL:** `https://api.parasail.io/v1`
- **Key:** `PARASAIL_API_KEY` from [Parasail SaaS keys](https://www.saas.parasail.io/keys)
- Invalid JSON from the model (e.g. unquoted `risk_level: High`) is repaired before display

### Local Ollama (optional private analyst)

- When the app runs on the lab network, **Local Analyst** calls Ollama (e.g. `phi3.5:3.8b`)
- From Render: usually **unavailable** (expected); pipeline continues with Observer + You.com + Parasail

### One MCP → GitHub issue (Act 3)

- **Server API:** `https://api.withone.ai/v1/passthrough/...` with headers **`X-One-Secret`** (`sk_live_…` from [API keys](https://app.withone.ai/settings/api-keys)) and **`X-One-Connection-Key`**
- **Not** the remote MCP URL `https://mcp.withone.ai/mcp` — that endpoint is **OAuth-only** (Cursor/ChatGPT), so `sk_live` keys always return **401** there
- **Repository:** `GITHUB_REPO_OWNER` + `GITHUB_REPO_NAME` (defaults in code: `Rafa-Innerchispa` / `ralphiia-liveops-intelligence`)
- **Flow:** Run Investigate → **Approve** (records checkpoint) → **Create GitHub Incident** → edit preview → **Create** → real `html_url` with `via: one_mcp`
- **No silent PAT fallback** in production path: issues are created through One only

### Human approval checkpoint

- Approve/Reject records a **dry-run audit** entry on the session result
- **Create GitHub Incident** is disabled until Approve succeeds
- `/api/incident/create` requires `human_approval=approved` and prior `human_decision=approve`

### Opsera (development evidence)

**Opsera Agents** is used in **Cursor during development** (pre-commit review). It is **not** a runtime pipeline agent. See `GET /api/build-review` and `data/opsera_build_review.json`.

---

## Demo flow (three acts)

| Act | UI | Pipeline |
|-----|-----|----------|
| **1 · Live Status** | “Check Live Status” | Observer (+ Local Analyst if available). You.com skipped when appropriate. |
| **2 · Investigate** | “Investigate with Live Sources” | Full chain: Observer → Local → You.com → Parasail Security → Parasail Arbitrator → Human awaiting approval. |
| **3 · GitHub incident** | Approve → Create GitHub Incident | Editable preview → One MCP creates issue in configured repo. |

Suggested pitch line: *“We observe live infrastructure read-only, research current sources with You.com, Parasail reviews the recommendation, a human approves, and One opens a tracking issue on GitHub — without changing production.”*

More detail: [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) · [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · [docs/DEPLOY_RENDER.md](docs/DEPLOY_RENDER.md) · [docs/BRIDGE.md](docs/BRIDGE.md)

---

## Environment variables

**Never commit secret values.** Set in `.env` locally or in the Render Dashboard.

| Variable | Purpose |
|----------|---------|
| `YDC_API_KEY` / `YOUCOM_API_KEY` | You.com authenticated MCP / API |
| `YOUCOM_TRANSPORT` | `mcp` (recommended), `rest`, or `auto` |
| `PARASAIL_API_KEY` | Parasail inference |
| `PARASAIL_MODEL` | Default `parasail-ui-tars-1p5-7b` |
| `PARASAIL_BASE_URL` | Default `https://api.parasail.io/v1` |
| `LIVEOPS_DATA_MODE` | `auto` \| `live` \| `fixture` |
| `LIVEOPS_PORT` | Local bind port (default `8788`) |
| `DEPLOY_SURFACE` | `local` or `render` (metadata) |
| `RALFIA_STATUS_URL` | HTTPS read-only status/bridge URL |
| `RALFIA_STATUS_TOKEN` | Bearer token for bridge (alias: `LIVEOPS_BRIDGE_TOKEN`) |
| `CF_ACCESS_CLIENT_ID` | Optional Cloudflare Access (Render → bridge) |
| `CF_ACCESS_CLIENT_SECRET` | Optional Cloudflare Access secret |
| `ONE_SECRET` | One MCP server Bearer token |
| `ONE_GITHUB_CONNECTION_KEY` | One GitHub connection key for `execute_one_action` |
| `GITHUB_REPO_OWNER` | GitHub org/user for issues |
| `GITHUB_REPO_NAME` | Repository name for issues |
| `LIVEOPS_PUBLIC_URL` | Public base URL for optional WhatsApp notify |
| `LIVEOPS_WHATSAPP_NOTIFY` | `true`/`false` — notify on analyze start/complete |
| `LIVEOPS_WHATSAPP_NUMBER` / `LIVEOPS_WHATSAPP_CONTACT_REF` | Evolution WhatsApp target |
| `RALFIA_OPENAI_ROOT` | Path hint for local RalfIA stack (lab only) |

Copy template: `.env.example`

---

## Run locally

```bash
cd /home/rlopez/projects/ralphiia-liveops-intelligence
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill keys; never commit .env
uvicorn app.main:app --host 0.0.0.0 --port 8788
```

Open http://127.0.0.1:8788/

---

## Deploy on Render

1. Connect GitHub repo `Rafa-Innerchispa/ralphiia-liveops-intelligence`, branch `hackathon/youcom-liveops-20260724`.
2. Use `render.yaml` (web service, health check `/health`, start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`).
3. Add environment variables from the table above in the Render Dashboard.
4. After deploy: `curl -s https://ralphiia-liveops-intelligence.onrender.com/health | jq .`

---

## API (selected)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Service + provider configuration status |
| `POST` | `/api/analyze` | Synchronous full pipeline |
| `POST` | `/api/analyze/stream` | SSE: agents, `data_flow`, `complete` |
| `POST` | `/api/decision` | `{ decision, session_id, note }` — human checkpoint |
| `POST` | `/api/incident/preview` | Editable GitHub issue draft |
| `POST` | `/api/incident/create` | Create issue via One (after Approve) |
| `GET` | `/api/nodes` | Sanitized node snapshot |
| `GET` | `/api/youcom/probe` | Single-chain You.com smoke test |
| `GET` | `/api/build-review` | Opsera build review artifact |

---

## Testing

```bash
source .venv/bin/activate
pytest tests/ -q
```

Public smoke (investigate SSE against Render):

```bash
LIVEOPS_BASE=https://ralphiia-liveops-intelligence.onrender.com \
  python scripts/verify_public_sse.py
```

You.com live probe (local or Render):

```bash
curl -s "$LIVEOPS_BASE/api/youcom/probe" | jq .
```

---

## License / safety

- **Dry-run by default:** no production restart, WhatsApp recover, or delete operations.
- Responses and GitHub issues are sanitized: no private IPs, tokens, raw logs, or PII in issue bodies.

---

**Tagline:** Multi-agent LiveOps with live evidence, You.com citations, Parasail review, human approval, and One-powered GitHub incident tracking.
