"""
AegisGraph Phase 2 — Deterministic entity resolution.

Resolves user-provided names/emails to actual graph nodes.
Returns confidence/status: found, ambiguous, or not_found.
Never silently picks between ambiguous matches.
"""
import re
from typing import Optional
from app.retrieval.schemas import ResolvedEntity, ResolutionStatus
import os

if os.getenv("USE_POSTGRES_RETRIEVAL", "false").lower() == "true":
    from app.retrieval.postgres_strategies import postgres_retrieval_strategies as retrieval_strategies
else:
    from app.retrieval.strategies import retrieval_strategies
import logging

logger = logging.getLogger(__name__)

EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")


class EntityResolver:
    """
    Deterministic entity resolution for the retrieval pipeline.

    Resolution priority:
    1. Exact email match (Employee)
    2. Name search (Employee)
    3. Entity name search (Entity)

    This component is designed to be replaceable with a more sophisticated
    resolver (e.g., fuzzy matching, LLM-assisted) in a future phase.
    """

    def __init__(self):
        self.strategies = retrieval_strategies

    def extract_email(self, text: str) -> Optional[str]:
        """Extract the first email address from text, if present."""
        match = EMAIL_PATTERN.search(text)
        return match.group(0).lower() if match else None

    # Words that carry the question, not the person's name.
    _STOPWORDS = {
        "what", "which", "whose", "whom", "who", "where", "when", "how", "many", "much",
        "show", "give", "list", "get", "fetch", "display", "tell", "me", "us", "please",
        "can", "could", "would", "you", "i", "we", "pls", "kindly", "need", "want", "like",
        "is", "are", "was", "were", "be", "been", "do", "does", "did", "has", "have", "had",
        "a", "an", "the", "of", "on", "in", "at", "all", "any", "some", "every", "recent",
        "latest", "last", "first", "top", "his", "her", "their", "its", "my",
        "email", "emails", "mail", "mails", "message", "messages", "inbox", "outbox",
        "send", "sent", "sends", "sending", "receive", "received", "receives", "receiving",
        "write", "wrote", "written", "got",
        "find", "search", "look", "up", "lookup", "for", "about", "from", "to", "by", "with",
        "employee", "employees", "person", "people", "user", "worker", "info", "information",
        "details", "detail", "communicate", "communicates", "communicated", "communication",
        "frequently", "frequent", "often", "most", "talk", "talks", "topics", "topic",
        "mention", "mentions", "discussed", "discuss", "belong", "organization", "and", "or",
        "s", "that", "this", "these", "those", "there", "it", "if", "so", "just", "also", "ever",
    }

    def clean_name_hint(self, query: str) -> str:
        """Strip question words from a query, leaving the person's name."""
        text = re.sub(r"['\u2019]s\b", "", query.lower())      # possessives: "lay's emails"
        text = re.sub(r"[^\w\s@.]", " ", text)
        words = [w.strip(".") for w in text.split()]
        kept = [w for w in words if w and w not in self._STOPWORDS]
        return " ".join(kept) or query.strip()

    async def _name_search(self, name_hint: str) -> list:
        """Ranked name search; falls back to dropping leading/trailing words so one
        stray word in the question doesn't make a real person "not found"."""
        rank = getattr(self.strategies, "rank_employee_by_name", None)
        words = name_hint.split()
        candidates = [name_hint]
        if len(words) > 2:
            candidates += [" ".join(words[:2]), " ".join(words[-2:])]
        for cand in candidates:
            if rank:
                found = await rank(cand, limit=5)
            else:
                found = await self.strategies.lookup_employee_by_name(cand, limit=5)
            if found:
                return found
        return []

    @staticmethod
    def _entity_from_matches(query_value: str, results: list) -> ResolvedEntity:
        """FOUND when one candidate clearly wins, else AMBIGUOUS."""
        matches = [{"email": r["email"], "name": r.get("name")} for r in results]
        winner = len(results) == 1
        if not winner and "tier" in results[0]:
            first, second = results[0], results[1]
            if first["tier"] < second["tier"]:
                winner = True          # exact/prefix match beats a mere substring match
            elif first["tier"] == second["tier"]:
                # same quality: the address that sent clearly more mail is the person's main one
                winner = first.get("activity", 0) >= 3 * max(second.get("activity", 0), 1)
        return ResolvedEntity(
            type="employee",
            query_value=query_value,
            status=ResolutionStatus.FOUND if winner else ResolutionStatus.AMBIGUOUS,
            matches=matches[:1] if winner else matches,
        )

    async def resolve_employee(self, query: str, extracted_params: dict = None, llm_provider: str | None = None) -> ResolvedEntity:
        """
        Attempt to resolve a user query to an Employee node.

        Strategy:
        1. If query contains an email address, try exact email match.
        2. Otherwise, search by name using deterministic heuristics.
        3. If deterministic fails, use LLM extracted_params to try name lookups.
        """
        email = self.extract_email(query)

        if email:
            results = await self.strategies.lookup_employee_by_email(email)
            if len(results) == 1:
                return ResolvedEntity(
                    type="employee",
                    query_value=email,
                    status=ResolutionStatus.FOUND,
                    matches=results,
                )
            elif len(results) > 1:
                return ResolvedEntity(
                    type="employee",
                    query_value=email,
                    status=ResolutionStatus.AMBIGUOUS,
                    matches=results,
                )
            # Email not found — fall through to name search using the local part
            name_hint = email.split("@")[0].replace(".", " ")
        else:
            name_hint = self.clean_name_hint(query)

        # Try name-based search (ranked, so the result does not depend on row order)
        results = await self._name_search(name_hint)
        if results:
            return self._entity_from_matches(name_hint, results)

        # Typo-tolerant search before letting the LLM guess spellings.
        fuzzy = await self.strategies.fuzzy_lookup_employee(name_hint, limit=5)
        if fuzzy:
            # ponytail: a 5% score lead picks one person; tied scores usually mean one person
            # under several Enron addresses, so ask the user. Merge identities if that gets annoying.
            clear_leader = len(fuzzy) == 1 or fuzzy[0]["score"] >= fuzzy[1]["score"] * 1.05
            chosen = fuzzy[:1] if clear_leader else fuzzy
            return ResolvedEntity(
                type="employee",
                query_value=name_hint,
                status=ResolutionStatus.FOUND if clear_leader else ResolutionStatus.AMBIGUOUS,
                matches=[{"email": m["email"], "name": m["name"]} for m in chosen],
            )

        # 3. LLM Fallback if NOT_FOUND deterministically
        logger.debug(f"Deterministic entity resolution failed for {query!r}. Attempting LLM fallback.")
        if not extracted_params:
            from app.retrieval.schemas import RetrievalIntent
            from app.llm.provider_factory import get_llm_provider
            allowed_intents = [i.value for i in RetrievalIntent]
            provider = get_llm_provider(llm_provider)
            extracted_params = await provider.extract_query_parameters(query, allowed_intents)
                
        if extracted_params:
            search_terms = extracted_params.get("search_terms", [])
            primary_person = extracted_params.get("primary_person")
            if primary_person and primary_person not in search_terms:
                search_terms.insert(0, primary_person)
                
            for term in search_terms:
                if not term or len(term.strip()) < 2:
                    continue
                term_results = await self._name_search(term)
                if term_results:
                    logger.info(f"LLM fallback resolved entity: {term}")
                    return self._entity_from_matches(term, term_results)
        
        logger.warning(f"Entity resolution completely failed for: {query!r}")
        return ResolvedEntity(
            type="employee",
            query_value=email or name_hint,
            status=ResolutionStatus.NOT_FOUND,
            matches=[],
        )

    async def resolve_entity(self, name: str) -> ResolvedEntity:
        """
        Attempt to resolve a user-provided name to an Entity node.
        Uses case-insensitive name search on the Entity label.
        """
        clean_name = name.lower()
        clean_name = re.sub(r"[^\w\s@.]", "", clean_name)
        stopwords = [
            "what", "entities", "are", "related", "to", "connected",
            "mentioned", "in", "chunk", "find", "search", "look", "for", "the"
        ]
        for word in stopwords:
            clean_name = re.sub(rf"\b{word}\b", "", clean_name)
        clean_name = re.sub(r"\s+", " ", clean_name).strip()
        if not clean_name:
            clean_name = name.strip()
            
        results = await self.strategies.resolve_topic(clean_name)

        if len(results) == 1:
            return ResolvedEntity(
                type="entity",
                query_value=name,
                status=ResolutionStatus.FOUND,
                matches=results,
            )
        elif len(results) > 1:
            return ResolvedEntity(
                type="entity",
                query_value=name,
                status=ResolutionStatus.AMBIGUOUS,
                matches=results,
            )
        else:
            return ResolvedEntity(
                type="entity",
                query_value=name,
                status=ResolutionStatus.NOT_FOUND,
                matches=[],
            )


# Module-level singleton
entity_resolver = EntityResolver()
