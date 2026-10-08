# Knowledge Graph Enrichment Implementation

## 1. Objective
Following the inspection phase, we implemented a safe, reproducible, and idempotent enrichment pipeline to augment the AegisGraph Neo4j database. The goal was to derive direct social and topical relationships from existing communication pathways to enable more robust security graph-traversal demonstrations.

## 2. Baseline Graph Statistics (Before Enrichment)
- **Employee nodes:** 8,263
- **Email nodes:** 50,042
- **Chunk nodes:** 82,384
- **Entity nodes:** 166,884
- **Relationships:** `SENT` (50k), `RECEIVED_BY` (454k), `CONTAINS` (82k), `MENTIONS` (1m+), `RELATED_TO` (100k)

## 3. Distribution Analysis & Threshold Selection
We ran aggregate Cypher queries to measure the distribution of indirect pathways before materializing them into direct edges.

**Communication Network (`Employee -> Email -> Employee`):**
- Total unique pairs (1+ emails): 30,276
- Pairs with 2+ emails: 21,853
- Pairs with 5+ emails: 11,644
- **Threshold Selected:** `weight >= 5`. This eliminates one-off emails and noise, creating a highly confident social network with ~1.4 average degree.

**Topical Mentions (`Employee -> Email -> Chunk -> Entity`):**
- Total unique pairs (1+ mentions): 368,829
- Pairs with 5+ mentions: 31,902
- Pairs with 10+ mentions: 13,304
- **Threshold Selected:** `count >= 10`. This eliminates NLP extraction errors and passing mentions, ensuring the Employee is genuinely associated with the Entity topic over multiple instances.

## 4. Enrichment Methodology
The enrichment was executed via a dedicated, idempotent Python script (`backend/scripts/enrich_knowledge_graph.py`). The script executed the following Cypher `MERGE` commands:

1. **Organization Nodes & BELONGS_TO**
   ```cypher
   MATCH (e:Employee) WHERE e.domain IS NOT NULL AND trim(e.domain) <> ''
   WITH DISTINCT e.domain AS domain
   MERGE (o:Organization {name: domain})

   MATCH (e:Employee) WHERE e.domain IS NOT NULL AND trim(e.domain) <> ''
   MATCH (o:Organization {name: e.domain})
   MERGE (e)-[:BELONGS_TO]->(o)
   ```

2. **COMMUNICATES_FREQUENTLY_WITH**
   ```cypher
   MATCH (p1:Employee)-[:SENT]->(:Email)-[:RECEIVED_BY]->(p2:Employee)
   WHERE p1 <> p2
   WITH p1, p2, count(*) as weight WHERE weight >= 5
   MERGE (p1)-[r:COMMUNICATES_FREQUENTLY_WITH]->(p2)
   SET r.weight = weight
   ```

3. **FREQUENTLY_MENTIONS**
   ```cypher
   MATCH (p:Employee)-[:SENT]->(:Email)-[:CONTAINS]->(:Chunk)-[:MENTIONS]->(ent:Entity)
   WITH p, ent, sum(1) as total_mentions WHERE total_mentions >= 10
   MERGE (p)-[r:FREQUENTLY_MENTIONS]->(ent)
   SET r.count = total_mentions
   ```

## 5. Final Graph Statistics (After Enrichment)
The following nodes and relationships were successfully generated:
- **New Nodes:** 526 `Organization` nodes (from distinct domains).
- **New Edges:** 
  - 11,644 `COMMUNICATES_FREQUENTLY_WITH`
  - 13,304 `FREQUENTLY_MENTIONS`
  - 8,263 `BELONGS_TO`

## 6. Validation Examples
We ran validation queries to confirm data integrity.
**Query:** Who does Veronica Espinoza communicate with most frequently?
- Russell Diamond (139 times)
- Tom Moran (112 times)
- Tana Jones (107 times)

**Query:** What topics does Veronica Espinoza frequently discuss?
- Bill Bradford (PERSON)
- Credit Watch (ORG)

**Query:** Who belongs to pkns.com?
- Djn, Dcastro, Mlk

## 7. Future Retrieval Integration
The enrichment enables powerful $O(1)$ conversational retrieval without needing deep, expensive database scans.
In the future, we can update the backend's Retrieval Strategies to support:
- `"Who does [Person] work with?"` $\to$ traverse `COMMUNICATES_FREQUENTLY_WITH`
- `"What does [Person] care about?"` $\to$ traverse `FREQUENTLY_MENTIONS`
- `"Who works at [Domain]?"` $\to$ traverse `BELONGS_TO`

**Crucially, these new dense edges will force the Adaptive Policy Engine to restrict access properly during the security demonstration. High-risk ($d_{eff} = 0$) sessions will be correctly blocked from sweeping the social network.**

## 8. Limitations
- `COMMUNICATES_FREQUENTLY_WITH` represents email frequency only; it does not prove a formal reporting structure.
- `FREQUENTLY_MENTIONS` depends on the accuracy of the upstream spaCy NER extraction model.
