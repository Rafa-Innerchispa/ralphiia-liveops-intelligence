from __future__ import annotations

DEFAULT_INCIDENT_QUESTION = (
    "Investigate the current health of my infrastructure. Use live server evidence "
    "and current web sources. Do not change production."
)

RESEARCH_HINTS = (
    "research",
    "investigate",
    "sources",
    "documentation",
    "why",
    "cause",
    "deeper",
    "compare",
    "troubleshoot",
    "you.com",
    "web",
    "citation",
)

STATUS_HINTS = (
    "status",
    "health",
    "unhealthy",
    "mongodb",
    "8101",
    "live",
    "right now",
    "what is running",
    "infrastructure",
    "ralfia",
    "evolution",
    ".5",
    ".4",
)


def normalize_prompt(raw: str | None) -> str:
    text = (raw or "").strip()
    return text if text else DEFAULT_INCIDENT_QUESTION


def needs_web_research(prompt: str, *, force: bool = False) -> bool:
    if force:
        return True
    p = prompt.lower()
    if any(h in p for h in RESEARCH_HINTS):
        return True
    if any(h in p for h in STATUS_HINTS) and "research" not in p and "investigate" not in p:
        return False
    return True


def build_research_query(user_prompt: str, observer_facts: list[str]) -> str:
    context = " ".join(observer_facts[:3])[:400]
    return (
        f"{user_prompt.strip()} Context (read-only RalfIA): {context} "
        "Evolution API WhatsApp health systemd troubleshooting read-only"
    ).strip()


def build_operator_summary(prompt: str, recommendation: str, confidence: float) -> str:
    short_rec = recommendation[:320] + ("…" if len(recommendation) > 320 else "")
    return (
        f"For your question: «{prompt[:120]}{'…' if len(prompt) > 120 else ''}» — "
        f"confidence {confidence:.0%}. {short_rec}"
    )
