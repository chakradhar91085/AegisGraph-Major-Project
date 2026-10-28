from fastapi import APIRouter, Depends, HTTPException, Query
import logging
from sqlalchemy.future import select
from app.db.postgres import AsyncSessionLocal
from app.security.auth import User, current_user, display_name, require_admin
from app.security.alerts import configured_channels, send_alert
from app.security.db_models import AuditSession, AuditQuery

# Every audit route exposes other users' queries, so all of them are admin-only.
router = APIRouter(dependencies=[Depends(require_admin)])
logger = logging.getLogger(__name__)

def _serialize_query(q: AuditQuery) -> dict:
    return {
        "id": q.id,
        "session_id": q.session_id,
        "timestamp": q.timestamp.isoformat() + "Z" if q.timestamp else None,
        "query": q.query,
        "intent": q.intent,
        "risk_score": q.risk_score,
        "instantaneous_risk": q.instantaneous_risk,
        "behavioral_mode": q.behavioral_mode,
        "retrieval_outcome": q.retrieval_outcome,
        "masked": q.masked,
        "attenuated": q.attenuated,
        "blocked": q.blocked,
        "result_count": q.result_count,
        "role": q.role,
        "user_id": q.user_id,
        "user_email": q.user_email,
        "user_name": display_name(q.user_id),
        "llm_provider": q.llm_provider,
        "signals": q.signals,
        "policy": q.policy,
        "cypher_queries": q.cypher_queries,  # audit routes are Auditor-only
        "exposure": q.exposure,
    }

@router.get("/audit/sessions")
async def get_audit_sessions(limit: int = Query(50, ge=1, le=500)):
    """
    Retrieve the most recent audit sessions.
    """
    try:
        async with AsyncSessionLocal() as db:
            stmt = select(AuditSession).order_by(AuditSession.started_at.desc()).limit(limit)
            result = await db.execute(stmt)
            sessions = result.scalars().all()

            # Serialize for JSON
            return {
                "sessions": [
                    {
                        "session_id": s.id,
                        "role": s.role,
                        "user_id": s.user_id,
                        "user_email": s.user_email,
                        "user_name": display_name(s.user_id),
                        "started_at": s.started_at.isoformat() + "Z" if s.started_at else None,
                        "ended_at": s.ended_at.isoformat() + "Z" if s.ended_at else None,
                        "status": s.status,
                        "query_count": s.query_count,
                        "final_risk_score": s.final_risk_score,
                        "peak_risk_score": s.peak_risk_score,
                        "final_behavioral_mode": s.final_behavioral_mode,
                        "highest_behavioral_mode": s.highest_behavioral_mode
                    }
                    for s in sessions
                ]
            }
    except Exception as e:
        logger.error(f"Error fetching sessions: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch audit sessions")

@router.get("/audit/recent")
async def get_recent_queries(limit: int = Query(50, ge=1, le=500), user_id: str | None = None):
    """
    Retrieve the most recent queries, newest first: across ALL users (the admin
    live feed), or only one user's when user_id is given (the user detail page).
    """
    try:
        async with AsyncSessionLocal() as db:
            stmt = select(AuditQuery)
            if user_id:
                stmt = stmt.where(AuditQuery.user_id == user_id)
            stmt = stmt.order_by(AuditQuery.timestamp.desc()).limit(limit)
            result = await db.execute(stmt)
            queries = result.scalars().all()

            return {"queries": [_serialize_query(q) for q in queries]}
    except Exception as e:
        logger.error(f"Error fetching recent queries: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch recent queries")

@router.get("/audit/alerts/status")
async def alert_status():
    """Which alert channels are configured on the server."""
    return {"channels": configured_channels()}

@router.post("/audit/alerts/test")
async def send_test_alert(admin: User = Depends(current_user)):
    """Send a test alert to every configured channel and report what happened."""
    channels = configured_channels()
    if not channels:
        raise HTTPException(status_code=400, detail="No alert channels configured. Set TELEGRAM_* and/or SMTP_* in backend/.env.")
    results = await send_alert(
        "AegisGraph test alert",
        f"Alerts are working. Sent by {admin.email or admin.user_id} from the admin dashboard.",
    )
    return {"results": results}

@router.get("/audit/sessions/{session_id}/queries")
async def get_session_queries(session_id: str):
    """
    Retrieve all queries for a specific session.
    """
    try:
        async with AsyncSessionLocal() as db:
            stmt = select(AuditQuery).where(AuditQuery.session_id == session_id).order_by(AuditQuery.timestamp.asc())
            result = await db.execute(stmt)
            queries = result.scalars().all()

            return {"queries": [_serialize_query(q) for q in queries]}
    except Exception as e:
        logger.error(f"Error fetching queries: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch session queries")
