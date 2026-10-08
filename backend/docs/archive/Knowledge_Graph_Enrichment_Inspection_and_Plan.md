# Knowledge Graph Enrichment Inspection and Plan

## 1. Current Dataset Description
The active dataset is the AegisGraph Final 50K Neo4j Dataset, derived from the CMU Enron Email Corpus. It contains exactly 50,042 canonical emails spanning ~8,263 communicators. 
**Crucial Note:** The original raw `emails_cleaned.jsonl` (and the raw `maildir` corpus) are intentionally omitted from the repository. The sole source of truth for the currently deployed application is the set of CSV files in `data/neo4j/` and the ingestion pipeline defined in `data/neo4j/prepare_neo4j_dataset.py`.

## 2. Current Graph Schema
The existing Neo4j schema is a highly normalized, bipartite event graph:
- **Nodes:** `Employee`, `Email`, `Chunk`, `Entity`
- **Relationships:**
  - `(:Employee)-[:SENT]->(:Email)`
  - `(:Email)-[:RECEIVED_BY]->(:Employee)`
  - `(:Email)-[:CONTAINS]->(:Chunk)`
  - `(:Chunk)-[:MENTIONS]->(:Entity)`
  - `(:Entity)-[:RELATED_TO]->(:Entity)`

## 3. Current Preprocessing Limitations
The current `prepare_neo4j_dataset.py` pipeline acts as a strict structural parser:
- It connects `Employee` to `Email`, but never `Employee` directly to `Employee`. This forces all social queries (e.g., "Who does X talk to?") to traverse through individual email nodes, heavily inflating path length.
- It extracts domains (e.g., `enron.com`) but assigns them purely as string properties on `Employee` nodes, preventing graph-level queries against entire external organizations.
- Entities are linked to Chunks, but there is no direct representation of an Employee's topical footprint (e.g., which entities they discuss most).

## 4. Information Found in Raw Dataset (Currently Unused Graphically)
Based on inspection of `prepare_neo4j_dataset.py` and the CSVs:
1. **Email Domains:** Fully extracted and preserved as properties (`e.domain`).
2. **Implicit Communication Edges:** The exact paths of who emailed whom exist via `SENT` -> `Email` -> `RECEIVED_BY`.
3. **Implicit Topical Focus:** The exact paths of who talks about what exist via `SENT` -> `Email` -> `CONTAINS` -> `Chunk` -> `MENTIONS` -> `Entity`.

## 5. Information That Is Genuinely Unavailable
- Formal organizational hierarchies (Managers, Direct Reports).
- Explicit Departments or Business Units (e.g., "HR", "Trading Desk").
- Official Job Titles (e.g., "CEO", "Analyst").
As stated in `data/README.md`, synthetic organizational roles are strictly forbidden because they were not reliably available across the historical corpus. We cannot and will not invent these facts.

## 6. Proposed Enriched Graph Schema
We propose adding 1 new Node type and 3 new Relationship types:

- **New Node:** `(:Organization {name: String})`
- **New Relationship:** `(:Employee)-[:BELONGS_TO]->(:Organization)`
- **New Relationship:** `(:Employee)-[:COMMUNICATES_FREQUENTLY_WITH {weight: Int}]->(:Employee)`
- **New Relationship:** `(:Employee)-[:FREQUENTLY_MENTIONS {count: Int}]->(:Entity)`

## 7. Derivation Methods for Proposed Relationships
All proposed enrichments are **Type B (Deterministically derived from the dataset)**. No external data or hallucinated facts are required.

1. **`Organization` and `BELONGS_TO`:**
   - *Method:* `MATCH (e:Employee) MERGE (o:Organization {name: e.domain}) MERGE (e)-[:BELONGS_TO]->(o)`
2. **`COMMUNICATES_FREQUENTLY_WITH`:**
   - *Method:* `MATCH (p1:Employee)-[:SENT]->(:Email)-[:RECEIVED_BY]->(p2:Employee) WITH p1, p2, count(*) as weight WHERE weight >= 5 MERGE (p1)-[r:COMMUNICATES_FREQUENTLY_WITH]->(p2) SET r.weight = weight`
3. **`FREQUENTLY_MENTIONS`:**
   - *Method:* `MATCH (p:Employee)-[:SENT]->(:Email)-[:CONTAINS]->(:Chunk)-[:MENTIONS]->(ent:Entity) WITH p, ent, sum(1) as total_mentions WHERE total_mentions >= 3 MERGE (p)-[r:FREQUENTLY_MENTIONS]->(ent) SET r.count = total_mentions`

## 8. Recommended Enrichment Priorities
1. **`COMMUNICATES_FREQUENTLY_WITH` (Highest Priority):** Directly models the social network, which is the most common natural language query pattern.
2. **`FREQUENTLY_MENTIONS` (High Priority):** Directly models the behavioral profile/topical focus of an employee.
3. **`Organization` Nodes (Medium Priority):** Good for macro-level clustering but less critical for conversational retrieval than direct edges.

## 9. Expected Impact on Retrieval Capabilities
- **Massive Performance Boost:** Resolving "Who does Person A collaborate with?" drops from an $O(E \times R)$ traversal (through every email) to an $O(1)$ direct edge traversal.
- **Richer LLM Context:** The LLM can be provided with an employee's exact communication circle and topical footprint instantly, allowing for highly accurate, summarized answers without deep database scans.

## 10. Expected Impact on AegisGraph Security Evaluation
This enrichment will *significantly improve* the realism of the security demonstration.
- Currently, the `max_depth` parameter blocks traversal through emails. 
- With direct `COMMUNICATES_FREQUENTLY_WITH` edges, an attacker can theoretically "hop" across the social graph directly. 
- The Adaptive Policy Engine will need to explicitly govern access to these high-density edges. A High-Risk user ($d_{eff} = 0$) will be correctly blocked from seeing a person's social network, clearly demonstrating Graph-RAG access control on direct semantic relationships.

## 11. Risks, Limitations, and Safety
- **Data Explosion:** A threshold (e.g., `weight >= 5`) must be enforced for both `COMMUNICATES_FREQUENTLY_WITH` and `FREQUENTLY_MENTIONS` to prevent a massive quadratic explosion of edges in the graph.
- **Safety Guarantee:** We will perform the enrichment *purely via post-processing Cypher queries* in Neo4j. This ensures we do not need to modify the missing JSONL file, we do not overwrite the existing Neo4j CSVs, and the core dataset remains completely uncorrupted. If a mistake is made, the generated edges can simply be deleted. None of the Python security models or risk formulas require modification.
