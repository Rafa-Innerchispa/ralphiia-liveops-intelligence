# RalphiIA LiveOps Intelligence

**Ask your infrastructure. Get evidence, not guesses.**

Evidence-first LiveOps for distributed ops teams: live read-only probes, web-backed research with citations, independent security review, human approval, and optional incident tracking on GitHub via **One passthrough API** — **no production mutations** (`dry_run=true`).

---

## Live hackathon status (verified on Render)

Public URL: https://ralphiia-liveops-intelligence.onrender.com · Branch: `hackathon/youcom-liveops-20260724` · **Last verified:** 2026-07-25 UTC · **Deploy commit:** `688ab9d` (One Act 3 fix)

**Demo-ready for submission:** Acts 1–3 on the web service (status → investigate → approve → GitHub issue). Optional Render Workflow button is a **separate, stubbed** path.

### Implemented and working

| Area | Status | Evidence |
|------|--------|----------|
| **Web service on Render** | Live | `/health` 200; You.com MCP live; Parasail configured |
| **Act 1 — Live Status** | Working | Observer + read-only bridge; SSE `/api/analyze/stream` |
| **Act 2 — Investigate** | Working | You.com research + citations; Parasail security + arbitrator; operator answer sanitized (no raw JSON) |
| **Human approval** | Working | `/api/decision` + UI **Approve** gates **Create GitHub Incident** |
| **Issue preview** | Working | `/api/incident/preview` editable title/body |
| **Act 3 — GitHub issue via One** | **Working** | Fix `688ab9d`: One CLI-style passthrough with **`x-one-action-id`** (raw passthrough without it returned `secret_middleware_error`). **Automated smoke on Render:** `POST /api/analyze` (`status_only`) → Approve → `POST /api/incident/create` → **200** → [issue #1](https://github.com/Rafa-Innerchispa/ralphiia-liveops-intelligence/issues/1) (smoke title; safe to close). |
| **Session / SSE pipeline** | Working | `session_id`; in-process pipeline unchanged for `/api/analyze` |
| **Render Workflow service** | Deployed | Separate Render resource `ralphiia-liveops-investigation`; start `python -m workflow.investigation` |
| **Workflow UI (feature flag)** | Working | `LIVEOPS_RENDER_WORKFLOW=true` → button **Run as Render Workflow**; `/api/render-workflow/start` → `completed` (verified API) |
| **Tests** | Passing | `pytest tests/` (includes answer render, One client, workflow lifecycle) |
| **Documentation** | In repo | This README, `docs/RENDER_WORKFLOW_SETUP.md`, `docs/DEPLOY_RENDER.md`, `docs/BRIDGE.md` |

### Not complete / not fully demo-tested

| Area | Status | What is missing or untested |
|------|--------|-----------------------------|
| **Live UI walkthrough (judges)** | **Not re-run end-to-end in browser after `688ab9d`** | API smoke passed; you should still click **2 · Investigate** → **Approve** → **Create GitHub Incident** once on stage (full SSE + citations). |
| **Render Workflow — remote trigger** | Not wired | UI workflow button runs **in-app** orchestration (`/api/render-workflow/*`), not Render’s Workflow API. `RENDER_API_KEY` (`rnd_…`) is **not** used in code yet. |
| **Workflow task bodies** | Stubs | `workflow/investigation.py` tasks return placeholder JSON; full You.com/Parasail/bridge logic still lives in the main SSE pipeline. |
| **WhatsApp notify on analyze** | Optional | Env present in some setups; not part of the core hackathon demo script. |
| **Local Ollama from Render** | Expected unavailable | Local Analyst skipped or unavailable from cloud; not a deployment bug. |
| **Opsera** | Dev-only artifact | Build review JSON for how the app was built in Cursor — **not** a runtime agent. |

### Environment variables (web service `ralphiia-liveops-intelligence`)

Required for the live demo acts: `YDC_API_KEY` or `YOUCOM_API_KEY`, `PARASAIL_API_KEY`, `RALFIA_STATUS_URL`, `RALFIA_STATUS_TOKEN` (or bridge token).

For Act 3 (issue create): `ONE_SECRET`, `ONE_GITHUB_CONNECTION_KEY`, `GITHUB_REPO_OWNER`, `GITHUB_REPO_NAME`.

For workflow button: `LIVEOPS_RENDER_WORKFLOW=true`, `LIVEOPS_RENDER_WORKFLOW_SERVICE=ralphiia-liveops-investigation`.

`RENDER_API_KEY` is for future Render API integration — **does not** replace `ONE_SECRET`.

---
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
┌──────────────┐     One REST API         ┌─────────────────────────┐
│  One → GH    │ ─────────────────────► │ passthrough + action id │
│  Issue       │                        │ (CLI execute path)      │
└──────────────┘                        └─────────────────────────┘

Optional (feature flag): **Run as Render Workflow** → `/api/render-workflow/*` (same repo, separate Render Workflow service)
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

### One → GitHub issue (Act 3)

- **App flow (same as [One CLI](https://www.withone.ai/docs/cli) `actions execute`):** resolve GitHub “Create an Issue” action → `GET /v1/knowledge?_id=…` → `POST /v1/passthrough{action.path}` with path vars `owner` / `repo`
- **Headers:** `x-one-secret`, `x-one-connection-key`, and **`x-one-action-id`** (required; omitting it caused `secret_middleware_error` before `688ab9d`)
- **Not** `https://mcp.withone.ai/mcp` with Bearer — OAuth-only (Cursor); server keys use `https://api.withone.ai`
- **Env:** `ONE_SECRET`, `ONE_GITHUB_CONNECTION_KEY`, `GITHUB_REPO_OWNER`, `GITHUB_REPO_NAME`; optional override `ONE_GITHUB_CREATE_ISSUE_ACTION_ID`
- **Flow:** Investigate (or Live Status) → **Approve** → **Create GitHub Incident** → **Create** → JSON includes `via: one_api_passthrough`, `one_action_id`, `html_url`
- **No `GITHUB_TOKEN` fallback** in the production path (One only)

### Render Workflow (optional Act 2 path — does not replace SSE)

Two separate Render resources:

| Resource | Name | Start command |
|----------|------|----------------|
| **Web Service** | `ralphiia-liveops-intelligence` | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| **Workflow** | `ralphiia-liveops-investigation` | `python -m workflow.investigation` |

- **Entry file:** `workflow/investigation.py` (tasks: `gather_context`, `research_live_sources`, `security_review`, `compose_incident`, `run_liveops_investigation`)
- **Workflow env:** `RENDER_WORKFLOW_TASK=run_liveops_investigation` (or per-step task name); copy `YDC_API_KEY`, `PARASAIL_API_KEY`, `RALFIA_STATUS_*` when wiring real logic (current tasks are **stubs** that return JSON)
- **Web env (shows UI button):** `LIVEOPS_RENDER_WORKFLOW=true`, `LIVEOPS_RENDER_WORKFLOW_SERVICE=ralphiia-liveops-investigation`
- **UI:** button **Run as Render Workflow** — calls **`/api/render-workflow/*` only**; **`/api/analyze` and SSE are unchanged**
- **Statuses:** `queued` → `running` → `completed` | `failed`
- **Setup:** [docs/RENDER_WORKFLOW_SETUP.md](docs/RENDER_WORKFLOW_SETUP.md) (Workflow must be created in Dashboard → New → Workflow; Blueprint only defines the web service)

**Verified on Render:** `GET /api/deployment` → `render_workflow_enabled: true`; `POST /api/render-workflow/start` → run completes with `status: completed`.

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
| **3 · GitHub incident** | Approve → Create GitHub Incident | Editable preview → One passthrough creates issue. |
| **Optional** | Run as Render Workflow | Isolated API path; SSE `/api/analyze` unchanged. |

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
| `ONE_SECRET` | One **Production** API key (`sk_live_…`) for passthrough API |
| `ONE_GITHUB_CONNECTION_KEY` | One GitHub connection key (`live::github::…`) |
| `ONE_GITHUB_CREATE_ISSUE_ACTION_ID` | Optional; default resolved via One action search |
| `ONE_API_BASE` | Default `https://api.withone.ai` |
| `LIVEOPS_RENDER_WORKFLOW` | `true` on **web** service to show workflow button |
| `LIVEOPS_RENDER_WORKFLOW_SERVICE` | Workflow service name (default `ralphiia-liveops-investigation`) |
| `RENDER_WORKFLOW_TASK` | On **Workflow** service: task function name (default `run_liveops_investigation`) |
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

### Web service (main demo)

1. Connect GitHub repo `Rafa-Innerchispa/ralphiia-liveops-intelligence`, branch `hackathon/youcom-liveops-20260724`.
2. Use `render.yaml` (web service, health check `/health`, start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`).
3. Add environment variables from the table above in the Render Dashboard.
4. After deploy: `curl -s https://ralphiia-liveops-intelligence.onrender.com/health | jq .`

### Workflow service (optional, separate resource)

1. Dashboard → **New → Workflow** (not Blueprint).
2. Name: **`ralphiia-liveops-investigation`**, same repo/branch, build `pip install -r requirements.txt`.
3. Start command: **`python -m workflow.investigation`**
4. Env: `PYTHON_VERSION=3.12.3`, `RENDER_WORKFLOW_TASK=run_liveops_investigation` (+ API keys when stubs are replaced).
5. On the **web** service add `LIVEOPS_RENDER_WORKFLOW=true` and redeploy the web app only.

Creating the Workflow **does not** replace or stop the web service.

---

## API (selected)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Service + provider configuration status |
| `POST` | `/api/analyze` | Synchronous full pipeline |
| `POST` | `/api/analyze/stream` | SSE: agents, `data_flow`, `complete` |
| `POST` | `/api/decision` | `{ decision, session_id, note }` — human checkpoint |
| `POST` | `/api/incident/preview` | Editable GitHub issue draft |
| `POST` | `/api/incident/create` | Create issue via One passthrough (after Approve) |
| `POST` | `/api/render-workflow/start` | Start isolated workflow run (feature flag) |
| `GET` | `/api/render-workflow/runs/{run_id}` | Poll `queued` / `running` / `completed` / `failed` |
| `GET` | `/api/deployment` | Deploy surface + `render_workflow_enabled` |
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
