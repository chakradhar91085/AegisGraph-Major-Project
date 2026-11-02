"""/chat/stream: server-sent events, one question per user."""
import json

import pytest
from fastapi.testclient import TestClient

from app.api import chat
from app.main import app
from app.security.auth import User, current_user
from app.rag.service import graph_rag_service


def parse(body: str):
    events = []
    for block in body.strip().split("\n\n"):
        kind, data = block.split("\n", 1)
        events.append((kind.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
    return events


@pytest.fixture
def client(monkeypatch):
    app.dependency_overrides[current_user] = lambda: User(user_id="stream-test", role="Standard", email=None)

    async def fake_answer(query, events=None, **_):
        events.put_nowait(("status", "Searching the knowledge graph…"))
        for piece in ["Hello", " there"]:
            events.put_nowait(("token", piece))
        return {"answer": "Hello there", "intent": "agent_query", "retrieval": {"status": "success"},
                "telemetry": {"response_mode": "ALLOW"}}

    monkeypatch.setattr(graph_rag_service, "generate_answer", fake_answer)
    yield TestClient(app)
    app.dependency_overrides.clear()
    chat._user_locks.pop("stream-test", None)


def test_streams_status_tokens_then_the_full_answer(client):
    r = client.post("/api/v1/chat/stream", json={"query": "hi"})
    assert r.headers["content-type"].startswith("text/event-stream")
    events = parse(r.text)
    assert [k for k, _ in events] == ["status", "token", "token", "done"]
    done = events[-1][1]
    assert done["answer"] == "Hello there" and done["session_token"] and done["status"] == "success"
    assert not chat._user_locks["stream-test"].locked()  # released: the next question can run


def test_second_question_while_one_runs_is_refused(client):
    import asyncio
    lock = chat._user_locks["stream-test"]
    asyncio.run(lock.acquire())  # pretend a question is in flight
    r = client.post("/api/v1/chat/stream", json={"query": "hi"})
    assert r.status_code == 429


def test_pipeline_failure_becomes_an_error_event(client, monkeypatch):
    async def boom(*a, **k):
        raise RuntimeError("down")
    monkeypatch.setattr(graph_rag_service, "generate_answer", boom)
    events = parse(client.post("/api/v1/chat/stream", json={"query": "hi"}).text)
    assert events == [("error", {"status": 500, "detail": "Internal server error during chat processing"})]
    assert not chat._user_locks["stream-test"].locked()
