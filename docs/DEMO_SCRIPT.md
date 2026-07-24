# Live demo script (60–90 s) — You.com hackathon (English)

**URLs:** Render (after deploy) · **Fallback:** ngrok `/liveops/` (`LIVEOPS_PUBLIC_URL`)

**Tagline:** Ask your infrastructure. Get evidence, not guesses.

## Act 1 — Live status, save credits (15 s)

"I'm in San Francisco; my servers are in Ecuador."

Click **1 · Check Live Status** (or ask: *What is currently unhealthy in my infrastructure?*).

Show **Live API trace:** RalfIA + Ollama; **You.com SKIPPED** on purpose.

## Act 2 — Web + Parasail (35 s)

Click **2 · Investigate with Live Sources**.

Show trace: `you-search` → contents → research → Parasail; **citation cards**; recommended dry-run action for Evolution `.5` health down.

## Act 3 — GitHub incident (20 s)

Click **3 · Create GitHub Incident** → edit preview → **Approve & create issue**.

Show real GitHub URL (One MCP if `ONE_SECRET`, else GitHub API if `GITHUB_TOKEN`).

## Act 4 — Human checkpoint (10 s)

**Approve (checkpoint)** — audit only; no production changes.

## Honesty

- **Used in this run** / API trace = only what executed this time.
- **Opsera** = IDE build-time panel, not a runtime agent.
- **Fixture** labeled when `:8101` unreachable (e.g. Render without `RALFIA_STATUS_URL` bridge).
