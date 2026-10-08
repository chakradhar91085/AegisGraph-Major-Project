from typing import List, Dict, Any
from app.db.postgres import engine, AsyncSessionLocal
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)

MAX_LIMIT = 50

class PostgresRetrievalStrategies:
    def _cap_limit(self, limit: int) -> int:
        return min(max(limit, 1), MAX_LIMIT)

    async def _execute_query(self, query: str, params: dict) -> List[Dict[str, Any]]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(text(query), params)
            rows = result.mappings().all()
            return [dict(row) for row in rows]

    async def lookup_employee_by_email(self, email: str) -> List[Dict[str, Any]]:
        query = """
        SELECT email, name
        FROM persons
        WHERE email = :email
        LIMIT 1
        """
        return await self._execute_query(query, {"email": email.strip().lower()})

    async def lookup_employee_by_name(self, name: str, limit: int = 5) -> List[Dict[str, Any]]:
        query = """
        SELECT email, name
        FROM persons
        WHERE LOWER(email) LIKE :name_like
           OR LOWER(email) LIKE :name_like2
           OR (name IS NOT NULL AND name != '' AND LOWER(name) LIKE :name_like)
        LIMIT :limit
        """
        name_clean = name.strip().lower()
        params = {
            "name_like": f"%{name_clean.replace(' ', '.')}%",
            "name_like2": f"%{name_clean.replace(' ', '')}%",
            "limit": self._cap_limit(limit)
        }
        return await self._execute_query(query, params)

    async def fuzzy_lookup_employee(self, name: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Typo-tolerant Person search via pg_trgm, best match first.
        Equivalent to the Neo4j fuzzy_lookup_employee (full-text fuzzy index)."""
        name_clean = name.strip().lower()
        if not name_clean:
            return []
        query = """
        SELECT email, name,
               GREATEST(
                   similarity(email, :dotted),
                   similarity(email, :joined),
                   COALESCE(similarity(name, :raw), 0)
               ) AS score
        FROM persons
        WHERE email % :dotted OR email % :joined OR (name IS NOT NULL AND name % :raw)
        ORDER BY score DESC
        LIMIT :limit
        """
        return await self._execute_query(query, {
            "raw": name_clean,
            "dotted": name_clean.replace(" ", "."),
            "joined": name_clean.replace(" ", ""),
            "limit": self._cap_limit(limit),
        })

    async def get_sent_emails(self, person_email: str, limit: int = 10) -> List[Dict[str, Any]]:
        query = """
        SELECT email_id, subject, sent_at as timestamp, body
        FROM emails
        WHERE sender_email = :email
        ORDER BY sent_at DESC
        LIMIT :limit
        """
        return await self._execute_query(query, {"email": person_email, "limit": self._cap_limit(limit)})

    async def get_received_emails(self, person_email: str, limit: int = 10) -> List[Dict[str, Any]]:
        query = """
        SELECT e.email_id, e.subject, e.sent_at as timestamp, e.body
        FROM emails e
        JOIN email_recipients er ON e.email_id = er.email_id
        WHERE er.person_email = :email
        ORDER BY e.sent_at DESC
        LIMIT :limit
        """
        return await self._execute_query(query, {"email": person_email, "limit": self._cap_limit(limit)})

    async def get_topical_footprint(self, person_email: str, limit: int = 20) -> List[Dict[str, Any]]:
        query = """
        SELECT et.topic_name, COUNT(*) as count
        FROM emails e
        JOIN email_topic et ON e.email_id = et.email_id
        WHERE e.sender_email = :email
        GROUP BY et.topic_name
        ORDER BY count DESC
        LIMIT :limit
        """
        return await self._execute_query(query, {"email": person_email, "limit": self._cap_limit(limit)})

    async def get_frequent_communication(self, person_email: str, limit: int = 10) -> List[Dict[str, Any]]:
        query = """
        SELECT er.person_email as email, p.name, COUNT(DISTINCT e.email_id) as email_count
        FROM emails e
        JOIN email_recipients er ON e.email_id = er.email_id
        LEFT JOIN persons p ON p.email = er.person_email
        WHERE e.sender_email = :email AND er.person_email != :email
        GROUP BY er.person_email, p.name
        ORDER BY email_count DESC
        LIMIT :limit
        """
        return await self._execute_query(query, {"email": person_email, "limit": self._cap_limit(limit)})

    async def get_person_connection(self, email_1: str, email_2: str, limit: int) -> List[Dict[str, Any]]:
        query = """
        SELECT e.sender_email as from_email, e.subject as via_email_subject, er.person_email as to_email
        FROM emails e
        JOIN email_recipients er ON e.email_id = er.email_id
        WHERE e.sender_email = :email1 AND er.person_email = :email2
        LIMIT :limit
        """
        return await self._execute_query(query, {"email1": email_1, "email2": email_2, "limit": self._cap_limit(limit)})

    async def semantic_graph_search(self, embedding: List[float], limit: int = 10) -> List[Dict[str, Any]]:
        return []

    async def resolve_topic(self, name: str) -> List[Dict[str, Any]]:
        query = """
        SELECT name AS entity_id, name AS entity_name, 'Topic' AS entity_type
        FROM topics
        WHERE LOWER(name) LIKE :name_like
        LIMIT 5
        """
        return await self._execute_query(query, {"name_like": f"%{name.strip().lower()}%"})

    async def ensure_person_fuzzy_index(self) -> None:
        """Idempotent: pg_trgm extension + trigram indexes fuzzy_lookup_employee relies on."""
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS persons_email_trgm_idx ON persons USING gin (email gin_trgm_ops)"
            ))
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS persons_name_trgm_idx ON persons USING gin (name gin_trgm_ops)"
            ))

postgres_retrieval_strategies = PostgresRetrievalStrategies()
