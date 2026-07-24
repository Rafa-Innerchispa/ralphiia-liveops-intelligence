# Render Workflow (Act 2) — create manually after this code is deployed

Render Blueprints **cannot** create Workflows yet. Use **Dashboard → New → Workflow**.

## Service name

`ralphiia-liveops-investigation`

## Repository settings

| Field | Value |
|-------|--------|
| **Root Directory** | *(repo root)* |
| **Branch** | `hackathon/youcom-liveops-20260724` |
| **Runtime** | Python 3 |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `python -m workflow.investigation` |

Set env **`RENDER_WORKFLOW_TASK`** per task definition in Render UI, or map each workflow step to:

- `gather_context`
- `research_live_sources`
- `security_review`
- `compose_incident`
- `run_liveops_investigation`

Copy **`YOUCOM_API_KEY`**, **`PARASAIL_API_KEY`**, **`RALFIA_STATUS_URL`**, **`RALFIA_STATUS_TOKEN`** from the web service.

## Web service feature flag (later)

When Workflow is live, set on **ralphiia-liveops-intelligence** web service:

- `LIVEOPS_RENDER_WORKFLOW=true`
- `LIVEOPS_RENDER_WORKFLOW_SERVICE=ralphiia-liveops-investigation`

Until then, Act 2 stays **in-process SSE** (current behavior).

## Badge

UI shows **Orchestrated by Render Workflows** only when `metrics.render_workflow_run_id` is present (not yet wired).
