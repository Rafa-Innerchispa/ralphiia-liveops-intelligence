# Architecture — RalphiIA LiveOps Intelligence

## Flow

```mermaid
sequenceDiagram
  participant UI as Single-page UI
  participant API as FastAPI :8788
  participant Obs as Observer
  participant Res as Research (You.com)
  participant Sec as Security Reviewer
  participant Arb as Arbitrator

  UI->>API: POST /api/analyze
  API->>Obs: fetch_live_status (read-only)
  Obs-->>API: facts + evidence_ref
  API->>Res: search + research + contents
  Res-->>API: citations
  API->>Sec: policy check
  Sec-->>API: approve/block
  API->>Arb: final JSON
  Arb-->>API: recommendation
  API-->>UI: PipelineResult
  UI->>API: POST /api/decision (dry-run checkpoint)
```

## Integrations

| Layer | Endpoint | Mode |
|-------|----------|------|
| RalfIA | `127.0.0.1:8101/status` | Read-only GET |
| You.com Search | `GET /v1/search` | Bearer `YOUCOM_API_KEY` |
| You.com Research | `POST /v1/research` | Bearer |
| You.com Contents | `POST /v1/contents` | Bearer |
| Fallback | fixtures in `youcom_client.py` | Labeled `fixture` |

## Safety

- No WhatsApp send, CRM, auth, or service restarts
- Approve button → audit checkpoint only (`executed: false`)
- UI sanitizes: no private IPs, Mongo URIs, or tokens in responses
