# Phase 9C.3: Hybrid Natural Language Intent Routing

## 1. Phase Objective
Improve the natural-language flexibility of the AegisGraph chat interface. The system must understand conversational variations of supported queries (e.g., "Who works at Enron?") without requiring users to conform strictly to rigid database schema phrasing or predefined regex patterns. Crucially, this must be accomplished without bypassing the security pipeline or hallucinating arbitrary Cypher.

## 2. Previous Regex-Only Limitation
Prior to this phase, `intent_classifier.py` relied exclusively on a sequential regex loop. While fast and deterministic, it failed on any novel phrasing that was semantically valid but structurally unseen. Queries that failed regex matching were hard-defaulted to `unsupported_intent`, heavily restricting chat discoverability.

## 3. Hybrid Router Architecture
We implemented a hybrid intent classification layer:
- **Fast Path (Deterministic):** The system first evaluates the query against the existing regex `INTENT_RULES`. If a match is found, it immediately resolves with zero LLM overhead.
- **Slow Path (Fallback):** If the regex yields `UNSUPPORTED`, the router intercepts the request and sends a strictly constrained zero-shot prompt to the local Ollama instance (`qwen2.5-coder:7b`).

## 4. LLM Classification Constraints
The LLM is treated as an untrusted environment. It is given a system prompt instructing it to act as a strict classification engine and output exactly one JSON object containing the intent. The prompt actively restricts the output domain to only the known, allowlisted `RetrievalIntent` enums.

## 5. Allowlist Validation Process
The LLM output is not executed directly. The backend parses the LLM's JSON response and attempts to cast the value back into the `RetrievalIntent` Enum.
- If the value matches an allowed enum, the intent is safely accepted.
- If the LLM hallucinates an `invented_intent`, outputs malformed JSON, or fails entirely, a `ValueError` is caught, and the system safely defaults to `UNSUPPORTED`.

## 6. Security Invariants Preserved
This phase strictly preserved the AegisGraph security model:
1. **No Cypher Generation:** The LLM intent fallback selects only an Enum string. It cannot generate arbitrary Cypher or database execution instructions.
2. **Policy Enforcement Intact:** The resulting intent still flows through the `RetrievalService` which enforces `max_depth` limits via the `INTENT_DEPTH_MAP`.
3. **Telemetry Integrity:** The LLM does NOT modify the original user query. The exact, raw string inputted by the user is passed directly to `aegis_security.observe_query` and `aegis_security.calculate_risk`. Semantic similarity, temporal tracking, and risk accumulation apply exactly as before.

## 7. Failure Handling
The system handles LLM unavailability smoothly. If the `httpx` request to Ollama times out (configured to 10.0 seconds) or the service is down, the exception is caught, logged, and `unsupported_intent` is returned. A failure in classification will never crash the backend endpoint.

## 8. Tests Performed and Results
An updated testing suite (`tests/test_retrieval.py`) validated the hybrid router:
- **Fast Path:** Regex classification continued to pass (0 latency overhead).
- **Fallback Success (Mocked):** A semantically valid fallback correctly yielded `all_employees`.
- **Hallucination Safety (Mocked):** An LLM hallucination of `invented_intent` was successfully rejected and safely clamped to `unsupported_intent`.
- **Overall Suite:** 38/38 integration tests passed, confirming no security or retrieval capabilities were broken.

## 9. Manual Runtime Verification
A local runtime test was performed using `qwen2.5-coder:7b` via Ollama.
- **Query:** `"Who works at Enron?"`
- **Result:** The LLM successfully parsed the novel phrasing and returned `{"intent": "all_employees"}`. The Python backend safely validated it, executed the parameterized retrieval, and returned 19 employees. All behavioral telemetry metrics (`instantaneous_risk`, `smoothed_risk`) were correctly logged and preserved in the final JSON response.

## 10. Limitations
The primary limitation is the latency overhead (typically 1-3 seconds) introduced for queries that miss the regex fast path, dependent on local GPU hardware capabilities.
