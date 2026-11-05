# AegisGraph — product

**What it is:** a question-answering system over the Enron email archive (Neo4j graph + LLM agent) that scores *how* each person asks. Normal questions get full answers; probing gets names blacked out (MASK); harvesting gets blocked (BLOCK). Five behavioural signals feed one risk score per user, remembered between sessions.

**Users:** (1) an analyst chatting with the graph; (2) an Auditor (admin) watching all users' risk, reading the audit log; (3) a faculty panel at a college demo, on a projector.

**Surfaces:** landing (Persuade), chat workspace with Graph and My-risk panels (Operate), admin Overview / Users / Audit log / Settings (Operate).

**Product truth to keep:** risk bands 0.35 / 0.65; modes ALLOW / MASK / RESTRICT / BLOCK; masked values arrive as [REDACTED_*] tokens; role comes from the server, never the UI.

**Brief for v2:** stylish, animated, dynamic. The interface itself reacts to risk (accent shifts calm -> amber -> red as the user's mode escalates). v1 (light "case file") is kept in frontend/ for comparison.

*Written by the assistant from known project facts; the init interview was not run.*
