# Phase 7B — Final Demonstration and Project Readiness

## 1. Purpose and Scope
This document serves as the definitive guide for evaluating, running, and demonstrating the AegisGraph prototype. Phase 7B focused entirely on solidifying the project's reproducibility and preparing curated workflows that highlight the core capabilities of the behavioral security layer, the adaptive policy engine, and the RAG orchestration pipeline. No new features were developed in this phase.

## 2. Reproducible Startup Procedure

To successfully boot the AegisGraph application for a demonstration, the following sequence must be followed:

### Prerequisites
1. **Neo4j Graph Database**: Running on `bolt://localhost:7687` with the Enron dataset loaded.
2. **Ollama**: Running locally on port `11434` with the required LLM model (e.g., `qwen3:8b`).
3. **Python 3.10+** (Backend)
4. **Node.js 18+** (Frontend)

### Backend Startup
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Activate the virtual environment (assuming it was previously configured):
   ```bash
   venv\Scripts\activate   # Windows
   source venv/bin/activate # Unix
   ```
3. Ensure `.env` is populated with correct Neo4j credentials matching `.env.example`.
4. Start the FastAPI server via Uvicorn:
   ```bash
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
   *Health Check*: Navigate to `http://localhost:8000/api/v1/health` in a browser. It should return status `ok`.

### Frontend Startup
1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install dependencies (if not already installed):
   ```bash
   npm install
   ```
3. Start the Vite development server:
   ```bash
   npm run dev
   ```
4. Access the demonstration dashboard at `http://localhost:5173`.

---

## 3. Curated Demonstration Scenarios

The following scenarios are guaranteed to reproduce the core features validated during Phase 7A. 

### Scenario A: The Benign Workflow
**Concept Demonstrated**: Normal, low-risk interactions permit the user to access standard data without restriction.

1. **Start**: Click **"New Session"** in the UI to ensure a fresh telemetry state.
2. **Query 1**: *"Who is Christopher Calger?"*
   - *Expected Behavior*: Permitted. Risk timeline initializes near ~0.01.
3. **Query 2**: *"What emails did he send?"*
   - *Expected Behavior*: Permitted. Risk timeline increases slightly but remains safely in the LOW tier. The system answers the query normally.

### Scenario B: The Suspicious Probing Workflow
**Concept Demonstrated**: Repeated or targeted reconnaissance triggers behavioral signals (Semantic Drift, Entity Focus), accelerating EWMA risk accumulation.

1. **Start**: Click **"New Session"** to reset the telemetry state.
2. **Query 1**: *"Who is Christopher Calger?"*
3. **Query 2**: *"What emails did he send?"*
4. **Query 3**: *"Show all chunks for enron_4f0c9a"*
   - *Expected Behavior*: Permitted, but you will observe visible spikes in the Semantic Drift ($S_{sem}$) and Temporal Frequency ($S_{temp}$) progress bars. The EWMA risk will climb aggressively toward the MEDIUM threshold.
5. **Query 4**: *"Find entities related to christopher.calger@enron.com"*
   - *Expected Behavior*: The query intent is deeply graph-expanding. Because the compounded EWMA risk is now elevated, the Adaptive Policy reduces the effective permitted graph depth ($d_{eff}$) below the depth required by this intent. 
   - **Observable Outcome**: The query is **BLOCKED**. The frontend will instantly display a red "REQUEST BLOCKED BY SECURITY POLICY" alert box. The underlying Neo4j retrieval is never executed.

---

## 4. Final Project Readiness Checklist

Prior to any faculty review or formal presentation, run through this checklist:

- [ ] **Neo4j Active**: Verify Neo4j desktop/server is running and the database is active.
- [ ] **Ollama Active**: Verify `ollama run <model>` is running in a separate terminal.
- [ ] **Backend Healthy**: `http://localhost:8000/api/v1/health` returns HTTP 200.
- [ ] **Frontend Active**: `http://localhost:5173` loads without console errors.
- [ ] **Session Continuity**: Verify that sending two consecutive queries updates the Risk Timeline continuously without dropping the `session_id`.
- [ ] **Signal Rendering**: Verify the Security Dashboard progress bars animate when a query completes.
- [ ] **Demonstration Execution**: Mentally review Scenario B to ensure the sequence is memorized.

## 5. Important Disclaimer
AegisGraph is a prototype. The thresholds (e.g., exactly when blocking occurs) are mathematically continuous based on the sigmoid functions evaluated in `PolicyEngine`. Therefore, variations in model embedding precision or specific phrasing may slightly alter exactly *which* query number triggers the block. The curated scenarios above represent the most stable, validated paths for demonstration.
