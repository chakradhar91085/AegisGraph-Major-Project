# Phase 4A — Behavioral Telemetry

## 1. Overview

Phase 4A implements the behavioral telemetry subsystem that observes user query patterns and computes security signals. This is a passive observation layer — it does not block or modify queries.

## 2. Session History

Session state is managed by an in-memory `SessionStore` (`app/security/session.py`):

```python
class SessionState(BaseModel):
    session_id: str
    history: List[QueryRecord] = []
    last_smoothed_risk: float = 0.0
```

Each `QueryRecord` stores:
- `timestamp`: Unix timestamp of the query
- `query`: Raw query text
- `embedding`: L2-normalized embedding vector (384 dimensions)
- `entities`: List of extracted entity names

Sessions are isolated by `session_id`. History is pruned to a configurable temporal window (default: 60 seconds) via `cleanup_old_history()`, with one exception: the absolute last query is always retained to enable semantic drift computation even if it falls just outside the window.

## 3. Query Observation Flow

The telemetry operates in two stages within `AegisSecurityService` (`app/security/service.py`):

### Stage 1: Pre-Retrieval (`observe_query`)

1. Clean up old history entries outside the temporal window.
2. Fetch the current query's embedding via `sentence-transformers`.
3. Retrieve the previous query's embedding from session history.
4. Compute **semantic drift** between current and previous embeddings.
5. Calculate the **adaptive policy** based on the session's previous EWMA risk.
6. Return a context dict containing the embedding, drift value, and policy.

### Stage 2: Post-Retrieval (`calculate_risk`)

1. Extract entities from the retrieval response (strategy-specific heuristics).
2. Retrieve session history within the temporal window.
3. Compute **temporal frequency** from inter-arrival time.
4. Compute **entity focus** from the entity distribution across history.
5. Compute **graph footprint** from the retrieval intent and result count.
6. Fuse all four signals into instantaneous risk.
7. Apply EWMA smoothing.
8. Persist the new `QueryRecord` and updated EWMA to session state.
9. Return a `TelemetryEvent`.

## 4. Semantic Embeddings

Embeddings are provided by `EmbeddingProvider` (`app/security/embeddings.py`):

- **Model**: `all-MiniLM-L6-v2` (384-dimensional)
- **Loading**: Lazy-loaded on first use via `sentence-transformers`
- **Normalization**: L2-normalized so that dot product equals cosine similarity
- **Failure handling**: Returns `None` on any embedding failure; downstream signals default to 0.0

## 5. Semantic Drift (S_sem)

```
S_sem(t) = 1 - cos(E_t, E_{t-1})
```

Where `E_t` and `E_{t-1}` are L2-normalized embeddings, so cosine similarity is computed as the dot product.

- **Range**: [0.0, 1.0]
- **First query**: Returns 0.0 (no previous embedding)
- **Missing embedding**: Returns 0.0
- **Dimension mismatch**: Returns 0.0
- **Identical queries**: ≈ 0.0
- **Orthogonal queries**: ≈ 1.0

## 6. Temporal Frequency (S_temp)

```
S_temp(t) = exp(-α_temp × Δτ_t)
```

Where:
- `Δτ_t = τ_t - τ_{t-1}` (inter-arrival time in seconds between current and previous query)
- `α_temp = 0.1` (inverse seconds, configurable via `SECURITY_ALPHA_TEMP`)

- **Range**: [0.0, 1.0]
- **First query**: Returns 0.0 (no previous timestamp)
- **Simultaneous queries** (Δτ = 0): Returns 1.0 (maximum frequency)
- **1 second apart**: ≈ 0.905
- **5 seconds apart**: ≈ 0.607
- **60 seconds apart**: ≈ 0.002 (nearly zero)

This is the paper-aligned exponential decay model. The key property is that only the most recent inter-arrival time matters, not the count of queries in a window.

## 7. Entity Extraction and Tracking

Entity extraction is performed heuristically in `AegisSecurityService.calculate_risk()`:

| Strategy | Extraction Method |
|:---|:---|
| `employee_lookup` | Name from the first retrieval result |
| `sent_emails` / `received_emails` | The full query text as a proxy entity |
| `chunk_entities` | All `entity_name` values from retrieval results |
| `entity_relationships` | All `entity_name` values from retrieval results |

Entities are stored in each `QueryRecord` and used for entity focus computation across the temporal window.

## 8. Entity Focus (S_ent)

```
S_ent(t) = 1 - H(E_t) / log(|E_t| + ε)
```

Where:
- `H(E_t)` is the Shannon entropy of the entity frequency distribution across the temporal window
- `|E_t|` is the number of unique entities
- `ε = 10⁻⁹` prevents division by zero

- **Range**: [0.0, 1.0]
- **Insufficient history** (< 2 total entity mentions): Returns 0.0 (cold-start protection)
- **Single unique entity repeated**: Returns 1.0 (maximum concentration)
- **Uniformly distributed entities**: Approaches 0.0

The cold-start guard (`len(all_entities) < 2`) prevents a first-time query containing one entity from being flagged as entity-focused probing.

## 9. Graph Footprint (S_graph)

```
S_graph(t) = min(1, d_t / d_max + η × v_t / v_max)
```

Where:
- `d_t`: Intent-based depth from `depth_map` (see Phase 2)
- `d_max`: Maximum graph depth normalization (default: 5)
- `η`: Graph weight (default: 0.5)
- `v_t`: Result count from retrieval
- `v_max`: Maximum visited nodes normalization (default: 50)

- **Range**: [0.0, 1.0]
- **Zero results**: Returns 0.0 (zero-result safeguard)
- **Employee lookup** (depth 1, 1 result): ≈ 0.21
- **Deep traversal with many results**: Approaches 1.0

**Important**: The depth component uses the intent-to-depth mapping, not physical Neo4j traversal depth. This is an intentional prototype simplification.

## 10. Telemetry Lifecycle

```
New Session → observe_query (pre-retrieval)
    → Embedding + Semantic Drift + Policy
    → Retrieval
    → calculate_risk (post-retrieval)
    → Temporal + Entity + Graph signals
    → Risk Fusion → EWMA
    → Session Update (new record + smoothed risk)
    → TelemetryEvent returned
```

## 11. First-Query Behavior

For the very first query in a session:
- `S_sem = 0.0` (no previous embedding)
- `S_temp = 0.0` (no previous timestamp)
- `S_ent = 0.0` (insufficient entity history)
- `S_graph` = based on intent and result count
- EWMA starts from 0.0

This ensures that a single benign query does not trigger disproportionate risk.

## 12. Signal Edge Cases

| Edge Case | Signal | Behavior |
|:---|:---|:---|
| Embedding failure | S_sem | Returns 0.0 |
| Dimension mismatch | S_sem | Returns 0.0 |
| No previous query | S_temp | Returns 0.0 |
| Negative time delta | S_temp | Clamped to 0.0 |
| < 2 entity mentions | S_ent | Returns 0.0 |
| Zero retrieval results | S_graph | Returns 0.0 |
| Unknown intent | S_graph | Depth defaults to 0 |

## 13. Tests

The security test suite (`tests/test_security.py`) covers 33 test cases including:
- Semantic drift: identical, orthogonal, opposite queries; missing/failed embeddings
- Temporal frequency: first query, simultaneous, 1s/5s/60s intervals; count independence
- Entity focus: no entities, insufficient history, repeated entity, diverse entities
- Graph footprint: zero results, employee lookup, deep maxed traversal
- Risk fusion and EWMA stepping
- Session isolation
- Real embedding model integration tests
- Synthetic attack sequences (benign, entity-focused, rapid probing, graph expansion)
