"""API-level checks for the authentication model (no Neo4j / LLM needed)."""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api import chat
from app.core.config import settings
from app.main import app
from app.security.auth import User, current_user
from app.security.tickets import issue_ticket

client = TestClient(app)
FAKE_RESULT = {"answer": "ok", "intent": "employee_lookup", "retrieval": {}, "telemetry": None}


@pytest.fixture(autouse=True)
def _clean_overrides():
    yield
    app.dependency_overrides.clear()


def login_as(user_id: str, role: str = "Standard"):
    app.dependency_overrides[current_user] = lambda: User(user_id, role)


def test_chat_requires_login():
    assert client.post("/api/v1/chat", json={"query": "hi"}).status_code == 401


def test_audit_requires_login_and_admin_role():
    assert client.get("/api/v1/audit/sessions").status_code == 401
    login_as("u1", "Analyst")
    assert client.get("/api/v1/audit/sessions").status_code == 403
    assert client.get("/api/v1/audit/sessions/x/queries").status_code == 403


def test_role_in_request_body_is_ignored():
    login_as("u1", "Standard")
    with patch("app.api.chat.graph_rag_service.generate_answer", new_callable=AsyncMock, return_value=FAKE_RESULT) as gen:
        r = client.post("/api/v1/chat", json={"query": "hi", "role": "Auditor"})
    assert r.status_code == 200
    assert gen.call_args.kwargs["role"] == "Standard"
    assert gen.call_args.kwargs["user_id"] == "u1"


def test_another_users_ticket_is_not_honored():
    ticket, sid = issue_ticket("alice")
    login_as("mallory")
    with patch("app.api.chat.graph_rag_service.generate_answer", new_callable=AsyncMock, return_value=FAKE_RESULT):
        r = client.post("/api/v1/chat", json={"query": "hi", "session_token": ticket})
    assert r.json()["session_id"] != sid


def test_own_ticket_continues_the_session():
    ticket, sid = issue_ticket("alice")
    login_as("alice")
    with patch("app.api.chat.graph_rag_service.generate_answer", new_callable=AsyncMock, return_value=FAKE_RESULT):
        r = client.post("/api/v1/chat", json={"query": "hi", "session_token": ticket})
    assert r.json()["session_id"] == sid


def test_risk_reset_is_off_unless_demo_flag_set():
    login_as("u1", "Auditor")
    with patch.object(settings, "DEMO_ALLOW_RISK_RESET", False):
        assert client.post("/api/v1/session/reset").status_code == 403
    with patch.object(settings, "DEMO_ALLOW_RISK_RESET", True):
        assert client.post("/api/v1/session/reset").status_code == 200


def test_ordinary_users_can_never_reset_their_risk():
    login_as("u1", "Standard")
    with patch.object(settings, "DEMO_ALLOW_RISK_RESET", True):
        assert client.post("/api/v1/session/reset").status_code == 403


def test_second_question_while_first_is_running_is_refused():
    login_as("busy")
    lock = chat._user_locks["busy"]
    with patch.object(lock, "locked", return_value=True),          patch("app.api.chat.graph_rag_service.generate_answer", new_callable=AsyncMock, return_value=FAKE_RESULT) as gen:
        r = client.post("/api/v1/chat", json={"query": "hi"})
    assert r.status_code == 429
    gen.assert_not_called()
