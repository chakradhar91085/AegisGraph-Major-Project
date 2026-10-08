# Phase 9A — Product Experience and UI/UX Architecture Planning

## 1. Current Frontend Assessment
The current AegisGraph frontend successfully demonstrates the core mechanics of the security framework. 

**Strengths:**
- **Decoupled Architecture:** The frontend is strictly a passive visualization layer. It accurately maps the `TelemetryEvent` JSON payload to the UI without executing any risk or policy logic locally.
- **Visual Clarity:** The separation between the `ChatPanel` and `SecurityPanel` makes the dual nature of the application (conversation vs. security monitoring) explicit.
- **Reliability:** Session continuity and API integration (`POST /api/v1/chat`) are robust and heavily typed via TypeScript.

**Weaknesses (Areas for Productization):**
- **No Onboarding/Introduction:** The user is immediately dropped into the dashboard. There is no landing page to explain what AegisGraph is, why Graph-RAG security is necessary, or how the architecture works.
- **Utilitarian Layout:** The 50/50 split is functional but feels like a prototype. Modern professional platforms typically utilize a centered conversational workspace with contextual sidebars.
- **Chat Polish:** The chat lacks subtle metadata (e.g., records retrieved, LLM loading states, quick-start suggestions) that elevate an application from a prototype to a polished product.

## 2. Design Goals
The objective is to elevate AegisGraph into a professional, research-oriented AI security platform suitable for a major engineering project demonstration.
- **Professionalism over Flash:** The visual identity should be technical, secure, and modern (avoiding excessive animations or generic AI buzzwords).
- **Preserve Logic:** Absolutely no backend security logic, formulas, or policy thresholds will be moved to the frontend.
- **Focused Conversational UI:** The chat should remain the primary user focus, with security telemetry acting as an ever-present but non-obtrusive secondary layer.

## 3. Proposed Information Architecture & Navigation

We will introduce a routing layer to manage two distinct experiences.

**Route 1: `/` (Landing Page)**
- **Hero Section:** "Secure your Graph-RAG intelligence."
- **Primary CTA:** "Launch AegisGraph"
- **Value Proposition:** Explanation of behavioral threat detection and adaptive response control.
- **Architecture Flowchart (Visual):** `Query -> Behavioral Analysis -> Risk Engine -> Adaptive Policy -> Secure Retrieval -> Local LLM`.

**Route 2: `/app` (AegisGraph Dashboard)**
- **Top Navigation:** Branding, subtle versioning, and a global "New Session" control.
- **Center Workspace (Main):** The Chat Interface. Includes quick-start query suggestions on empty state.
- **Right Sidebar (Contextual):** The Security Panel. Condensed and styled as a professional telemetry dashboard (maintaining the Risk Timeline, EWMA, and Behavioral Signals).

## 4. Proposed Component Architecture

To support the new architecture, the following component structure is proposed:

```text
src/
├── pages/
│   ├── LandingPage.tsx       # New: Marketing/Architecture explanation
│   └── Dashboard.tsx         # New: Main layout wrapper for the app
├── components/
│   ├── chat/
│   │   ├── ChatPanel.tsx     # Refactored: Main chat container
│   │   ├── ChatMessage.tsx   # New: Extracted for cleaner rendering + metadata
│   │   └── EmptyState.tsx    # New: Contains suggested starting queries
│   ├── security/
│   │   ├── SecurityPanel.tsx # Refactored: Right sidebar layout
│   │   ├── RiskTimeline.tsx  # Existing: Preserved charting
│   │   └── SignalBars.tsx    # New: Extracted for cleaner component tree
│   └── layout/
│       └── Header.tsx        # New: Top navigation bar
```

### Chat Experience Refinements
- **Loading States:** Improve the `Loader2` state to distinguish between "AegisGraph is analyzing risk..." and "Ollama is generating response...".
- **Metadata Badges:** Append small, subtle badges to the agent's response indicating context limits applied and records retrieved, without cluttering the text.
- **Blocked Experience:** Retain the prominent red `ShieldBan` intervention UI. Ensure it visually overrides standard application errors to reinforce that it is a deliberate security action.

## 5. Planned Implementation Phases

- **Phase 9B: Landing Page & Routing Integration**
  - Install `react-router-dom`.
  - Build the professional Landing Page component.
  - Establish the `/` to `/app` routing flow.
- **Phase 9C: Dashboard Layout Redesign**
  - Refactor `App.tsx` into `Dashboard.tsx`.
  - Implement the Top Header + Center Chat + Right Sidebar layout grid.
  - Refine the `SecurityPanel` styling to fit the new sidebar dimensions.
- **Phase 9D: Interactive Chat and Response Polish**
  - Extract `ChatMessage.tsx`.
  - Add query suggestions to the empty state.
  - Inject subtle retrieval metadata into the chat bubbles.
- **Phase 9E: Visual QA and Final Integration**
  - Verify all responsive behaviors.
  - Ensure dark/technical aesthetic is consistent.

## 6. Explicit Constraints
- **No backend changes:** API contracts (`ChatRequest`, `ChatResponse`, `TelemetryEvent`) will remain exactly as they are.
- **Passive visualization:** The frontend will continue to rely solely on the `blocked_by_policy` flag and provided risk scalars from the backend.
