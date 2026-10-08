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
            # Clean intent stop words to extract the name
            name_hint = query.lower()
            name_hint = re.sub(r"[^\w\s@.]", "", name_hint) # Remove punctuation except @ and .
            stopwords = [
                "what", "emails", "did", "send", "receive", "who", "is",
                "find", "employee", "sent", "by", "received", "from",
                "look", "up", "search", "for", "the", "about", "tell", "me",
                "does", "communicate", "with", "frequently", "topics", "frequent",
                "mention", "belong", "to", "organization", "info", "information",
                "were", "was", "discussed", "has", "have", "had"
            ]
            for word in stopwords:
                name_hint = re.sub(rf"\b{word}\b", "", name_hint)
            name_hint = re.sub(r"\s+", " ", name_hint).strip()
            # If nothing left (e.g. "find employee"), fallback to original
            if not name_hint:
                name_hint = query.strip()

        # Try name-based search
        results = await self.strategies.lookup_employee_by_name(name_hint, limit=5)

        if len(results) == 1:
            return ResolvedEntity(
                type="employee",
                query_value=name_hint,
                status=ResolutionStatus.FOUND,
                matches=results,
            )
        elif len(results) > 1:
            return ResolvedEntity(
                type="employee",
                query_value=name_hint,
                status=ResolutionStatus.AMBIGUOUS,
                matches=results,
            )

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
                term_results = await self.strategies.lookup_employee_by_name(term, limit=5)
                if len(term_results) == 1:
                    logger.info(f"LLM fallback successfully resolved entity: {term}")
                    return ResolvedEntity(
                        type="employee",
                        query_value=term,
                        status=ResolutionStatus.FOUND,
                        matches=term_results,
                    )
                elif len(term_results) > 1:
                    logger.info(f"LLM fallback resulted in ambiguous entity: {term}")
                    return ResolvedEntity(
                        type="employee",
                        query_value=term,
                        status=ResolutionStatus.AMBIGUOUS,
                        matches=term_results,
                    )
        
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
