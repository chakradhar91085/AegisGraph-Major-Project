# AegisGraph

**AegisGraph** is a research prototype of a behavioral security layer for Graph-RAG (graph-based Retrieval-Augmented Generation): users ask questions about a company email archive (the Enron corpus) in plain English, and AegisGraph scores each user's behavior to decide how much data they may see.

Traditional RAG systems let users query the underlying data freely, which makes them open to data exfiltration, probing and reconnaissance. AegisGraph monitors semantic focus, temporal frequency, entity focus, graph footprint and sensitivity exposure to calculate a compounding **EWMA Risk Score**. As risk increases, an **Adaptive Policy Engine** limits how many records a user can reach, masks names and addresses, and ultimately blocks the user before data is leaked.

## High-Level Architecture
- **Frontend**: React, Vite, TypeScript, Tailwind CSS, Recharts — a user chat (`/app`) and an admin dashboard (`/admin`)
- **Backend**: FastAPI, Pydantic (orchestrator and security engine)
- **Sign-in**: Clerk
- **Graph database**: Neo4j
- **PostgreSQL**: audit trail
- **Retrieval agent**: an NVIDIA-hosted model writes read-only Cypher through the Neo4j MCP server
- **Answer model**: Ollama running `llama3.1:8b`, fully local
- **Embeddings**: SentenceTransformers (`all-MiniLM-L6-v2`) for the behavioral signals
- **Security evaluation**: from `backend/`, run `venv/Scripts/python.exe scripts/evaluate.py`. It scores the gate on 80 harmless questions, 33 development attacks and 51 frozen held-out attacks (`tests/fixtures`), then replays scripted sessions. Never edit the held-out set to raise its score.
- **Admin alerts**: Telegram and/or email

See [`backend/docs/AegisGraph_Technical_Architecture.md`](backend/docs/AegisGraph_Technical_Architecture.md) for the full architecture.

## Getting Started

### Prerequisites
- **Python 3.10+** and **Node.js 18+**
- **Neo4j** running on `bolt://localhost:7687` with the Enron graph loaded
- **PostgreSQL** with an empty database (e.g. `aegisgraph`); the audit tables are created automatically
- **Ollama** running on `http://localhost:11434` with the model: `ollama pull llama3.1:8b`
- **An NVIDIA API key** from [build.nvidia.com](https://build.nvidia.com) (internet access is needed to answer data questions)
- **A Clerk application** (free tier is fine) for sign-in

### Backend
```bash
cd backend
python -m venv venv
venv\Scripts\activate   # Or `source venv/bin/activate` on Unix
pip install -r requirements.txt
```
Copy `.env.example` to `.env` and fill it in. `DATABASE_URL`, `SECURITY_SESSION_SECRET` and the `NEO4J_*` credentials are required; also set `AGENT_API_KEY` and `CLERK_ISSUER`.

Start the server (bound to localhost; the API is sensitive, so don't expose it with `--host 0.0.0.0`):
```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

**Who can do what.** Every endpoint requires a signed-in Clerk user. The role is never taken from the request; it comes from `SECURITY_USER_ROLES` in `.env` (`clerk_user_id:Role`, e.g. `user_2abc:Auditor`). Signed-in users not listed are `Standard`. `Auditor` is also the admin role: only it can read the audit logs. Risk is remembered per user and decays with idle time, so starting a new session does not reset it. For local demos, `DEMO_ALLOW_RISK_RESET=true` makes the "New Session" button reset an Auditor's own risk.

### Frontend
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173`. Signed-in users chat at `/app`; Auditors also get the admin dashboard at `/admin`.

### Tests
```bash
cd backend
python -m pytest tests
```
Point `DATABASE_URL` at a scratch database first, so test runs stay out of the real audit trail.

### Optional settings (`backend/.env`)
- **Admin alerts**: fill in `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`, and/or `SMTP_USER`, `SMTP_PASSWORD` (a Gmail App Password) and `ALERT_EMAIL_TO`, and/or `SLACK_WEBHOOK_URL` (a Slack incoming webhook; BLOCK alerts ping `@channel`). Use "Send test alert" on the admin Settings page to check them.
- **Emails in the audit log**: in the Clerk dashboard, add `{"email": "{{user.primary_email_address}}"}` under Sessions → Customize session token.
