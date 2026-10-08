# AegisGraph

**AegisGraph** is a research prototype of a behavioral security layer for Graph-RAG (graph-based Retrieval-Augmented Generation): users ask questions about a company email archive (the Enron corpus) in plain English, and AegisGraph scores each user's behavior to decide how much data they may see.

The core problem AegisGraph solves is the security vulnerability of standard RAG pipelines. Traditional RAG systems allow users to blindly query the underlying database via semantic search, making them highly susceptible to data exfiltration, probing, and unauthorized reconnaissance. AegisGraph introduces a continuous behavioral security layer that monitors semantic drift, temporal frequency, entity focus, and graph footprint to calculate a compounding **EWMA Risk Score**. As risk increases, an **Adaptive Policy Engine** dynamically limits the model's access to the graph (restricting context limits and graph depth) and can ultimately block malicious exploration before data is leaked.

## High-Level Architecture
- **Frontend**: React, Vite, TypeScript, Tailwind CSS, Recharts — a user chat (`/app`) and an admin dashboard (`/admin`)
- **Backend**: FastAPI, Pydantic (Orchestrator & Security Engine)
- **Sign-in**: Clerk
- **Graph Database**: Neo4j (primary data store)
- **PostgreSQL**: audit trail, plus an optional retrieval fail-safe copy of part of the dataset
- **Embeddings**: SentenceTransformers (`all-MiniLM-L6-v2`) for the behavioral signals
- **Language Model**: Ollama running `llama3.1:8b`, fully local
- **Admin alerts**: Telegram and/or email

See [`backend/docs/AegisGraph_Technical_Architecture.md`](backend/docs/AegisGraph_Technical_Architecture.md) for the full architecture.

## Getting Started

### Prerequisites
- **Python 3.10+**
- **Node.js 18+**
- **Neo4j Desktop / Server** running with the Enron dataset ingested.
- **PostgreSQL** running locally with an empty database (e.g. `aegisgraph`); it stores the audit trail. The tables are created automatically.
- **Ollama** installed and running locally with the target model: `ollama pull llama3.1:8b` (set via `OLLAMA_MODEL` in `.env`).
- **A Clerk application** (free tier is fine) for sign-in. The frontend uses its publishable key; the backend verifies its tokens.

### 1. Database & LLM Preparation
1. Ensure your Neo4j database is active on `bolt://localhost:7687`.
2. Ensure Ollama is running on `http://localhost:11434`.

### 2. Backend Setup
Navigate to the `backend` directory:
```bash
cd backend
python -m venv venv
venv\Scripts\activate   # Or `source venv/bin/activate` on Unix
pip install -r requirements.txt
```
Copy `.env.example` to `.env` and fill it in. These have no defaults and the server will not start without them: `DATABASE_URL`, `SECURITY_SESSION_SECRET` (generate with `python -c "import secrets; print(secrets.token_hex(32))"`), and the `NEO4J_*` credentials. Also set `CLERK_ISSUER` to your Clerk Frontend API URL.

Start the backend server (bound to localhost; the API is sensitive, so don't expose it with `--host 0.0.0.0`):
```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```
The API will be available at `http://localhost:8001/api/v1` (the frontend expects this port).

**Who can do what.** Every endpoint except `/health*` requires a signed-in Clerk user. The role is never taken from the request; it comes from `SECURITY_USER_ROLES` in `.env` (`clerk_user_id:Role`, e.g. `user_2abc:Auditor`). Signed-in users not listed are `Standard`. Sign in once and copy your user id from the "Current Role" box in the workspace, then add it to `SECURITY_USER_ROLES` and restart. `Auditor` is also the admin role: only it can read the audit logs. Risk is remembered per user (and decays with idle time), so starting a new session does not reset it. For local demos, `DEMO_ALLOW_RISK_RESET=true` makes the "New Session" button reset your risk.

### 3. Frontend Setup
Navigate to the `frontend` directory:
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173`. Signed-in users chat at `/app`; Auditors also get the admin dashboard at `/admin`.

### Optional settings (`backend/.env`)
- **Admin alerts**: fill in `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`, and/or `SMTP_USER`, `SMTP_PASSWORD` (a Gmail App Password) and `ALERT_EMAIL_TO`. Use "Send test alert" on the admin Overview page to check them.
- **PostgreSQL fail-safe**: load the subset with `python scripts/ingest_enron_postgres.py`, then set `USE_POSTGRES_RETRIEVAL=true` to answer from PostgreSQL instead of Neo4j.
- **Emails in the audit log**: in the Clerk dashboard, add `{"email": "{{user.primary_email_address}}"}` under Sessions → Customize session token.

## Documentation
- [`backend/docs/AegisGraph_Technical_Architecture.md`](backend/docs/AegisGraph_Technical_Architecture.md) describes the current system.
- [`backend/docs/archive/`](backend/docs/archive/README.md) holds the phase-by-phase development notes from August 2026. They record how the system was built but describe it as it was then.
- Evaluation charts are in `backend/docs/figures/`.
