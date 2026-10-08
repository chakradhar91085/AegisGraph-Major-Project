# Phase 2 — Controlled Retrieval Layer

## 1. Retrieval Architecture

The retrieval layer provides a single, controlled chokepoint through which all graph queries flow. The pipeline is:

```
User Query → Intent Classification → Entity Resolution → Strategy Execution → Structured Results
```

All components are implemented in `app/retrieval/`:

| File | Responsibility |
|:---|:---|
| `schemas.py` | Pydantic data models for requests, responses, intents, and entity resolution |
| `intent_classifier.py` | Rule-based intent classification |
| `entity_resolver.py` | Deterministic entity resolution against the graph |
| `strategies.py` | Parameterized Cypher query execution |
| `service.py` | Orchestrator that ties the pipeline together |

## 2. RetrievalRequest and RetrievalResponse

### RetrievalRequest

```python
class RetrievalRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    limit: int = Field(default=10, ge=1, le=50)
    max_depth: int = Field(..., ge=0)  # No default — must be explicitly supplied
```

`max_depth` has no default value. This was a deliberate Phase 4C.2 correction to prevent any caller from bypassing the policy-controlled depth limit through silent defaults.

### RetrievalResponse

```python
class RetrievalResponse(BaseModel):
    query: str
    intent: str
    resolved_entities: List[ResolvedEntity] = []
    results: List[Dict[str, Any]] = []
    result_count: int = 0
    strategy: str
    metadata: Dict[str, Any] = {}
```

## 3. Supported Intents

| Intent | Example Query |
|:---|:---|
| `employee_lookup` | "Who is Christopher Calger?" |
| `sent_emails` | "What emails did Christopher Calger send?" |
| `received_emails` | "Emails received by Bob" |
| `email_chunks` | "Chunks of email enron_abc123" |
| `chunk_entities` | "Entities mentioned in chunk chk_enron_abc_0" |
| `entity_relationships` | "Entities related to Enron" |
| `unsupported_intent` | "What is the weather today?" |

## 4. Intent Routing

Intent classification is implemented as a deterministic, rule-based classifier in `intent_classifier.py`. Rules are ordered regex patterns evaluated top-to-bottom; the first match wins.

This design was chosen because:
- It is fully deterministic and testable
- It avoids LLM latency for classification
- It is replaceable with an LLM-based classifier in a future phase

An email-address fallback pattern defaults to `employee_lookup` if an `@` sign is detected.

## 5. Retrieval Strategies

All Cypher queries are defined in `strategies.py` as parameterized templates. There are six strategies:

| Strategy | Cypher Pattern | Parameters |
|:---|:---|:---|
| `lookup_employee_by_email` | `MATCH (e:Employee {email: $email})` | `$email` |
| `lookup_employee_by_name` | `MATCH (e:Employee) WHERE toLower(e.name) CONTAINS toLower($name)` | `$name`, `$limit` |
| `get_sent_emails` | `MATCH (e:Employee {employee_id: $employee_id})-[:SENT]->(m:Email)` | `$employee_id`, `$limit` |
| `get_received_emails` | `MATCH (e:Employee {employee_id: $employee_id})<-[:RECEIVED_BY]-(m:Email)` | `$employee_id`, `$limit` |
| `get_email_chunks` | `MATCH (m:Email {email_id: $email_id})-[:CONTAINS]->(c:Chunk)` | `$email_id`, `$limit` |
| `get_chunk_entities` | `MATCH (c:Chunk {chunk_id: $chunk_id})-[r:MENTIONS]->(ent:Entity)` | `$chunk_id`, `$limit` |
| `get_entity_relationships` | `MATCH (e1:Entity {entity_id: $entity_id})-[r:RELATED_TO]-(e2:Entity)` | `$entity_id`, `$limit` |

## 6. Parameterized Cypher

Every Cypher query uses Neo4j query parameters (`$param`). No string interpolation or concatenation is used. This prevents Cypher injection attacks at the database driver level.

## 7. Arbitrary Cypher Prevention

The system does not expose any raw Cypher endpoint. Queries that do not match a known intent are classified as `unsupported_intent` and return zero results without executing any graph query.

## 8. Hard Result Limits

A hard ceiling of 50 records is enforced in `strategies.py`:

```python
MAX_LIMIT = 50

def _cap_limit(self, limit: int) -> int:
    return min(max(limit, 1), MAX_LIMIT)
```

Every strategy call passes the limit through `_cap_limit()` before including it in the Cypher `LIMIT` clause.

## 9. Graph-Depth Interpretation

The prototype maps intents to abstract depth levels via `INTENT_DEPTH_MAP` in `service.py`:

```python
INTENT_DEPTH_MAP = {
    EMPLOYEE_LOOKUP: 0,      # non-expansive base lookup
    SENT_EMAILS: 2,
    RECEIVED_EMAILS: 2,
    EMAIL_CHUNKS: 3,
    CHUNK_ENTITIES: 4,
    ENTITY_RELATIONSHIPS: 5,
    UNSUPPORTED: 0
}
```

**Important**: This is an intent-to-depth abstraction, NOT a measurement of physical Neo4j traversal depth. For example, `sent_emails` always uses a 1-hop Cypher traversal (`Employee→Email`), but is assigned depth 2 because it represents the second conceptual layer of information exposure in the AegisGraph hierarchy.

When `required_depth > request.max_depth`, the retrieval service returns `blocked_by_policy` with zero results.

## 10. Error Handling

- Neo4j connection failures propagate as exceptions caught by the RAG service
- Entity resolution returns explicit `not_found` or `ambiguous` statuses rather than silent failures
- All Neo4j `DateTime` objects are serialized via `isoformat()` for JSON safety

## 11. Tests Performed

The retrieval test suite (`tests/test_retrieval.py`) covers 35 test cases:
- Neo4j health check
- All six strategies (lookup, sent, received, chunks, entities, relationships)
- Entity resolution (by email, by name, not found, ambiguous)
- Intent classification (all intents including unsupported)
- Security tests: Cypher injection, hard limit enforcement, arbitrary Cypher rejection
- Policy enforcement: `max_depth` validation, `d_eff=0` blocking, non-expansive lookup exception
- Empty result handling
- End-to-end service integration

## 12. Security Rationale

The retrieval layer is designed as a security boundary:
1. **No user-supplied Cypher**: Users cannot execute arbitrary graph queries.
2. **Parameterized queries**: All Cypher uses driver-level parameterization.
3. **Result limits**: A hard ceiling prevents unbounded data extraction.
4. **Intent gating**: Only predefined, auditable query patterns are executed.
5. **Depth enforcement**: The adaptive policy can restrict which intents are permitted based on the current risk level.

## 13. Limitations

1. **Intent classification is regex-based**: Edge cases in natural language phrasing may cause misclassification.
2. **Entity resolution is heuristic**: Name matching uses `CONTAINS` which may return false positives for short names.
3. **No query rewriting**: The system does not attempt to reformulate ambiguous queries.
4. **Intent-to-depth is an abstraction**: The depth map represents conceptual information exposure, not physical Neo4j hop counts.
