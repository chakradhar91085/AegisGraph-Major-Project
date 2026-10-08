import time

from app.security import service
from app.security.models import AdaptivePolicy, ResponseMode, RiskLevel, SessionState


def _ctx(mode: ResponseMode, gate: float = 0.0) -> dict:
    policy = AdaptivePolicy(
        risk_score=0.5, risk_level=RiskLevel.MEDIUM, attenuation_factor=0.5,
        effective_context_limit=5, effective_graph_depth=1, response_mode=mode,
    )
    return {"policy": policy, "gate": gate, "user_email": "cfo@corp.com", "role": "Analyst",
            "session_id": "abcdef123456", "query": "who is ken lay", "timestamp": time.time()}


def test_alerts_fire_on_escalation_and_gates_only(monkeypatch):
    sent = []
    monkeypatch.setattr(service, "notify", lambda subject, text: sent.append((subject, text)))
    state = SessionState(session_id="u1")
    alert = lambda mode, gate=0.0: service.AegisSecurityService._alert_admin(_ctx(mode, gate), state, 0.5)

    alert(ResponseMode.ALLOW)
    assert sent == []

    alert(ResponseMode.MASK)
    assert len(sent) == 1 and "MASKED" in sent[0][1] and "cfo@corp.com" in sent[0][1]

    alert(ResponseMode.MASK)
    assert len(sent) == 1  # staying at the same level is not news

    alert(ResponseMode.BLOCK)
    assert len(sent) == 2 and sent[1][0] == "AegisGraph BLOCK alert"

    alert(ResponseMode.ALLOW)  # risk decayed
    alert(ResponseMode.ALLOW, gate=0.65)
    assert len(sent) == 3 and "injection" in sent[2][1]
