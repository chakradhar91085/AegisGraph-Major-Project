"""Pydantic schemas for the retrieval layer."""
from pydantic import BaseModel, Field
from typing import List, Dict, Any
from enum import Enum


class RetrievalIntent(str, Enum):
    AGENT_QUERY = "agent_query"
    UNSUPPORTED = "unsupported_intent"  # no data needed (greeting, small talk)


class RetrievalRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    limit: int = Field(default=10, ge=1, le=50)
    response_mode: str = "ALLOW"


class RetrievalResponse(BaseModel):
    query: str
    intent: str
    entities: List[str] = Field(default_factory=list)  # email addresses of the people found
    results: List[Dict[str, Any]] = Field(default_factory=list)
    result_count: int = 0
    strategy: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
