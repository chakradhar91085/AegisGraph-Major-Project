# Phase 10C: Context Quality Inspection and Plan

## 1. Current Context Flow
The current Graph-RAG pipeline flows as follows:
1. **User Query** is received by `GraphRAGService`.
2. **Security Observation** triggers `AdaptivePolicy` risk evaluation.
3. **RetrievalService** resolves entities and executes the parameterized Cypher strategy, returning a `RetrievalResponse` which contains both the `results` and the `resolved_entities` metadata.
4. **ContextBuilder** takes the `RetrievalResponse`, extracts the `results` list up to the `effective_limit`, and passes only this list to strategy-specific formatting methods (e.g., `_format_frequent_communication`).
5. **GraphRAGService** wraps the generated string in `<CONTEXT>` tags and sends it to Ollama.

## 2. Current Format and Limitations
The primary limitation is that **ContextBuilder strips away the `resolved_entities` metadata** when delegating to its helper methods.

For example, when formatting `frequent_communication`:
```python
def _format_frequent_communication(self, results: List[Dict[str, Any]]) -> List[str]:
    parts = ["OBSERVED FREQUENT COMMUNICATION"]
    for row in results:
        parts.append(f"- {row.get('name', '')}: {row.get('weight', '')} observed email interactions")
    return ["\n".join(parts)]
```
Because the LLM only sees a list of names and weights under "OBSERVED FREQUENT COMMUNICATION" (without knowing who the source employee is), it frequently responds with: *"I do not have enough information."* The 7B model struggles to implicitly bind the user's query subject to the orphaned list.

## 3. Proposed Structured Context Strategy (Source-Grounded & Intent-Aware)
The solution is to **anchor the context** using the rich metadata already retrieved securely. We will pass the full `RetrievalResponse` to the helper methods, allowing the `ContextBuilder` to preface the raw records with the known subject of the query.

### Conceptual Template Design:

**Network-Centric Intents (e.g., `frequent_communication`, `topical_footprint`)**
```markdown
SUBJECT: [Resolved Entity Name] ([Resolved Entity Type])
INTENT: [Retrieval Intent]

DATA:
- [Target Name] ([Weight/Count] interactions)
- ...
```

**Path-Centric Intents (e.g., `person_connection`)**
```markdown
SUBJECT 1: [Resolved Entity 1]
SUBJECT 2: [Resolved Entity 2]
INTENT: [Retrieval Intent]

CONNECTION PATH:
- [Path Nodes] (Interactions: [Weights])
```

## 4. Security Guarantees
- **No Additional Queries:** The ContextBuilder will only utilize `resolved_entities` and `results` that were already securely fetched by the `RetrievalService`.
- **Policy Enforcement Maintained:** The `effective_limit` passed by the Adaptive Policy will continue to truncate the list of records before formatting.
- **Separation of Concerns:** The LLM is strictly fed the structured `<CONTEXT>` block as unprivileged data, while the Security layer remains the absolute authority over access.

## 5. Exact Files to Modify
- `backend/app/rag/context_builder.py`

## 6. Implementation Plan
1. **Refactor `ContextBuilder.build_context`**
   - Modify the signature of the internal format methods to accept `response: RetrievalResponse` and the truncated `results_to_process: List[Dict]`.
2. **Update Format Helpers**
   - Enhance `_format_frequent_communication`, `_format_topical_footprint`, `_format_organization_info`, and `_format_person_connection` to safely extract `response.resolved_entities` and prepend `SUBJECT:` metadata to the output string.
   - Improve the visual hierarchy of the generic and email templates.
3. **Execution**
   - Restart the FastAPI backend.
   - Run `verify_api_endpoints.py` to validate that the LLM now accurately synthesizes answers for the failing queries.

## 7. Test Strategy
- Re-run `python tests/verify_api_endpoints.py`.
- Validate that the LLM response to *"Who does veronica.espinoza@enron.com communicate with most frequently?"* successfully lists her top contacts based on the newly anchored context.
- Ensure no regressions occur in the standard backend regression suite.
