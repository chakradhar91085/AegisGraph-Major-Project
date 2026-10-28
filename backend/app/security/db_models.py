from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
import datetime
import uuid
from app.db.postgres import Base

def get_utc_now():
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)

class AuditSession(Base):
    __tablename__ = "audit_sessions"
    
    id = Column(String, primary_key=True) # Maps to session_id
    role = Column(String, nullable=False, default="Standard")
    user_id = Column(String, nullable=True)
    user_email = Column(String, nullable=True)
    started_at = Column(DateTime, default=get_utc_now)
    ended_at = Column(DateTime, nullable=True)
    status = Column(String, default="ACTIVE") # ACTIVE, COMPLETED
    
    query_count = Column(Integer, default=0)
    final_risk_score = Column(Float, default=0.0)
    peak_risk_score = Column(Float, default=0.0)
    
    final_behavioral_mode = Column(String, default="ALLOW")
    highest_behavioral_mode = Column(String, default="ALLOW")
    
    queries = relationship("AuditQuery", back_populates="session", cascade="all, delete-orphan")


class AuditQuery(Base):
    __tablename__ = "audit_queries"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("audit_sessions.id"))
    timestamp = Column(DateTime, default=get_utc_now)
    
    query = Column(String, nullable=False)
    intent = Column(String, nullable=False)
    
    risk_score = Column(Float, nullable=False)
    behavioral_mode = Column(String, nullable=False) # ALLOW, MASK, RESTRICT, BLOCK
    
    retrieval_outcome = Column(String, nullable=False) # PERMITTED, MASKED, ATTENUATED, BLOCKED
    
    masked = Column(Boolean, default=False)
    attenuated = Column(Boolean, default=False)
    blocked = Column(Boolean, default=False)
    
    result_count = Column(Integer, default=0)
    role = Column(String, nullable=False)
    user_id = Column(String, nullable=True)
    user_email = Column(String, nullable=True)
    llm_provider = Column(String, nullable=True)

    # Full telemetry detail, previously computed but discarded — needed to
    # drive a global (cross-user) live risk view for the admin dashboard.
    instantaneous_risk = Column(Float, nullable=True)
    signals = Column(JSON, nullable=True)
    policy = Column(JSON, nullable=True)
    cypher_queries = Column(JSON, nullable=True)  # what the MCP agent ran, if it ran

    session = relationship("AuditSession", back_populates="queries")
