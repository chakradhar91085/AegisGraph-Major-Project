# Phase 11C: Interactive Graph Visualization

## 1. Components and Hooks Created
- **`useGraphState` Hook (`frontend/src/hooks/useGraphState.ts`)**: Manages the accumulation of session graph exploration. It merges new nodes/edges from `ChatResponse` into the existing graph state and tags newly discovered items with an `isNew` boolean flag.
- **`GraphVisualization` Component (`frontend/src/components/GraphVisualization.tsx`)**: The UI component that wraps `react-force-graph-2d`. It accepts the `GraphState` from the hook and renders the physics-driven network.
- **`DashboardPage` Updates (`frontend/src/pages/DashboardPage.tsx`)**: Reorganized the right column layout to split it evenly between the Graph Visualization and the Security Panel, ensuring the chat-first experience remains dominant on the left.

## 2. Data Flow
1. User submits a query in `ChatPanel`.
2. `useChat` fires the API request and receives a `ChatResponse`, which now contains `graph_data`.
3. `DashboardPage` uses a `useEffect` on `messages` to detect when a new `agent` message arrives.
4. It calls `addGraphData(lastMsg.graph_data)`, which diffs the new graph topology against the previously explored topology.
5. The `GraphVisualization` component automatically receives the updated `graphState` and renders it.

## 3. Session Accumulation Behavior
The graph is designed to conceptually grow as the user queries different but connected items:
- Nodes and edges returned from previous queries persist during the session.
- Duplicate nodes or edges from subsequent queries update their visual state to appear "new" again, preventing duplicates while accurately highlighting the current area of focus.

## 4. Visual Exploration States
- **Newly Explored (Current Query):** Colored **Blue** (`#3b82f6`). The visual indicator explicitly maps to what the backend just permitted for this exact query.
- **Previously Explored (Past Queries):** Colored **Slate/Gray** (`#94a3b8`). These are nodes discovered earlier in the session.
- **Empty State:** A clean fallback message is shown instructing the user to ask about connections or organizations if the graph is currently empty.

## 5. Security Behaviors Maintained
### Blocked Queries
When a query is blocked or restricted by the Adaptive Policy, the `graph_data` array is empty or reduced. 
- The `useGraphState` hook safely detects an empty payload and simply transitions all existing nodes to `isNew: false`. 
- No protected nodes are rendered, and the visualization accurately reflects the block by not expanding.

### New Session Behavior
Clicking the **"New Session"** button in the dashboard triggers `clearGraphState()` alongside `clearSession()`, completely wiping the accumulated visualization history.

## 6. Testing Results
- `npm run build` completed successfully with zero TypeScript errors.
- Component props strictly enforce the decoupled `GraphVisualizationPayload` schema to ensure no raw backend attributes are inadvertently exposed to the DOM.

## 7. Known Limitations
- The force-directed graph physics require a moment to "settle" when a large cluster of nodes is introduced. We implemented a delayed `zoomToFit` to handle this gracefully.
- The `person_connection` path logic uses string names instead of IDs. This requires the backend to guarantee uniqueness, or names may visually merge.
- Since this is an MVP, session exploration is strictly in-memory (React State). Reloading the browser clears the visualization, which is intentional for privacy.
