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
    text = (raw or "").strip()
    return text if text else DEFAULT_INCIDENT_QUESTION


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
    if run_mode == "status_only":
        return user_prompt.strip() or STATUS_DEFAULT_PROMPT
    if run_mode == "investigate":
        ctx = " ".join(observer_facts[:5])[:500]
        base = user_prompt.strip() or INVESTIGATE_DEFAULT_PROMPT
        if ctx and ctx not in base:
            return f"{base} Observed facts from live probe: {ctx}"
        return base
    return user_prompt


def build_research_query(user_prompt: str, observer_facts: list[str]) -> str:
    context = " ".join(observer_facts[:3])[:400]
    return (
        f"{user_prompt.strip()} Context (read-only RalfIA): {context} "
        "Evolution API WhatsApp health systemd troubleshooting read-only"
    ).strip()


def build_operator_summary(
    prompt: str,
    recommendation: str,
    confidence: float,
    *,
    data_sources: dict[str, str] | None = None,
    local_preview: str = "",
) -> str:
    short_rec = recommendation[:280] + ("…" if len(recommendation) > 280 else "")
    proof = ""
    if data_sources:
        proof = (
            f"APIs this run: Observer={data_sources.get('observer', '?')}; "
            f"Local={data_sources.get('local_analyst', '?')}; "
            f"Research={data_sources.get('research', '?')}. "
        )
    local_bit = ""
    if local_preview:
        local_bit = f" Local analyst: {local_preview[:160]}…" if len(local_preview) > 160 else f" Local analyst: {local_preview}"
    return (
        f"{proof}"
        f"Answer (confidence {confidence:.0%}): {short_rec}{local_bit}"
    )
