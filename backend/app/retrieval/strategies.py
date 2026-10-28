"""
AegisGraph Phase 2 — Parameterized Cypher retrieval strategies.

All queries use Neo4j query parameters ($param). No string interpolation.
Every query has a configurable LIMIT. No unrestricted traversals.

SCHEMA (actual ingested data):
  Labels:  Person (email, name), Email (email_id, sent_at, subject, message_id, source_path, body), Topic (name)
  Rels:    SENT (Person->Email), SENT_TO (Email->Person), CC_TO (Email->Person),
           DISCUSSES (Email->Topic), REPLY_TO (Email->Email)
"""
import re
from typing import List, Dict, Any
from app.db.neo4j import neo4j_client
import logging

logger = logging.getLogger(__name__)

MAX_LIMIT = 50  # Hard ceiling for any retrieval operation


def fuzzy_search_terms(name: str) -> str:
    """Lucene query where every name word must match, allowing 1 typo in short
    words and 2 in longer ones ("christopher calgar" finds "christopher.calger")."""
    terms = []
    for word in re.findall(r"[a-z0-9]+", name.lower()):
        if len(word) < 2:
            continue
        typos = "~" if len(word) >= 5 else "~1" if len(word) >= 3 else ""
        terms.append(f"+{word}{typos}")
    return " ".join(terms)


class RetrievalStrategies:
    """
    Contains all parameterized Cypher retrieval strategies.

    This class is the single point where Cypher is defined.
    A future AegisGraph security layer can intercept calls to these methods
    to enforce behavioral risk policies before graph access.
    """

    def __init__(self):
        self.db = neo4j_client

    def _cap_limit(self, limit: int) -> int:
        """Enforce hard ceiling on result limits."""
        return min(max(limit, 1), MAX_LIMIT)

    # ------------------------------------------------------------------
    # Strategy A — Person Lookup (by email)
    # ------------------------------------------------------------------

    async def lookup_employee_by_email(self, email: str) -> List[Dict[str, Any]]:
        """Find a Person node by exact email address."""
        query = """
        MATCH (p:Person {email: $email})
        RETURN p.email AS email, p.name AS name
        LIMIT 1
        """
        return await self.db.execute_read(query, {"email": email.strip().lower()})

    async def lookup_employee_by_name(
        self, name: str, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Find Person nodes by case-insensitive search on the email property.
        Since the 'name' field is empty for most Person nodes, we search by
        matching the name fragment against the email local part.
        """
        query = """
        MATCH (p:Person)
        WHERE toLower(p.email) CONTAINS toLower(replace($name, ' ', '.'))
           OR toLower(p.email) CONTAINS toLower(replace($name, ' ', ''))
           OR (p.name <> '' AND toLower(p.name) CONTAINS toLower($name))
        RETURN p.email AS email, p.name AS name
        LIMIT $limit
        """
        return await self.db.execute_read(
            query, {"name": name.strip(), "limit": self._cap_limit(limit)}
        )

    async def rank_employee_by_name(self, name: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Like lookup_employee_by_name, but best match first (deterministic).

        tier 0 = the name equals the email's local part / stored name, tier 1 = it
        starts it, tier 2 = it appears inside it. Ties are broken by how many emails
        the address sent, so the main mailbox beats a stray alias. Without the ORDER BY,
        LIMIT kept an arbitrary few matches and the answer changed from run to run.
        """
        clean = name.strip().lower()
        if not clean:
            return []
        query = """
        MATCH (p:Person)
        WHERE toLower(p.email) CONTAINS $dotted
           OR toLower(p.email) CONTAINS $joined
           OR (p.name <> '' AND toLower(p.name) CONTAINS $name)
        WITH p, split(toLower(p.email), '@')[0] AS local_part, toLower(coalesce(p.name, '')) AS lname
        WITH p,
             CASE WHEN local_part IN [$dotted, $joined] OR lname = $name THEN 0
                  WHEN local_part STARTS WITH $dotted OR local_part STARTS WITH $joined
                       OR lname STARTS WITH $name THEN 1
                  ELSE 2 END AS tier
        ORDER BY tier, p.email
        LIMIT 25
        RETURN p.email AS email, p.name AS name, tier,
               COUNT { (p)-[:SENT]->() } AS activity
        ORDER BY tier, activity DESC, email
        LIMIT $limit
        """
        return await self.db.execute_read(query, {
            "name": clean,
            "dotted": clean.replace(" ", "."),
            "joined": clean.replace(" ", ""),
            "limit": self._cap_limit(limit),
        })

    async def ensure_person_fuzzy_index(self) -> None:
        """Create the full-text index fuzzy_lookup_employee relies on (idempotent).
        The 'simple' analyzer splits emails on punctuation, so each name part is its own word."""
        await self.db.execute_read(
            "CREATE FULLTEXT INDEX person_name_fuzzy IF NOT EXISTS "
            "FOR (p:Person) ON EACH [p.email, p.name] "
            "OPTIONS {indexConfig: {`fulltext.analyzer`: 'simple'}}"
        )

    async def fuzzy_lookup_employee(self, name: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Typo-tolerant Person search, best match first (includes a relevance score)."""
        search = fuzzy_search_terms(name)
        if not search:
            return []
        query = """
        CALL db.index.fulltext.queryNodes('person_name_fuzzy', $search) YIELD node, score
        RETURN node.email AS email, node.name AS name, score
        LIMIT $limit
        """
        return await self.db.execute_read(
            query, {"search": search, "limit": self._cap_limit(limit)}
        )

    # ------------------------------------------------------------------
    # Strategy B — Sent Emails
    # ------------------------------------------------------------------

    async def get_sent_emails(
        self, person_email: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Retrieve emails sent by a specific person."""
        query = """
        MATCH (p:Person {email: $person_email})-[:SENT]->(e:Email)
        RETURN e.emailId AS email_id, e.subject AS subject,
               e.sent_at AS timestamp, e.body AS body
        ORDER BY e.sent_at DESC
        LIMIT $limit
        """
        return await self.db.execute_read(
            query, {"person_email": person_email, "limit": self._cap_limit(limit)}
        )

    # ------------------------------------------------------------------
    # Strategy C — Received Emails (via SENT_TO)
    # ------------------------------------------------------------------

    async def get_received_emails(
        self, person_email: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Retrieve emails received by a specific person (via SENT_TO relationship)."""
        query = """
        MATCH (e:Email)-[:SENT_TO]->(p:Person {email: $person_email})
        RETURN e.emailId AS email_id, e.subject AS subject,
               e.sent_at AS timestamp, e.body AS body
        ORDER BY e.sent_at DESC
        LIMIT $limit
        """
        return await self.db.execute_read(
            query, {"person_email": person_email, "limit": self._cap_limit(limit)}
        )

    # ------------------------------------------------------------------
    # Strategy D — Topics Discussed by a Person (Topical Footprint)
    # ------------------------------------------------------------------

    async def get_topical_footprint(
        self, person_email: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Retrieve topics most frequently discussed in a person's sent emails."""
        query = """
        MATCH (p:Person {email: $person_email})-[:SENT]->(e:Email)-[:DISCUSSES]->(t:Topic)
        RETURN t.name AS topic_name, count(*) AS count
        ORDER BY count DESC
        LIMIT $limit
        """
        return await self.db.execute_read(
            query, {"person_email": person_email, "limit": self._cap_limit(limit)}
        )

    # ------------------------------------------------------------------
    # Strategy E — Frequent Communication Partners
    # ------------------------------------------------------------------

    async def get_frequent_communication(
        self, person_email: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Retrieve people this person communicates with most frequently.
        Computed from shared SENT->Email->SENT_TO patterns."""
        query = """
        MATCH (p1:Person {email: $person_email})-[:SENT]->(e:Email)-[:SENT_TO]->(p2:Person)
        WHERE p2.email <> $person_email
        RETURN p2.email AS email, p2.name AS name, count(DISTINCT e) AS email_count
        ORDER BY email_count DESC
        LIMIT $limit
        """
        return await self.db.execute_read(
            query, {"person_email": person_email, "limit": self._cap_limit(limit)}
        )

    # ------------------------------------------------------------------
    # Strategy F — Person Connection (shortest path via shared emails)
    # ------------------------------------------------------------------

    async def get_person_connection(
        self, email_1: str, email_2: str, limit: int
    ) -> List[Dict[str, Any]]:
        """Find a communication path between two people via shared emails."""
        # Use a 2-hop pattern: Person1 -[:SENT]-> Email <-[:SENT_TO]- (implicit) -> Person2
        query = """
        MATCH (p1:Person {email: $email1})-[:SENT]->(e:Email)-[:SENT_TO]->(p2:Person {email: $email2})
        RETURN p1.email AS from_email, e.subject AS via_email_subject, p2.email AS to_email
        LIMIT $limit
        """
        return await self.db.execute_read(
            query, {"email1": email_1, "email2": email_2, "limit": self._cap_limit(limit)}
        )

    # ------------------------------------------------------------------
    # Strategy G — Semantic Graph Search (Hybrid RAG)
    # ------------------------------------------------------------------

    async def semantic_graph_search(
        self, embedding: List[float], limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Find emails semantically similar to a query embedding, and traverse the graph to get sender context."""
        query = """
        CALL db.index.vector.queryNodes('email_embeddings', $limit, $embedding)
        YIELD node AS e, score
        OPTIONAL MATCH (p:Person)-[:SENT]->(e)
        RETURN e.emailId AS email_id, e.subject AS subject, e.body AS body, e.sent_at AS timestamp,
               p.email AS sender_email, p.name AS sender_name, score
        ORDER BY score DESC
        """
        return await self.db.execute_read(
            query, {"embedding": embedding, "limit": self._cap_limit(limit)}
        )

    async def resolve_topic(self, name: str) -> List[Dict[str, Any]]:
        query = """
        MATCH (t:Topic)
        WHERE toLower(t.name) CONTAINS toLower($name)
        RETURN t.name AS entity_id, t.name AS entity_name,
               'Topic' AS entity_type
        LIMIT 5
        """
        return await self.db.execute_read(query, {"name": name})

# Module-level singleton
retrieval_strategies = RetrievalStrategies()
