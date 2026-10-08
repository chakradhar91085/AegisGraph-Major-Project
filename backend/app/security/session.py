from typing import Dict, List
import time
import logging
from app.core.config import settings
from app.security.models import SessionState, QueryRecord

logger = logging.getLogger(__name__)

class SessionStore:
    def __init__(self):
        # In-memory session store for Phase 4A
        self.sessions: Dict[str, SessionState] = {}

    def get_or_create_session(self, session_id: str) -> SessionState:
        if session_id not in self.sessions:
            self.sessions[session_id] = SessionState(session_id=session_id)
        return self.sessions[session_id]

    def cleanup_old_history(self, session_id: str, current_time: float):
        """
        Removes query records that fall outside the configured temporal window.
        """
        if session_id not in self.sessions:
            return
            
        state = self.sessions[session_id]
        window = settings.SECURITY_TEMPORAL_WINDOW_SECONDS
        
        cutoff_time = current_time - window

        # Keep records within the window (used for temporal/entity signals).
        new_history = [q for q in state.history if q.timestamp >= cutoff_time]

        # Always retain the single most recent query even if it falls just
        # outside the window, since the semantic-focus and temporal signals
        # need it as the reference point for the *next* query.
        if state.history and not new_history:
            new_history = [state.history[-1]]
            
        state.history = new_history

    def add_query_record(self, session_id: str, record: QueryRecord):
        state = self.get_or_create_session(session_id)
        state.history.append(record)

    def decayed_risk(self, session_id: str, now: float) -> float:
        """Remembered risk after idle decay: it halves every SECURITY_RISK_HALF_LIFE_SECONDS."""
        state = self.get_or_create_session(session_id)
        if not state.last_seen:
            return state.last_smoothed_risk
        idle = now - state.last_seen
        return state.last_smoothed_risk * 0.5 ** (idle / settings.SECURITY_RISK_HALF_LIFE_SECONDS)

    def update_smoothed_risk(self, session_id: str, risk: float):
        state = self.get_or_create_session(session_id)
        state.last_smoothed_risk = risk

    def reset(self, key: str):
        self.sessions.pop(key, None)

session_store = SessionStore()
