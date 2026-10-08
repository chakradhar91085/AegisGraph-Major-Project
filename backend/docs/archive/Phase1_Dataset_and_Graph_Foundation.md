# Phase 1 — Dataset and Graph Foundation

## 1. Project Objective

AegisGraph is a research prototype implementing a behavioral security layer for Graph-RAG (Retrieval-Augmented Generation) systems. The objective of Phase 1 was to establish the foundational graph database from a real-world email corpus, providing a realistic knowledge graph for the Graph-RAG pipeline to query against.

## 2. Dataset Used

**CMU Enron Email Corpus** (May 7, 2015 release)

- **Raw volume**: 517,401 emails across 150 employee mailboxes
- **Final working dataset**: 50,042 canonical emails

### Why the Enron Dataset

1. **Public domain**: The Enron corpus is one of the few large-scale, real corporate email datasets publicly available for research.
2. **Rich relational structure**: Emails naturally form a multi-hop graph (employees → emails → text chunks → named entities → entity co-occurrences).
3. **Security research relevance**: The dataset represents a realistic corporate communication graph where information traversal depth is meaningful — exactly the scenario AegisGraph's behavioral security model targets.
4. **Reproducibility**: Being publicly available ensures the research is reproducible.

## 3. Data Preprocessing

The raw corpus was processed through a streaming pipeline:

1. **RFC-822 / MIME Parsing**: Extraction of envelope headers (`Date`, `From`, `To`, `Cc`, `Bcc`, `Subject`, `Message-ID`, `X-From`, `X-To`, `X-Folder`).
2. **Text Normalization & Body Cleaning**: Unicode normalization, removal of transmission artifacts, header-boundary splitting.
3. **Deterministic SHA-256 Deduplication**: Fingerprinting on `(sender, sorted(recipients), subject, normalized_body)`, reducing 517,401 raw files to 251,328 canonical unique emails.
4. **High-Density Graph Selection**: Extracted the final 50,042-email core combining:
   - Peak temporal crisis alignment (2000–2001)
   - 94.00% mailbox coverage
   - 90.08% internal communication
   - Zero graph fragmentation (100% single connected component)
   - 100% text completeness for Graph-RAG

The preprocessing pipeline script is preserved at `data/neo4j/prepare_neo4j_dataset.py`.

## 4. Neo4j Graph Schema

### Node Types

| Node Label | Count | Key Properties |
|:---|---:|:---|
| `(:Employee)` | 8,263 | `employee_id`, `email`, `name`, `mailbox`, `domain` |
| `(:Email)` | 50,042 | `email_id`, `message_id`, `timestamp`, `subject`, `content_hash`, `source_folder` |
| `(:Chunk)` | 82,384 | `chunk_id`, `email_id`, `chunk_index`, `text` |
| `(:Entity)` | 166,884 | `entity_id`, `name`, `entity_type` |

**Total nodes**: 307,573

### Relationship Types

| Relationship | Count | Description |
|:---|---:|:---|
| `(:Employee)-[:SENT]->(:Email)` | 50,042 | Who sent the email |
| `(:Email)-[:RECEIVED_BY]->(:Employee)` | 454,710 | To, CC, BCC recipients |
| `(:Email)-[:CONTAINS]->(:Chunk)` | 82,384 | Paragraph-bounded text chunks |
| `(:Chunk)-[:MENTIONS]->(:Entity)` | 1,036,087 | NER-extracted entities (with `count`) |
| `(:Entity)-[:RELATED_TO]->(:Entity)` | 7,569,625 | Entity co-occurrence (with `co_occurrence_count`) |

**Total relationships**: 9,192,848

### Graph Topology Diagram

```
Employee --[:SENT]--> Email --[:CONTAINS]--> Chunk --[:MENTIONS]--> Entity
                      |                                              |
                      +--[:RECEIVED_BY]--> Employee    [:RELATED_TO]-+
```

## 5. Ingestion Pipeline

Data was ingested into Neo4j via CSV import using the following files in `data/neo4j/`:

- `employees.csv` → `(:Employee)` nodes
- `emails.csv` → `(:Email)` nodes
- `chunks.csv` → `(:Chunk)` nodes (paragraph-bounded text splits)
- `entities.csv` → `(:Entity)` nodes (spaCy `en_core_web_sm` NER)
- `sent_relationships.csv` → `[:SENT]` edges
- `received_relationships.csv` → `[:RECEIVED_BY]` edges
- `contains_relationships.csv` → `[:CONTAINS]` edges
- `mentions_relationships.csv` → `[:MENTIONS]` edges (with occurrence count)
- `entity_relationships.csv` → `[:RELATED_TO]` edges (with co-occurrence count)

### Indexing and Constraints

Uniqueness constraints and indexes were created on primary keys:
- `Employee.employee_id` (unique)
- `Employee.email` (index)
- `Email.email_id` (unique)
- `Chunk.chunk_id` (unique)
- `Entity.entity_id` (unique)

Full DDL is documented in `data/neo4j/NEO4J_SCHEMA.md`.

## 6. How the Graph Supports Graph-RAG

The graph structure enables multi-hop traversal patterns that the retrieval layer uses:

1. **Shallow lookup** (depth 1): `Employee` node by name or email
2. **Email retrieval** (depth 2): `Employee → Email` via `[:SENT]` or `[:RECEIVED_BY]`
3. **Content access** (depth 3): `Email → Chunk` via `[:CONTAINS]`
4. **Entity extraction** (depth 4): `Chunk → Entity` via `[:MENTIONS]`
5. **Relationship exploration** (depth 5): `Entity → Entity` via `[:RELATED_TO]`

Each depth level exposes progressively more information from the graph. This natural depth hierarchy is the foundation of the AegisGraph security model's graph footprint signal.

## 7. Validation Performed

A 15-point integrity validation suite was executed and documented in `data/neo4j/NEO4J_VALIDATION_REPORT.md`:

- Exactly 50,042 Email nodes matching the selected IDs
- Zero duplicate node IDs across all node types
- Zero orphan or dangling relationships across all relationship CSVs
- RFC-4180 standard escaping for all text fields
- Graph connectivity validation (single connected component)

## 8. Limitations

1. **No organizational roles**: Historical Enron employee roles (CEO, HR, Manager) are not encoded on `(:Employee)` nodes because they were not reliably available across the corpus.
2. **Entity quality**: Named entities were extracted using spaCy `en_core_web_sm`, which is a lightweight model. Entity extraction quality varies, particularly for domain-specific financial terminology.
3. **Static snapshot**: The graph represents a static historical corpus, not a live communication system.
4. **No RBAC on historical data**: The graph does not contain access control metadata. RBAC is enforced at the application layer.
