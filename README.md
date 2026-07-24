# RalphiIA LiveOps Intelligence

**Ask your infrastructure. Get evidence, not guesses.**

You.com Agentic Hackathon · **Multi-Agent Systems** — evidence-first LiveOps on **real RalfIA servers** (read-only / dry-run).

| | |
|---|---|
| **Public demo** | https://sworn-profusely-alongside.ngrok-free.dev/liveops/ |
| **Server path** | `/home/rlopez/projects/ralphiia-liveops-intelligence` |
| **Port** | **8788** (isolated from `raphiia-openai` production) |
| **Branch** | `hackathon/youcom-liveops-20260724` |

## Problem

Infrastructure teams switch between dashboards, logs, docs, web search, and LLMs that cannot separate **live facts** from **speculation**.

## Solution

Operators ask in natural language. The system:

1. **Observes** live state via RalfIA (`:8101/status`) — labeled live vs fixture  
2. **Researches** with **You.com MCP** (Search · Contents · Research) when needed — citations as cards  
3. **Reasons locally** with **Ollama** (Local Analyst) when available  
4. **Reviews** with **Parasail** (Security + Arbitrator)  
5. **Requires human approval** before any operational action (checkpoint only)

**Differentiator:** Observed operational truth ≠ Web evidence ≠ Model hypothesis ≠ Approved action.

## Quick start

```bash
cd /home/rlopez/projects/ralphiia-liveops-intelligence
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add YOUCOM_API_KEY, PARASAIL_API_KEY, optional LIVEOPS_WHATSAPP_NUMBER
uvicorn app.main:app --host 0.0.0.0 --port 8788
```

## API

- `POST /api/analyze` — `{ "prompt", "session_id", "research_deeper" }`  
- `POST /api/analyze/stream` — SSE progress + `data_flow` events  
- `GET /api/nodes` — live node snapshot  
- `GET /api/build-review` — **Opsera Agents** (IDE review evidence, not runtime)

## Opsera (partner prize — honest)

**Opsera Agents** runs in **Cursor during development** (pre-commit security/architecture review). It is **not** a fake runtime agent in the pipeline. Export scan results to `data/opsera_build_review.json` for the UI panel.

## WhatsApp alerts (optional)

When `LIVEOPS_WHATSAPP_NOTIFY=true` and `LIVEOPS_WHATSAPP_NUMBER` or `LIVEOPS_WHATSAPP_CONTACT_REF` is set, each analysis sends start/complete messages via RalfIA Evolution (primary node).

## Tests

```bash
pytest -q tests/test_app.py
```

## Demo

[docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) · [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## You.com proof

```bash
curl -s http://127.0.0.1:8788/api/youcom/probe | jq .
```
