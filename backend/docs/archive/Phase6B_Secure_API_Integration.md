# Phase 6B — Secure API Integration

## 1. Objective
The objective of Phase 6B is to securely prepare the AegisGraph API layer for frontend integration by implementing two critical corrections identified during Phase 6A: enabling cross-query session continuity for behavioral tracking, and removing public API access to the unsecured retrieval endpoints.

## 2. Problem Identified in Phase 6A
- **API Session Continuity Issue**: The primary `POST /api/v1/chat` endpoint previously generated a random `uuid4` on every incoming request. Because a client could not submit their own session identifier, it was impossible to link consecutive queries to the same user session. Consequently, behavioral history (semantic drift, temporal frequency) and exponential moving average (EWMA) risk could not accumulate across API requests.
- **Public Retrieval Bypass Issue**: The `POST /api/v1/retrieval/query` endpoint mapped directly to the `RetrievalService` and was exposed on the public FastAPI router. This provided a critical bypass vulnerability where a malicious client could execute raw graph retrievals without being subjected to `AegisSecurityService` observation or `AdaptivePolicy` context reduction.

## 3. Implementation
- **ChatRequest Changes**: Modified the Pydantic `ChatRequest` schema in `app/api/chat.py` to include `session_id: Optional[str] = None`.
- **Session Lifecycle**: Updated the `chat_endpoint` logic to reuse the client-provided `session_id` if present. If absent, the backend safely generates a new UUID. The active `session_id` is always passed through to `GraphRAGService` and returned in the `ChatResponse`.
- **Public Route Changes**: Removed `app.include_router(retrieval_router...)` from `app/main.py`. 
- **Preserved Secure Execution Path**: The only remaining public query vector is `/api/v1/chat`, enforcing the strict execution path: *Client → GraphRAGService → Security Observation → Adaptive Policy → RetrievalService → ContextBuilder → LLM*.

## 4. API Contract

### New conversation request
When initiating a new session, the client omits the `session_id`:
```json
{
    "query": "Who is Christopher Calger?"
}
```

### New conversation response
The backend provisions a new session and returns it alongside the generated answer and comprehensive telemetry:
```json
{
  "answer": "Christopher Calger is an employee...",
  "session_id": "a1b2c3d4-e5f6-7890",
  "intent": "employee_lookup",
  "retrieval": {
    "result_count": 1,
    "strategy": "employee_lookup"
  },
  "status": "success",
  "telemetry": {
    "session_id": "a1b2c3d4-e5f6-7890",
    "timestamp": 1787222056.559,
    "query": "Who is Christopher Calger?",
    "intent": "employee_lookup",
    "retrieval_strategy": "employee_lookup",
    "result_count": 1,
    "signals": {
      "semantic_drift": 0.0,
      "temporal_frequency": 0.0,
      "entity_focus": 0.0,
      "graph_footprint": 0.21
    },
    "instantaneous_risk": 0.0525,
    "smoothed_risk": 0.0157,
    "policy": {
      "attenuation_factor": 1.0,
      "effective_context_limit": 20,
      "effective_graph_depth": 5
    }
  }
}
```

### Follow-up request using session_id
The client preserves state by supplying the `session_id` in subsequent requests:
```json
{
    "query": "What emails did he send?",
    "session_id": "a1b2c3d4-e5f6-7890"
}
```

## 5. Security Impact
Removing the public `/api/v1/retrieval/query` route ensures that external clients **cannot** bypass the security telemetry layer. Every query must now traverse the `AegisSecurityService`, guaranteeing that:
- Behavioral telemetry ($S_{sem}$, $S_{temp}$, $S_{ent}$, $S_{graph}$) is actively monitored.
- EWMA risk effectively accumulates across the unified session ID.
- The `AdaptivePolicy` can mathematically enforce $k_{eff}$ (context reduction) and $d_{eff}$ (graph-depth restriction) without any loopholes.

## 6. Limitations
- **In-Memory Session State**: The current `session_store` is purely in-memory. If the FastAPI server restarts, all behavioral history and EWMA risk progression for active session IDs will be cleared.
- **No Authentication**: This prototype iteration remains unauthenticated. The API relies entirely on the behavioral telemetry model rather than traditional RBAC to throttle excessive data extraction.
