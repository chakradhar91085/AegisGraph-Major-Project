# Phase 4C.2 — Policy Enforcement in Retrieval

## 1. Execution Timing

A critical security requirement is ensuring the correct timing of policy application. The policy must restrict the *current* query based on the risk accumulated *before* the query executes.

```
Previous EWMA → Current Policy → Retrieval → New Telemetry → Next EWMA
```

This prevents a circular dependency where the current query's retrieval results affect the risk score that determines how much data the current query is allowed to retrieve.

**Verification**: `tests/test_policy_timing.py` explicitly proves this ordering.

## 2. max_depth Enforcement

The `RetrievalService` (`app/retrieval/service.py`) acts as the enforcement point for the graph depth restriction (`d_eff`).

Every retrieval intent is mapped to a required depth:

```python
INTENT_DEPTH_MAP = {
    RetrievalIntent.EMPLOYEE_LOOKUP: 0,
    RetrievalIntent.SENT_EMAILS: 2,
    RetrievalIntent.RECEIVED_EMAILS: 2,
    RetrievalIntent.EMAIL_CHUNKS: 3,
    RetrievalIntent.CHUNK_ENTITIES: 4,
    RetrievalIntent.ENTITY_RELATIONSHIPS: 5,
    RetrievalIntent.UNSUPPORTED: 0
}
```

The service checks the required depth against the policy-supplied `max_depth`:

```python
required_depth = INTENT_DEPTH_MAP.get(intent, 5)
if required_depth > request.max_depth:
    return RetrievalResponse(..., strategy="blocked_by_policy")
```

## 3. Behavior when d_eff = 0

At HIGH risk (`Γ̄_t > 0.7`), the attenuation factor `κ_t` approaches 0, driving `d_eff` to 0.

When `d_eff = 0`:
- Graph-expanding strategies (depth 2-5) require depth > 0, so they are **blocked**.
- `EMPLOYEE_LOOKUP` is mapped to depth 0, so it **remains permitted**.

This ensures the system degrades gracefully under attack, allowing basic identity verification while preventing deeper graph traversals.

## 4. RetrievalRequest Bypass Fix

During Phase 4C.2, a vulnerability was identified where `RetrievalRequest` defaulted `max_depth` to 5. A direct call to the retrieval service could silently bypass depth restrictions.

**Correction**: The default value was removed. `max_depth` must now be explicitly supplied by the orchestrator (which receives it from the policy engine).

## 5. Tests

The retrieval test suite (`tests/test_retrieval.py`) verifies:
- `RetrievalRequest` cannot silently default `max_depth`
- `d_eff = 0` blocks graph-expanding strategies (`blocked_by_policy`)
- `d_eff = 0` permits non-expansive base lookups (`employee_lookup`)

## 6. Limitations

1. **Intent-to-depth is an abstraction**: The depth map represents conceptual information exposure, not the physical Neo4j hop count of the Cypher query.
2. **Binary depth blocking**: Depth is enforced as a strict cutoff. If `max_depth = 2`, an `EMAIL_CHUNKS` intent (depth 3) is completely blocked, rather than returning partial depth-2 information (which is not supported by the current Cypher architecture).
