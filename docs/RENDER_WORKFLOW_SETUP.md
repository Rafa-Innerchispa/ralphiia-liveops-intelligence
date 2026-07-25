# Render Workflow (Act 2)

Blueprint cannot create Workflows — use **Dashboard → New → Workflow** (service `ralphiia-liveops-investigation`).

| Field | Value |
|-------|--------|
| **Start Command** | `python -m workflow.investigation` |
| **Build** | `pip install -r requirements.txt` |

## Env — workflow service (`ralphiia-liveops-investigation`)

Copy from web service (investigate chain needs these):

- `YDC_API_KEY` or `YOUCOM_API_KEY`
- `PARASAIL_API_KEY`
- `RALFIA_STATUS_URL`, `RALFIA_STATUS_TOKEN` (or `LIVEOPS_BRIDGE_TOKEN`)
- `LIVEOPS_DATA_MODE` (optional, default `auto`)
- `RENDER_WORKFLOW_TASK=run_liveops_investigation` (CLI entry when not using Render task runner)
- **`LIVEOPS_WORKFLOW_PROMPT`** — default prompt if task has no API input
- **`LIVEOPS_WORKFLOW_SESSION_ID`** — optional session label

Task slug in Render UI: `run_liveops_investigation` (or step tasks: `gather_context`, …).

## Env — web service (`ralphiia-liveops-intelligence`)

- `LIVEOPS_RENDER_WORKFLOW=true`
- `LIVEOPS_RENDER_WORKFLOW_SERVICE=ralphiia-liveops-investigation`
- **Optional remote trigger** (else in-process `/api/render-workflow/start`):
  - `RENDER_API_KEY` (`rnd_…`)
  - `RENDER_WORKFLOW_TASK_SLUG` e.g. `ralphiia-liveops-investigation/run_liveops_investigation`

In-process runs use the same agents as `/api/analyze` investigate mode (`run_observer` → `run_research` → security → arbitrator), without touching the SSE route.
