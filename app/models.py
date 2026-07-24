from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AgentName(str, Enum):
    observer = "observer"
    local_analyst = "local_analyst"
    research = "research"
    security_reviewer = "security_reviewer"
    arbitrator = "arbitrator"


class Citation(BaseModel):
    title: str
    url: str
    snippet: str = ""
    retrieved_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class AgentStep(BaseModel):
    agent: AgentName
    status: str
    started_at: str
    finished_at: str | None = None
    summary: str
    facts: list[str] = Field(default_factory=list)
    hypotheses: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SecurityVerdict(BaseModel):
    approved: bool
    blocked_actions: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class FinalRecommendation(BaseModel):
    observed_facts: list[str]
    hypotheses: list[str]
    confidence: float
    citations: list[Citation]
    recommended_action: str
    risk_level: str
    requires_approval: bool = True
    dry_run: bool = True
    security: SecurityVerdict


class PipelineResult(BaseModel):
    correlation_id: str
    session_id: str = ""
    incident_id: str
    mode: str
    youcom_mode: str
    user_prompt: str = ""
    operator_summary: str = ""
    providers_used: list[dict[str, Any]] = Field(default_factory=list)
    models_used: list[dict[str, Any]] = Field(default_factory=list)
    models_available: list[str] = Field(default_factory=list)
    data_sources: dict[str, str] = Field(default_factory=dict)
    live_nodes: dict[str, Any] = Field(default_factory=dict)
    steps: list[AgentStep]
    recommendation: FinalRecommendation
    metrics: dict[str, Any]
    human_decision: str | None = None


class AnalyzeRequest(BaseModel):
    prompt: str = ""
    correlation_id: str | None = None
    session_id: str | None = None
    research_deeper: bool = False


class HumanDecisionRequest(BaseModel):
    decision: str  # approve | reject | research_deeper
    note: str = ""


class HealthResponse(BaseModel):
    ok: bool
    service: str
    port: int
    data_mode: str
    youcom: dict
    dry_run: bool
    timestamp: str
    hackathon_track: str = "Multi-Agent Systems"
    hackathon_event: str = ""
