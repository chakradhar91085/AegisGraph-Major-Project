# Development log (archived)

These are the phase-by-phase design and implementation notes written while AegisGraph was
being built (22–24 August 2026). They record how the system evolved and the reasoning
behind each step, which is why they are kept.

They describe the system **as it was at the time**, not as it is now. Several details have
since changed, among them the language model (Qwen 2.5 Coder 7B was replaced by Llama 3.1 8B),
the backend port (8000 became 8001), sign-in and roles, the split into user and admin
interfaces, admin alerts, fuzzy name matching and the PostgreSQL retrieval fail-safe.

For the current system, see [`../AegisGraph_Technical_Architecture.md`](../AegisGraph_Technical_Architecture.md).
