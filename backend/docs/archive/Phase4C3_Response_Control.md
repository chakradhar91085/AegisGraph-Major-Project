# Phase 4C.3 — Adaptive Response Control

## 1. End-to-End Orchestration

Phase 4C.3 integrates the adaptive policy (Phase 4C.1) and retrieval enforcement (Phase 4C.2) into the main `GraphRAGService` orchestrator (`app/rag/service.py`). This completes the end-to-end security feedback loop.

### Integrated Pipeline

1. **Pre-Retrieval Observation**: `aegis_security.observe_query()` computes semantic drift and returns the `AdaptivePolicy` based on the *previous* EWMA risk.
2. **Policy Application**: `GraphRAGService` applies the policy's limits to the `RetrievalRequest`.
3. **Retrieval**: `RetrievalService` enforces `max_depth` and executes the query subject to the hardware `limit`.
4. **Post-Retrieval Observation**: `aegis_security.calculate_risk()` computes the remaining signals, fuses them, updates the EWMA risk, and logs the telemetry event.
5. **Context Truncation**: `ContextBuilder` enforces the policy's `effective_context_limit`.
6. **LLM Generation**: The truncated, grounded context is sent to the LLM.

## 2. Context Truncation Enforcement

While `RetrievalService` enforces the hardware limit on the number of records retrieved from Neo4j, `ContextBuilder` (`app/rag/context_builder.py`) performs a secondary enforcement step before constructing the system prompt.

```python
limit = min(effective_limit, self.max_records)
results_to_process = response.results[:limit]
```

This dual-layer enforcement ensures that even if retrieval logic changes, the context passed to the LLM will strictly adhere to the policy's `effective_context_limit`.

## 3. Short-Circuit Paths

The `GraphRAGService` implements short-circuit paths to bypass the LLM when appropriate, reducing latency and cost:

1. **Unsupported Intent**: Returns a canned "unsupported" message. Telemetry is still calculated to track anomalous probing.
2. **Zero Results**: Returns a canned "no results found" message. Telemetry is still calculated.
3. **Blocked by Policy**: Handled naturally by the zero-results short-circuit, as blocked queries return zero results.

## 4. Signal Behavior During High Risk

When the session reaches HIGH risk (`Γ̄_t > 0.7`):

1. **Policy Calculation**: `κ_t` approaches 0.
2. **Limits**: `d_eff = 0`, `k_eff = 1`.
3. **Retrieval**: Deep intents are blocked (`blocked_by_policy`). `EMPLOYEE_LOOKUP` is permitted but limited to 1 record.
4. **LLM Generation**: Bypassed for blocked queries. For permitted queries, the LLM receives highly truncated context (1 record) and must answer based only on that sparse information.
5. **Telemetry**: The blocked query still generates telemetry. `S_sem` and `S_temp` operate normally. `S_graph` is 0.0 due to the zero-result safeguard.

## 5. Security Posture

This architecture achieves the primary goal of AegisGraph: **Information exposure degrades gracefully in response to suspicious behavior.**

Rather than a binary ALLOW/DENY decision (which attackers can map and evade), the system gradually tightens context limits and graph depth boundaries, increasing the cost of extraction and limiting the blast radius of a successful compromise, while maintaining high utility for benign users.

## 6. Limitations

1. **No Adaptive System Prompt**: The system prompt currently remains static regardless of risk level. Future phases could dynamically inject warning instructions or redaction directives based on risk.
2. **No Decoys or Noise**: The prototype does not inject honeypot records or differential privacy noise at high risk levels.
3. **LLM Context Window**: The policy limits the *number of records*, not the absolute *token count*. Individual chunks can vary in length, making token usage unpredictable.
