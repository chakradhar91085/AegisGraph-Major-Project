import time
import logging
from typing import Any, Dict
from app.security.models import TelemetryEvent, SignalValues, QueryRecord
from app.security.session import session_store
from app.security.embeddings import embedding_provider
from app.security.signals import signals_calculator
from app.security.risk import risk_engine
from app.security.policy import policy_engine
from app.security.gates import gate_check
from app.security.alerts import notify
from app.security import exposure
from app.security.audit import SEVERITY_ORDER
from app.retrieval.schemas import RetrievalResponse
from app.core.config import settings

logger = logging.getLogger(__name__)

# Sensitive emails in a single answer that trigger an admin alert.
SENSITIVE_PULL_ALERT = 5

class AegisSecurityService:
    async def observe_query(self, session_id: str, query: str, role: str = "Standard", user_id: str | None = None, user_email: str | None = None) -> Dict[str, Any]:
        """
        Step 1: Pre-retrieval observation.
        Fetches embedding, calculates the semantic-focus signal over the
        recent query window, returns partial context.

        Risk memory is keyed by user_id (falling back to session_id), so a
        client cannot shed its risk by starting a new session.
        """
        current_time = time.time()
        risk_key = user_id or session_id

        # Cleanup old history based on temporal window
        session_store.cleanup_old_history(risk_key, current_time)

        # Fetch current embedding
        current_embedding = await embedding_provider.get_embedding(query)

        # Semantic focus looks at a small sliding window of recent queries
        # (paper Eq. 1), not just the single previous one.
        state = session_store.get_or_create_session(risk_key)
        state.last_smoothed_risk = session_store.decayed_risk(risk_key, current_time)
        state.last_seen = current_time
        window_size = settings.SECURITY_SEMANTIC_WINDOW_SIZE
        prior_count = max(0, window_size - 1)
        prior_embeddings = (
            [q.embedding for q in state.history[-prior_count:] if q.embedding]
            if prior_count > 0 else []
        )
        window_embeddings = prior_embeddings + ([current_embedding] if current_embedding else [])
        semantic_focus = signals_calculator.calculate_semantic_focus(window_embeddings)

        # Adaptive policy uses the smoothed risk BEFORE this query, raised to
        # the hard-gate floor if this query itself is an obvious attack.
        gate, gate_reason = gate_check(query)
        current_policy = policy_engine.calculate_policy(max(state.last_smoothed_risk, gate), role)

        return {
            "session_id": session_id,
            "risk_key": risk_key,
            "user_id": user_id,
            "user_email": user_email,
            "gate": gate,
            "gate_reason": gate_reason,
            "query": query,
            "role": role,
            "timestamp": current_time,
            "embedding": current_embedding,
            "semantic_focus": semantic_focus,
            "policy": current_policy
        }

    async def calculate_risk(self, ctx: Dict[str, Any], retrieval_response: RetrievalResponse) -> TelemetryEvent:
        """
        Step 2: Post-retrieval observation.
        Calculates remaining signals (temporal, entity, graph), fuses risk, and updates session.
        """
        session_id = ctx["session_id"]
        risk_key = ctx["risk_key"]
        current_time = ctx["timestamp"]
        
        # People the agent's rows named, so no separate entity-extraction pass is needed.
        entities = retrieval_response.entities

        # Get history for temporal and entity calculations.
        # History currently does NOT include the CURRENT query yet.
        state = session_store.get_or_create_session(risk_key)
        history = [q for q in state.history if q.timestamp >= (current_time - settings.SECURITY_TEMPORAL_WINDOW_SECONDS)]

        temporal_frequency = signals_calculator.calculate_temporal_frequency(history, current_time)

        # Calculate Entity Focus (including current query's entities)
        # Create a temporary history list adding the current record
        temp_history = history + [QueryRecord(timestamp=current_time, query=ctx["query"], entities=entities)]
        entity_focus = signals_calculator.calculate_entity_focus(temp_history)
        
        # Calculate Graph Footprint
        graph_footprint = signals_calculator.calculate_graph_footprint(
            intent=retrieval_response.intent,
            result_count=retrieval_response.result_count
        )
        
        # Sensitivity exposure: what this answer touched, added to a fading per-user total.
        answer_exposure = await exposure.measure(retrieval_response.results)
        state.exposure = exposure.accumulate(state.exposure, state.exposure_at, current_time,
                                             answer_exposure.get("units", 0.0))
        state.exposure_at = current_time

        signals = SignalValues(
            semantic_focus=ctx["semantic_focus"],
            temporal_frequency=temporal_frequency,
            entity_focus=entity_focus,
            graph_footprint=graph_footprint,
            sensitivity_exposure=exposure.signal(state.exposure),
        )
        
        # Fuse Risk
        gate = ctx["gate"]
        instantaneous_risk = max(risk_engine.calculate_instantaneous_risk(signals), gate)
        
        # EWMA Smoothing (a hard gate is a floor the smoothed score cannot dip below)
        prev_smoothed = state.last_smoothed_risk
        smoothed_risk = max(risk_engine.calculate_ewma(instantaneous_risk, prev_smoothed), gate)

        # Sensitive data already handed over keeps counting however long the user waits.
        session_store.add_ratchet(risk_key, answer_exposure.get("sensitive_units", 0.0), current_time)
        smoothed_risk = max(smoothed_risk, session_store.ratchet_floor(risk_key, current_time))
        
        # Persist to Session Store
        record = QueryRecord(
            timestamp=current_time,
            query=ctx["query"],
            embedding=ctx["embedding"],
            entities=entities
        )
        session_store.add_query_record(risk_key, record)
        session_store.update_smoothed_risk(risk_key, smoothed_risk)
        retrieval_executed = retrieval_response.strategy not in ("blocked_by_policy", "error", "count_limit")

        quarantined = retrieval_response.metadata.get("quarantined", 0)
        if quarantined:
            answer_exposure = {**answer_exposure, "quarantined": quarantined}
        self._alert_admin(ctx, state, smoothed_risk, answer_exposure)

        # Return Telemetry
        return TelemetryEvent(
            session_id=session_id,
            timestamp=current_time,
            query=ctx["query"],
            intent=retrieval_response.intent,
            retrieval_strategy=retrieval_response.strategy,
            result_count=retrieval_response.result_count,
            signals=signals,
            instantaneous_risk=instantaneous_risk,
            smoothed_risk=smoothed_risk,
            policy=ctx["policy"],
            blocked_by_policy=(retrieval_response.strategy == "blocked_by_policy" or ctx["policy"].response_mode == "BLOCK"),
            retrieval_executed=retrieval_executed,
            role=ctx.get("role", "Standard"),
            user_id=ctx.get("user_id"),
            user_email=ctx.get("user_email"),
            response_mode=ctx["policy"].response_mode,
            cypher_queries=retrieval_response.metadata.get("cypher", []),
            exposure=answer_exposure,
            retrieval_model=retrieval_response.metadata.get("agent_model"),
        )

    @staticmethod
    def _alert_admin(ctx: Dict[str, Any], state, smoothed_risk: float, answer_exposure: Dict[str, Any] | None = None) -> None:
        """Alert on a security-gate hit, a large pull of sensitive data, or when a
        user's mode escalates (ALLOW -> MASK -> BLOCK)."""
        mode = ctx["policy"].response_mode.value
        escalated = SEVERITY_ORDER[mode] > SEVERITY_ORDER.get(state.last_mode, 0)
        state.last_mode = mode

        events = []
        if ctx["gate"] > 0:
            events.append(ctx.get("gate_reason") or "Prompt-injection / privilege-escalation attempt detected")
        if answer_exposure and answer_exposure.get("quarantined"):
            events.append(f"Withheld {answer_exposure['quarantined']} retrieved email(s) containing text that looks like an attack")
        if escalated and mode == "BLOCK":
            events.append("Risk reached HIGH: this user's queries are now BLOCKED")
        elif escalated and mode == "MASK":
            events.append("Risk reached MEDIUM: names and emails are now MASKED for this user")
        if answer_exposure and answer_exposure.get("sensitive_items", 0) >= SENSITIVE_PULL_ALERT:
            labels = ", ".join(f"{n} {k}" for k, n in sorted(answer_exposure["labels"].items(), key=lambda kv: -kv[1]))
            events.append(f"Pulled {answer_exposure['sensitive_items']} sensitive emails in one answer ({labels}); "
                          f"most senior person involved: seniority {answer_exposure['max_seniority']}")
        if not events:
            return

        who = ctx.get("user_email") or ctx.get("user_id") or f"session {ctx['session_id'][:8]}"
        text = "\n".join(
            [f"- {e}" for e in events]
            + [
                "",
                f"User: {who} ({ctx.get('role', 'Standard')})",
                f"Risk score: {smoothed_risk:.2f}",
                f"Query: {ctx['query'][:300]}",
                f"Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ctx['timestamp']))}",
            ]
        )
        subject = "AegisGraph BLOCK alert" if mode == "BLOCK" else "AegisGraph security alert"
        notify(subject, text)

# Singleton
aegis_security = AegisSecurityService()
