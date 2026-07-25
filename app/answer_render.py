from __future__ import annotations

import json
import re


def parse_recommended_action(raw: str) -> str:
    """Extract markdown/text from Parasail JSON blobs — never show raw JSON in UI."""
    text = (raw or "").strip()
    if not text:
        return ""
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    if text.startswith("{") and ("recommended_action" in text or '"confidence"' in text):
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            m = re.search(r"\{[\s\S]*\}", text)
            if m:
                try:
                    data = json.loads(m.group(0))
                except json.JSONDecodeError:
                    return _strip_json_artifacts(text)
            else:
                return text
        if isinstance(data, dict):
            action = data.get("recommended_action")
            if action:
                return str(action).strip()
            if data.get("raw"):
                return str(data["raw"]).strip()
    return text


def _strip_json_artifacts(text: str) -> str:
    return re.sub(r'^\s*\{\s*"recommended_action"\s*:\s*', "", text).strip()


def dedupe_operator_answer(text: str) -> str:
    """Collapse repeated lines/sections (gateway/Mongo/Evolution loops)."""
    lines = text.splitlines()
    seen: set[str] = set()
    out: list[str] = []
    section_seen: set[str] = set()
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if out and out[-1] != "":
                out.append("")
            continue
        norm = re.sub(r"\[\d+\]", "", stripped.lower())
        norm = re.sub(r"https?://\S+", "", norm).strip()
        if norm in seen and stripped.startswith("•"):
            continue
        if stripped.endswith(":") and stripped.lower() in section_seen:
            continue
        if stripped.endswith(":"):
            section_seen.add(stripped.lower())
        seen.add(norm)
        out.append(line.rstrip())
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out)


def limit_readonly_actions(text: str, max_items: int = 4) -> str:
    """Keep at most N bullet/numbered action lines in recommendation sections."""
    lines = text.splitlines()
    out: list[str] = []
    in_actions = False
    action_count = 0
    action_re = re.compile(r"^\s*(?:[-•*]|\d+[.)])\s+")
    for line in lines:
        stripped = line.strip()
        if re.search(r"(?i)recommended|next steps|read-only", stripped) and stripped.endswith(":"):
            in_actions = True
            action_count = 0
            out.append(line)
            continue
        if in_actions and action_re.match(line):
            if action_count >= max_items:
                continue
            action_count += 1
            out.append(line)
            continue
        if in_actions and stripped and not action_re.match(line) and stripped.endswith(":"):
            in_actions = False
        out.append(line)
    return "\n".join(out)


def normalize_operator_answer(raw: str) -> str:
    text = parse_recommended_action(raw)
    text = dedupe_operator_answer(text)
    if text.startswith("{") and "recommended_action" in text:
        text = parse_recommended_action(text)
    text = re.sub(
        r',?\s*"risk_level"\s*:\s*"?[a-z]+"?\s*}?\s*$',
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()
    text = limit_readonly_actions(text.strip(), max_items=4)
    return text.strip()
