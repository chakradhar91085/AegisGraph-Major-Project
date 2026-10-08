# Phase 11A: Graph Visualization Architecture

## 1. Current Data Flow Inspection

### Findings
Currently, the pipeline flows as follows:
1. `RetrievalService` queries Neo4j and returns a `RetrievalResponse` object containing the raw Neo4j records in `results` and entity metadata in `resolved_entities`.
2. `GraphRAGService` passes this object to `ContextBuilder`, which generates a secure, structured text string for Ollama.
3. The raw `results` are then **discarded**. The final `ChatResponse` API schema (`backend/app/api/chat.py`) only includes:
   - `answer` (LLM text)
   - `intent`
   - `retrieval` (metadata containing only `result_count` and `strategy`)
   - `telemetry` (risk scoring and policy data)

### Conclusion
Currently, **no actual graph nodes or relationships are exposed to the frontend**. This inherently guarantees security but prevents visualization. To visualize the subgraph safely, we must parse the `RetrievalResponse.results` into a generic graph format and send it within the `ChatResponse`.

---

## 2. Safe Graph Data Contract

We will introduce a minimal, bounded payload in the backend to explicitly decouple the visualization from raw database records. This prevents accidental exposure of internal IDs or restricted attributes.

### Proposed Schema
```python
class GraphNode(BaseModel):
    id: str           # Hashed or public ID (e.g., email address)
    label: str        # Display name (e.g., "Veronica Espinoza")
    type: str         # "Employee", "Organization", "Entity"

class GraphEdge(BaseModel):
    source: str       # Node ID
    target: str       # Node ID
    type: str         # e.g., "COMMUNICATES_FREQUENTLY_WITH"
    weight: Optional[float] = None

class GraphVisualizationPayload(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
```
This payload will be appended to the `ChatResponse` as an optional `graph_data` field. A new backend component (e.g., `GraphDataExtractor`) will be responsible for translating strategy-specific `results` into this uniform structure.

---

## 3. Session Exploration Model

### Backend Responsibility
The backend will remain completely stateless regarding visualization. It will **only** return the specific subgraph (nodes and edges) retrieved for the *current single query*.

### Frontend Responsibility
The frontend React application will manage the persistent "Session Exploration" state.
- We will create a `useGraphState` hook.
- When a `ChatResponse` arrives, it merges the new `graph_data.nodes` and `graph_data.edges` into the existing visualization state.
- **Exploration Highlighting:** The frontend can compare incoming nodes against its existing state. Newly discovered nodes can be temporarily highlighted or animated to visually represent the user "exploring" new areas of the graph.

---

## 4. Security + Visualization Integration

This architecture strictly preserves the AegisGraph security boundary:
- **No Direct Queries:** The frontend never queries Neo4j. It only visualizes what the backend's `AdaptivePolicy` has permitted to be returned.
- **Blocked Queries:** If the `AdaptivePolicy` blocks a query (e.g., returning 0 results), `graph_data` will simply be empty. The graph visualization will naturally halt its expansion, visually demonstrating the security policy in action.
- **Telemetry Integration:** The frontend can use the existing `telemetry.policy.risk_level` to style the graph (e.g., changing the background or edge colors to warn the user if the risk transitions to MEDIUM or HIGH).

---

## 5. Graph Library Recommendation

**Recommended Library:** `react-force-graph-2d` (Force Graph)
- **Rationale:** AegisGraph deals heavily with communication networks (who emails whom). Force-directed graphs utilize D3 physics to naturally cluster connected nodes, making social structures immediately obvious.
- **Suitability:** It is highly performant with HTML5 Canvas, seamlessly supports React and TypeScript, handles dynamic nodes (perfect for session exploration accumulation), and allows easy styling for highlighted/new nodes.

*(Alternative considered: `React Flow` — Excellent, but better suited for rigid hierarchical diagrams rather than organic communication networks).*

---

## 6. Implementation Roadmap

### Phase 11B: Secure Backend Data Extraction
- Create `GraphDataExtractor` in `backend/app/retrieval/graph_extractor.py`.
- Update `ChatResponse` schema to include `graph_data`.
- Wire `GraphRAGService` to populate `graph_data` based strictly on the permitted `RetrievalResponse`.
- Add backend unit tests.

### Phase 11C: Frontend Visualization Implementation
- Install `react-force-graph-2d`.
- Implement `useGraphState` to accumulate nodes and edges during the session.
- Create a `GraphVisualization` React component to render the data payload.

### Phase 11D: Security Visualization Polish (Optional)
- Add visual indicators linking the graph UI to the Adaptive Policy telemetry (e.g., pulsing nodes on new discovery, risk-level styling).
