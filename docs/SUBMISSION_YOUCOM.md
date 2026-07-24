# You.com Hackathon — Submission narrative

**Track:** Multi-Agent Systems  
**Project:** RalphiIA LiveOps Intelligence  
**Correlation:** `youcom-hackathon-liveops-20260724`

## You.com integration (what judges ask for)

| Slide capability | Our implementation |
|------------------|-------------------|
| Web Search & News | `YouComClient.search` → You.com Search API |
| Content Extraction | `YouComClient.contents` → Contents API |
| Multi-Step Research | `YouComClient.research` → Research API (`lite`) |
| Official stack | Compatible with [agent-skills](https://github.com/youdotcom-oss/agent-skills) + MCP `https://api.you.com/mcp` |

## Multi-agent workflow

1. **Observer** — RalfIA read-only probe (real incident: node `.5`, Evolution health down, dry-run).
2. **Research** — You.com Search → Contents on top hit → Research synthesis with citations.
3. **Security Reviewer** — Deny restart/recover without evidence; enforce dry-run.
4. **Arbitrator** — JSON recommendation, `requires_approval: true`.

## Why not a generic demo

- **Impact:** Real dual-node ops stack (months in production), not a mock CRUD app.
- **Innovation:** Human-in-the-loop LiveOps + web-grounded research vs single LLM guess.
- **Safety:** Approve button is audit-only (`executed: false`).

## Repo isolation

All hackathon code lives under `/home/rlopez/projects/ralphiia-liveops-intelligence` on branch `hackathon/youcom-liveops-20260724`. No changes to RalfIA core, WhatsApp production, or DNS.
