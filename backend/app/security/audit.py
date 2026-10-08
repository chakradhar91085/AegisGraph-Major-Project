import json
import os
from pathlib import Path
from typing import Dict, Any
import logging
import datetime
from sqlalchemy.future import select
from app.db.postgres import AsyncSessionLocal
from app.security.db_models import AuditSession, AuditQuery

logger = logging.getLogger(__name__)

SEVERITY_ORDER = {"ALLOW": 0, "MASK": 1, "RESTRICT": 2, "BLOCK": 3}

class PostgresAuditLogger:
    async def log_event_async(self, telemetry: Dict[str, Any], llm_provider: str = None):
        try:
            session_id = telemetry.get("session_id")
            if not session_id:
                return

            role = telemetry.get("role", "Standard")
            smoothed_risk = telemetry.get("smoothed_risk", 0.0)
            behavioral_mode = telemetry.get("response_mode", "ALLOW")
            
            # Determine Retrieval Outcome
            blocked_by_policy = telemetry.get("blocked_by_policy", False)
            retrieval_strategy = telemetry.get("retrieval_strategy", "")
            
            outcome = "PERMITTED"
            is_masked = False
            is_attenuated = False
            is_blocked = False
            
            if blocked_by_policy or retrieval_strategy == "blocked_by_policy":
                outcome = "BLOCKED"
                is_blocked = True
            elif behavioral_mode == "RESTRICT":
                outcome = "ATTENUATED"
                is_attenuated = True
            elif behavioral_mode == "MASK":
                outcome = "MASKED"
                is_masked = True
                
            timestamp = telemetry.get("timestamp", 0)
            dt_timestamp = datetime.datetime.fromtimestamp(timestamp)

            async with AsyncSessionLocal() as db:
                # Get or Create Session
                stmt = select(AuditSession).where(AuditSession.id == session_id)
                result = await db.execute(stmt)
                session = result.scalar_one_or_none()
                
                if not session:
                    session = AuditSession(
                        id=session_id,
                        role=role,
                        user_id=telemetry.get("user_id"),
                        user_email=telemetry.get("user_email"),
                        started_at=dt_timestamp,
                        query_count=1,
                        final_risk_score=smoothed_risk,
                        peak_risk_score=smoothed_risk,
                        final_behavioral_mode=behavioral_mode,
                        highest_behavioral_mode=behavioral_mode
                    )
                    db.add(session)
                else:
                    # Update session
                    session.query_count += 1
                    session.final_risk_score = smoothed_risk
                    session.final_behavioral_mode = behavioral_mode
                    
                    if smoothed_risk > session.peak_risk_score:
                        session.peak_risk_score = smoothed_risk
                        
                    current_highest_sev = SEVERITY_ORDER.get(session.highest_behavioral_mode, 0)
                    new_sev = SEVERITY_ORDER.get(behavioral_mode, 0)
                    if new_sev > current_highest_sev:
                        session.highest_behavioral_mode = behavioral_mode
                
                # Create Query record
                audit_query = AuditQuery(
                    session_id=session_id,
                    timestamp=dt_timestamp,
                    query=telemetry.get("query", ""),
                    intent=telemetry.get("intent", ""),
                    risk_score=smoothed_risk,
                    behavioral_mode=behavioral_mode,
                    retrieval_outcome=outcome,
                    masked=is_masked,
                    attenuated=is_attenuated,
                    blocked=is_blocked,
                    result_count=telemetry.get("result_count", 0),
                    role=role,
                    user_id=telemetry.get("user_id"),
                    user_email=telemetry.get("user_email"),
                    llm_provider=llm_provider,
                    instantaneous_risk=telemetry.get("instantaneous_risk", 0.0),
                    signals=telemetry.get("signals"),
                    policy=telemetry.get("policy"),
                )
                db.add(audit_query)
                
                await db.commit()
                
        except Exception as e:
            logger.error(f"Failed to write audit log to postgres: {e}")

audit_logger = PostgresAuditLogger()
