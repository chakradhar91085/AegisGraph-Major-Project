# Phase 9C.1 — Conversational Retrieval and Chat Experience

## 1. The Usability Problem
During practical usage, AegisGraph felt restrictive. If a user asked a question that did not perfectly match one of the rigid intent patterns (like "Who are the employees?" or "What can I explore?"), the system immediately bypassed the LLM and responded with a hardcoded, unhelpful rejection: `"I can only answer questions related to employees, their emails, chunks of email content, and entity relationships in the Enron dataset."`

This required users to implicitly know the exact schema of the database to use the tool successfully, preventing natural knowledge discovery.

## 2. Changes Made to Improve Query Discoverability

### New Intents
To support natural discovery, we augmented the `intent_classifier.py` and `schemas.py` with two new retrieval intents:
1. `GRAPH_DISCOVERY`: Maps phrases like "What can I explore?", "Help", or "How does AegisGraph work?" to a built-in schema discovery query.
2. `ALL_EMPLOYEES`: Maps phrases like "Who are the employees?" or "List employees" to a broad query that retrieves top personnel.

### Retrieval Strategy Mapping
In `service.py`, we implemented specific handlers for these intents:
- `_handle_all_employees`: Executes the existing `lookup_employee_by_name` parameterized strategy with an empty string, safely returning a configurable limit of top employees.
- `_handle_graph_discovery`: Returns a static JSON summary of the AegisGraph schema (Employees, Emails, Chunks, Entities) without making an unnecessary database trip, providing safe, instant context to the LLM.

### Conversational Fallbacks
We completely overhauled the restrictive fallback behavior in the `GraphRAGService` orchestrator (`app/rag/service.py`):
- **Unsupported Queries**: Instead of a rigid rejection, unsupported intents now receive a polite, conversational fallback string: `"I'm AegisGraph, a secure Graph-RAG system over the Enron dataset. I don't see any information in the knowledge graph to answer that specific question. You can try exploring employees, their emails, or entity relationships."` This prevents the system from pretending to act like a general ChatGPT clone, while remaining helpful.
- **Empty Results**: Missing lookups (e.g., "Who is the CEO?") now return a slightly softer string: `"I searched the knowledge graph but couldn't find any information matching your query."` This allows the system to acknowledge the attempt without hallucinating data.

## 3. Security Pipeline Preservation
**Crucially, no security boundaries were bypassed.**
- The new intents (`ALL_EMPLOYEES`, `GRAPH_DISCOVERY`) are integrated directly into the standard `RetrievalService` pipeline.
- Both new intents trigger the exact same `aegis_security.observe_query()` and `aegis_security.calculate_risk()` methods as all other queries.
- `GRAPH_DISCOVERY` was assigned an intent depth of `0`, ensuring it can never be used to perform deep recursive graph traversals.
- The LLM orchestrator remains completely decoupled from security decisions.
- Unsupported queries still log telemetry to the backend, ensuring that probing behavior mapping the edges of the application is mathematically captured by the EWMA tracker.

## 4. Chat Input and Keyboard Improvements
In the frontend (`ChatPanel.tsx`), we resolved the frustrating input focus bug:
- Implemented a `useRef` attachment to the main textarea.
- Added a `useEffect` hook that automatically calls `inputRef.current?.focus()` whenever `loading` changes to `false`.
- This allows a user to submit a query, read the response, and immediately begin typing their next query without needing to grab the mouse.
- The Quick-Start queries were updated to reflect the new conversational intents (e.g., `"What can I explore in this knowledge graph?"`).

## 5. Test Queries and Observed Behavior

| Test Category | Query | Observed Behavior |
| :--- | :--- | :--- |
| **A. Knowledge Discovery** | "What can I explore?" | Classified as `GRAPH_DISCOVERY`. Security telemetry logs event. LLM returns a well-formatted summary of the Enron schema. |
| **B. Broad Graph Query** | "Who are the employees?" | Classified as `ALL_EMPLOYEES`. Telemetry logged. Neo4j retrieves top employees. LLM lists them. |
| **C. Known Entity Query** | "Who is Christopher Calger?" | Classified as `EMPLOYEE_LOOKUP`. Exact match found. LLM summarizes the person's node data. |
| **D. Missing Info Query** | "Who is the CEO?" | Classified as `EMPLOYEE_LOOKUP`. Name "the CEO" not found in DB. System responds gracefully with "I searched... but couldn't find any information." |
| **E. Unrelated Question** | "What is the capital of France?" | Classified as `UNSUPPORTED`. LLM is intentionally bypassed. System responds with the polite AegisGraph fallback explanation. |

## 6. Files Created and Modified
- **Modified**: `backend/app/retrieval/schemas.py` (Added intents)
- **Modified**: `backend/app/retrieval/intent_classifier.py` (Added regex rules)
- **Modified**: `backend/app/retrieval/service.py` (Added handler mapping and mock/broad retrievals)
- **Modified**: `backend/app/rag/service.py` (Improved fallback strings)
- **Modified**: `frontend/src/components/ChatPanel.tsx` (Added auto-focus ref and updated Quick-Starts)
- **Created**: `backend/docs/Phase9C1_Conversational_Retrieval_and_Chat_Experience.md`

## 7. Known Limitations
- The `UNSUPPORTED` queries explicitly bypass the LLM to prevent general-purpose chatting. If a user asks a highly complex graph query that simply lacks a regex trigger, it will trigger the fallback rather than passing the raw prompt to the LLM. True conversational parsing will eventually require an LLM-based intent classifier.
