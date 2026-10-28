import asyncio
import uuid
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, Literal, Optional
import logging

from app.core.config import settings
from app.db.postgres import AsyncSessionLocal
from app.llm.provider_factory import (
    SUPPORTED_PROVIDERS, get_llm_provider, provider_available, resolve_provider_name,
)
from app.rag.service import graph_rag_service
from app.security.auth import User, current_user, require_admin
from app.security.db_models import AuditSession
from app.security.policy import policy_engine
from app.security.session import session_store
from app.security.tickets import issue_ticket, verify_ticket
from sqlalchemy.future import select
import datetime
import time

logger = logging.getLogger(__name__)

router = APIRouter()

# One question in flight per user. Without this, parallel requests are all judged
# against the same not-yet-updated risk score and slip past the policy.
# ponytail: in-process locks; use a shared lock (e.g. Redis) if run with several workers.
_user_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

class ChatRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    session_token: Optional[str] = None
    # Which model answers this question. Omitted = the server default (ollama).
    llm_provider: Optional[Literal["ollama", "openrouter"]] = None

class ChatResponse(BaseModel):
    answer: str
    session_id: str
    session_token: str
    intent: str
    retrieval: Dict[str, Any]
    status: str
    telemetry: Optional[Dict[str, Any]] = None
    graph_data: Optional[Dict[str, Any]] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None

@router.get("/llm/providers")
async def llm_providers(user: User = Depends(current_user)):
    """The models a user can switch between, and which one is the default."""
    models = {"ollama": settings.OLLAMA_MODEL, "openrouter": settings.OPENROUTER_MODEL}
    return {
        "default": resolve_provider_name(None),
        "providers": [
            {"id": name, "model": models[name], "available": provider_available(name)}
            for name in SUPPORTED_PROVIDERS
        ],
    }

@router.get("/me")
async def me(user: User = Depends(current_user)):
    """Who is signed in, plus the risk and policy their next query will face."""
    risk = session_store.decayed_risk(user.user_id, time.time())
    policy = policy_engine.calculate_policy(risk, user.role)
    return {
        "user_id": user.user_id,
        "role": user.role,
        "risk_score": risk,
        "response_mode": policy.response_mode.value,
    }

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest, user: User = Depends(current_user)):
    """
    Secure Graph-RAG chat endpoint.

    Identity and role come from the verified login token, never from the
    request body. The session ticket only groups a user's messages for the
    audit trail; the user's remembered risk is keyed by user id, so dropping
    the ticket does not reset it.
    """
    lock = _user_locks[user.user_id]
    if lock.locked():
        raise HTTPException(status_code=429, detail="Please wait for your previous question to finish.")
    async with lock:
        return await _answer(request, user)


async def _answer(request: ChatRequest, user: User) -> ChatResponse:
    session_id = (verify_ticket(request.session_token, user.user_id) if request.session_token else None) or str(uuid.uuid4())

    logger.info(f"Chat request: user={user.user_id} session={session_id} role={user.role}")

    provider_name = resolve_provider_name(request.llm_provider)
    if not provider_available(provider_name):
        raise HTTPException(status_code=400, detail=f"{provider_name} is not configured on the server.")

    try:
        rag_result = await graph_rag_service.generate_answer(
            request.query,
            session_id=session_id,
            role=user.role,
            llm_provider=provider_name,
            user_id=user.user_id,
            user_email=user.email,
        )

        token, session_id = issue_ticket(user.user_id, session_id=session_id)
        # Agent Cypher is for the audit log only (it can contain unmasked addresses).
        if rag_result.get("telemetry"):
            rag_result["telemetry"].pop("cypher_queries", None)

        return ChatResponse(
            answer=rag_result["answer"],
            session_id=session_id,
            session_token=token,
            intent=rag_result.get("intent", "unknown"),
            retrieval=rag_result.get("retrieval", {}),
            telemetry=rag_result.get("telemetry", None),
            graph_data=rag_result.get("graph_data", None),
            llm_provider=rag_result.get("llm_provider", None),
            llm_model=getattr(get_llm_provider(provider_name), "model", None),
            status="success"
        )
    except Exception as e:
        logger.error(f"Error during chat generation for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during chat processing")


class SessionRef(BaseModel):
    session_token: str

@router.post("/session/end")
async def end_own_session(ref: SessionRef, user: User = Depends(current_user)):
    """Mark the caller's own audit session as completed (proved by its ticket)."""
    session_id = verify_ticket(ref.session_token, user.user_id)
    if not session_id:
        raise HTTPException(status_code=404, detail="Session not found")
    async with AsyncSessionLocal() as db:
        session = (await db.execute(select(AuditSession).where(AuditSession.id == session_id))).scalar_one_or_none()
        if session and session.status != "COMPLETED":
            session.status = "COMPLETED"
            session.ended_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
            await db.commit()
    return {"status": "success"}

@router.post("/session/reset")
async def reset_risk(user: User = Depends(require_admin)):
    """Demo convenience for Auditors: forget their own remembered risk. Off unless
    DEMO_ALLOW_RISK_RESET=true. Never open to ordinary users, or anyone could
    wipe their risk score and dodge the policy."""
    if not settings.DEMO_ALLOW_RISK_RESET:
        raise HTTPException(status_code=403, detail="Risk reset is disabled")
    session_store.reset(user.user_id)
    return {"status": "reset"}
