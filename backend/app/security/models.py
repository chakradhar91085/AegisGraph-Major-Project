from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from enum import Enum
import time

class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class ResponseMode(str, Enum):
    ALLOW = "ALLOW"
    MASK = "MASK"
    RESTRICT = "RESTRICT"
    BLOCK = "BLOCK"

class AdaptivePolicy(BaseModel):
    risk_score: float = Field(..., ge=0.0, le=1.0)
    risk_level: RiskLevel
    attenuation_factor: float = Field(..., ge=0.0, le=1.0)
    effective_context_limit: int = Field(..., ge=1)
    effective_graph_depth: int = Field(..., ge=0)
    response_mode: ResponseMode = ResponseMode.ALLOW
class SignalValues(BaseModel):
    semantic_focus: float = Field(0.0, ge=0.0, le=1.0)
    temporal_frequency: float = Field(0.0, ge=0.0, le=1.0)
    entity_focus: float = Field(0.0, ge=0.0, le=1.0)
    graph_footprint: float = Field(0.0, ge=0.0, le=1.0)
    sensitivity_exposure: float = Field(0.0, ge=0.0, le=1.0)

class TelemetryEvent(BaseModel):
    session_id: str
    timestamp: float = Field(default_factory=time.time)
    query: str
    intent: Optional[str] = None
    retrieval_strategy: Optional[str] = None
    result_count: int = 0
    signals: SignalValues = Field(default_factory=SignalValues)
    instantaneous_risk: float = Field(0.0, ge=0.0, le=1.0)
    smoothed_risk: float = Field(0.0, ge=0.0, le=1.0)
    policy: Optional[AdaptivePolicy] = None
    blocked_by_policy: bool = False
    retrieval_executed: bool = False
    role: str = "Standard"
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    response_mode: ResponseMode = ResponseMode.ALLOW
    # Cypher the MCP agent ran. Audit only: stripped from the chat response,
    # since it can name people the user is not allowed to see unmasked.
    cypher_queries: List[str] = Field(default_factory=list)
    # What this answer touched: {"labels": {"Legal": 3}, "pii": {...}, "sensitive_items": n,
    # "max_seniority": x, "units": x}. Counts only, no names, so it is safe to show the user.
    exposure: Dict[str, Any] = Field(default_factory=dict)
    # Who fetched the evidence: the MCP agent's model, "fixed queries", or None if nothing ran.
    retrieval_model: Optional[str] = None

class QueryRecord(BaseModel):
    timestamp: float
    query: str
    embedding: Optional[List[float]] = None
    entities: List[str] = Field(default_factory=list)

class SessionState(BaseModel):
    session_id: str
    history: List[QueryRecord] = Field(default_factory=list)
    last_smoothed_risk: float = 0.0
    last_seen: float = 0.0
    last_entity: Optional[str] = None
    # Mode of the previous query, so alerts fire on escalation, not every query.
    last_mode: str = "ALLOW"
    # Accumulated sensitivity exposure and when it was last updated (it fades over time).
    exposure: float = 0.0
    exposure_at: float = 0.0
