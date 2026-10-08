# Phase 9C.2 — Natural Language Query Understanding Architecture

## 1. Phase Objective
The objective of this phase is to design a secure, flexible query-understanding architecture that allows AegisGraph to interpret natural-language requests without relying solely on rigid regex patterns. The goal is to make the system feel conversational and intelligent while strictly preserving the integrity of the behavioral security pipeline and preventing arbitrary graph access.

## 2. Current Architecture and Limitations
**Current Flow:** 
`User Query -> intent_classifier.py (Regex) -> Validated Intent -> Security Telemetry -> Adaptive Policy -> Retrieval`

**Limitation:**
The `intent_classifier.py` relies exclusively on sequential regex matching (`INTENT_RULES`). If a user submits a semantically valid but structurally novel query (e.g., "Who works at Enron?"), the regex fails, and the system defaults to the `UNSUPPORTED` intent. This forces users to memorize specific command-like phrasing, severely hindering the natural discoverability of the knowledge graph.

## 3. Architecture Options Considered
We evaluated several approaches for replacing or supplementing the regex classifier:

- **Option A: Expanded Deterministic Rules (Regex ++)**
  - *Pros:* Zero latency, zero hallucination risk, highly predictable.
  - *Cons:* Unsustainable to maintain. Impossible to predict every natural language variation.
- **Option B: Embedding-Based Semantic Router**
  - *Pros:* Fast (if using a lightweight local model like `all-MiniLM-L6-v2`), handles semantic variations well.
  - *Cons:* Introduces a new dependency stack (e.g., `sentence-transformers` or `langchain`), requires maintaining reference embeddings for each intent.
- **Option C: Pure LLM Intent Interpretation**
  - *Pros:* Maximum flexibility.
  - *Cons:* High latency (every query requires an LLM call before retrieval, then a second LLM call for generation). 
- **Option D: Hybrid Router (Regex + LLM Fallback)**
  - *Pros:* Balances speed and flexibility. Known queries bypass the LLM for zero latency. Unrecognized queries utilize a strict, zero-shot classification prompt to the LLM to map the query to a predefined schema.

## 4. Recommended Approach
**Recommendation: Option D (Hybrid Router with Local Ollama Fallback)**

We will implement a hybrid query understanding layer.
1. The system will first attempt deterministic classification using the existing regex rules.
2. If the regex falls through to `UNSUPPORTED`, the system will intercept the query and send a specialized, structured prompt to the existing local Ollama instance (`qwen2.5-coder:7b`).
3. The LLM will be instructed to classify the query into exactly one of the strings defined in the `RetrievalIntent` enum (e.g., `employee_lookup`, `graph_discovery`, etc.).
4. The output will be strictly validated against the enum. If the LLM hallucinates an invalid string, it safely defaults back to `UNSUPPORTED`.

## 5. Proposed Structured Intent Contract
The LLM will be prompted to return a raw JSON object (or exact string) conforming to this contract:
```json
{
  "intent": "employee_lookup" | "sent_emails" | "graph_discovery" | "unsupported_intent"
}
```
The output of the classifier is mathematically constrained to this set. It cannot output Cypher commands or system instructions.

## 6. Security Invariants Preserved
This architecture is structurally incapable of bypassing the AegisGraph security pipeline because:
1. **No Arbitrary Cypher:** The LLM's only job in this phase is to pick a key from a dictionary. The actual database execution remains securely locked behind `RetrievalService`'s parameterized methods.
2. **Telemetry Intact:** The `AegisSecurityService` will continue to analyze the **original, unmodified user query** for semantic drift and entity focus, ensuring that an attacker cannot disguise a probing sequence by having the LLM "normalize" their intent.
3. **Policy Supremacy:** Regardless of what intent the LLM selects, the `AdaptivePolicy` will still clamp the `max_depth` and `limit` before execution.

## 7. Proposed Integration Flow
```text
User Query
    ↓
Intent Classifier (Regex pass)
    ↓ (if Unsupported)
OllamaClient (Intent Extraction Prompt)
    ↓
Validated Intent (String Enum)
    ↓
AegisSecurityService.observe_query(original_query)
    ↓
Adaptive Policy (Depth/Context Limits)
    ↓
RetrievalService.execute(Validated Intent)
    ↓
Context Builder
    ↓
OllamaClient (Generation Prompt)
```

## 8. Failure and Fallback Behavior
- **LLM Timeout / Connection Error:** The classifier traps the exception and returns `UNSUPPORTED`.
- **LLM Hallucination:** If the LLM returns "find_users" instead of "employee_lookup", the parser fails validation and returns `UNSUPPORTED`.
- **Ambiguous Queries:** If the LLM cannot confidently map the query, it is instructed to return `UNSUPPORTED`.

## 9. Implementation Plan for Next Phase
1. Add an `extract_intent` method to `OllamaClient` or a dedicated `llm_router.py`.
2. Update `intent_classifier.py` to become `async`, enabling it to call the LLM fallback.
3. Update `RetrievalService` and `GraphRAGService` to handle the asynchronous intent classification.
4. Validate that the telemetry pipeline still receives the exact original user string.

*Explicit Confirmation: No application code was modified during this Phase 9C.2 architecture planning and inspection stage.*
