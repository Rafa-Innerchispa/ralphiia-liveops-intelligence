from __future__ import annotations

DEFAULT_INCIDENT_QUESTION = (
    "Investigate the current health of my infrastructure. Use live server evidence "
    "and current web sources. Do not change production."
)

RESEARCH_HINTS = (
    "research",
    "investigate",
    "investiga",
    "investigar",
    "sources",
    "fuentes",
    "documentation",
    "why",
    "por qué",
    "porque",
    "cause",
    "causa",
    "deeper",
    "compare",
    "troubleshoot",
    "you.com",
    "web",
    "citation",
    "citas",
    "actual",
    "current sources",
)

STATUS_HINTS = (
    "status",
    "health",
    "unhealthy",
    "salud",
    "estado",
    "servidor",
    "servidores",
    "infraestructura",
    "evalua",
    "evaluar",
    "evalúa",
    "revisa",
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
    "ahora",
)


def normalize_prompt(raw: str | None) -> str:
    from app.provenance import sanitize_operator_prompt

    text = sanitize_operator_prompt(raw)
    if text:
        return text
    if raw and str(raw).strip() in {"promptLiveStatus", "promptInvestigate"}:
        return ""
    return (raw or "").strip() or DEFAULT_INCIDENT_QUESTION


def needs_web_research(
    prompt: str, *, force: bool = False, run_mode: str = "auto"
) -> bool:
    if run_mode == "status_only":
        return False
    if run_mode == "investigate" or force:
        return True
    p = prompt.lower()
    if any(h in p for h in RESEARCH_HINTS):
        return True
    if any(h in p for h in STATUS_HINTS) and "research" not in p and "investigate" not in p:
        return False
    return True


INVESTIGATE_DEFAULT_PROMPT = (
    "Evaluate my servers and give possible solutions to the problem found, "
    "with web-backed recommendations and citations. Do not change production."
)

STATUS_DEFAULT_PROMPT = (
    "What is currently unhealthy in my infrastructure? Use live read-only evidence only."
)


def prompt_for_run_mode(run_mode: str, user_prompt: str, observer_facts: list[str]) -> str:
    from app.provenance import sanitize_operator_prompt

    clean = sanitize_operator_prompt(user_prompt) or user_prompt.strip()
    if run_mode == "status_only":
        return clean or STATUS_DEFAULT_PROMPT
    if run_mode == "investigate":
        return clean or INVESTIGATE_DEFAULT_PROMPT
    return user_prompt


def build_research_query(user_prompt: str, observer_facts: list[str]) -> str:
    from app.provenance import build_sanitized_research_query

    observed = [f for f in observer_facts if not f.startswith("DEMO_")]
    demo = [f for f in observer_facts if f.startswith("DEMO_")]
    return build_sanitized_research_query(user_prompt, observed, demo)


from app.answer_render import normalize_operator_answer


def build_operator_summary(
    prompt: str,
    recommendation: str,
    confidence: float,
    *,
    data_sources: dict[str, str] | None = None,
    local_preview: str = "",
) -> str:
    """Operator-facing text; keep recommendation readable (no API dump prefix)."""
    return normalize_operator_answer(recommendation)
