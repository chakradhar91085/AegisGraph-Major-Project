"""
AegisGraph Phase 2 — Retrieval service orchestrator.

Pipeline: Query -> Intent Classification -> Entity Resolution -> Strategy Execution -> Results

This is the single chokepoint through which all retrieval requests flow.
A future AegisGraph behavioral security layer can intercept at this level
to enforce risk policies before and after graph access.
"""
from typing import Dict, Any
from app.retrieval.schemas import (
    RetrievalRequest,
    RetrievalResponse,
    RetrievalIntent,
    ResolutionStatus,
)
from app.retrieval.intent_classifier import classify_intent
from app.retrieval.entity_resolver import entity_resolver
import os

if os.getenv("USE_POSTGRES_RETRIEVAL", "false").lower() == "true":
    from app.retrieval.postgres_strategies import postgres_retrieval_strategies as retrieval_strategies
else:
    from app.retrieval.strategies import retrieval_strategies
    
import logging

logger = logging.getLogger(__name__)
from app.core.config import settings

INTENT_DEPTH_MAP = {
    # prototype policy interpretation: d_eff=0 permits non-expansive base lookups
    RetrievalIntent.EMPLOYEE_LOOKUP: 0, 
    RetrievalIntent.SENT_EMAILS: 2,
    RetrievalIntent.RECEIVED_EMAILS: 2,
    RetrievalIntent.EMAIL_CHUNKS: 3,
    RetrievalIntent.CHUNK_ENTITIES: 4,
    RetrievalIntent.ENTITY_RELATIONSHIPS: 5,
    RetrievalIntent.ALL_EMPLOYEES: 1,
    RetrievalIntent.GRAPH_DISCOVERY: 0,
    RetrievalIntent.FREQUENT_COMMUNICATION: 1,
    RetrievalIntent.TOPICAL_FOOTPRINT: 1,
    RetrievalIntent.ORGANIZATION_INFO: 1,
    RetrievalIntent.PERSON_CONNECTION: 1,
    RetrievalIntent.SEMANTIC_SEARCH: 2,
    RetrievalIntent.UNSUPPORTED: 0
}


def _serialize_results(results: list) -> list:
    """Convert Neo4j result dicts to JSON-safe dicts (handle DateTime etc.)."""
    serialized = []
    for record in results:
        row = {}
        for key, value in record.items():
            # Neo4j DateTime objects need string conversion
            if hasattr(value, "isoformat"):
                row[key] = value.isoformat()
            else:
                row[key] = value
        serialized.append(row)
    return serialized


class RetrievalService:
    """
    Orchestrates the controlled retrieval pipeline.

    Execution flow:
    1. Classify intent
    2. Resolve entities (if needed)
    3. Execute the matching parameterized Cypher strategy
    4. Return structured results

    Security guarantees:
    - Only predefined strategies are executed
    - All Cypher is parameterized
    - Result limits are enforced
    - No arbitrary Cypher exposure
    """

    def __init__(self):
        self.strategies = retrieval_strategies
        self.resolver = entity_resolver

    async def execute(self, request: RetrievalRequest, llm_provider: str | None = None) -> RetrievalResponse:
        """
        Main entry point for all retrieval requests.

        This method is the interception point for the
        AegisGraph behavioral security layer.
        """
        # --- Phase: Intent Classification ---
        intent = await classify_intent(request.query)
        logger.info(f"Classified intent: {intent.value} for query: {request.query!r}")

        extracted_params = None
        if intent == RetrievalIntent.UNSUPPORTED:
            logger.info(f"Deterministic intent failed. Falling back to LLM extraction (provider={llm_provider or 'default'}).")
            from app.llm.provider_factory import get_llm_provider
            provider = get_llm_provider(llm_provider)
            allowed_intents = [i.value for i in RetrievalIntent]
            extracted_params = await provider.extract_query_parameters(request.query, allowed_intents)
            try:
                intent = RetrievalIntent(extracted_params.get("intent", "unsupported_intent"))
            except ValueError:
                intent = RetrievalIntent.UNSUPPORTED

        if intent == RetrievalIntent.UNSUPPORTED:
            return RetrievalResponse(
                query=request.query,
                intent=intent.value,
                results=[],
                result_count=0,
                strategy="none",
                metadata={"reason": "Query intent could not be determined."},
            )

        # --- Phase: Security Enforcement ---
        required_depth = INTENT_DEPTH_MAP.get(intent, 5)
        
        # Explicit block decision (short-circuited in RAG service mostly, but kept for defense-in-depth)
        if getattr(request, "response_mode", "ALLOW") == "BLOCK":
            logger.warning("Security block: Explicit BLOCK decision.")
            return RetrievalResponse(
                query=request.query,
                intent=intent.value,
                results=[],
                result_count=0,
                strategy="blocked_by_policy",
                metadata={"reason": "Query blocked completely by security policy."},
            )
            
        # Scope restriction exceeding permitted boundaries
        if required_depth > request.max_depth:
            logger.warning(f"Security restriction: required depth {required_depth} > max depth {request.max_depth}")
            return RetrievalResponse(
                query=request.query,
                intent=intent.value,
                results=[],
                result_count=0,
                strategy="restricted_by_policy",
                metadata={"reason": "Query exceeds permitted graph depth due to security restriction. No data accessible."},
            )

        # --- Phase: Entity Resolution + Strategy Execution ---
        if intent == RetrievalIntent.EMPLOYEE_LOOKUP:
            return await self._handle_employee_lookup(request, intent, extracted_params, llm_provider)

        elif intent == RetrievalIntent.ALL_EMPLOYEES:
            return await self._handle_all_employees(request, intent)

        elif intent == RetrievalIntent.GRAPH_DISCOVERY:
            return await self._handle_graph_discovery(request, intent)

        elif intent == RetrievalIntent.SENT_EMAILS:
            return await self._handle_employee_emails(request, intent, "sent", extracted_params, llm_provider)

        elif intent == RetrievalIntent.RECEIVED_EMAILS:
            return await self._handle_employee_emails(request, intent, "received", extracted_params, llm_provider)

        elif intent == RetrievalIntent.EMAIL_CHUNKS:
            return await self._handle_email_chunks(request, intent)

        elif intent == RetrievalIntent.CHUNK_ENTITIES:
            return await self._handle_chunk_entities(request, intent)

        elif intent == RetrievalIntent.ENTITY_RELATIONSHIPS:
            return await self._handle_entity_relationships(request, intent)

        elif intent == RetrievalIntent.FREQUENT_COMMUNICATION:
            return await self._handle_frequent_communication(request, intent, extracted_params, llm_provider)

        elif intent == RetrievalIntent.TOPICAL_FOOTPRINT:
            return await self._handle_topical_footprint(request, intent, extracted_params, llm_provider)

        elif intent == RetrievalIntent.ORGANIZATION_INFO:
            return await self._handle_organization_info(request, intent)

        elif intent == RetrievalIntent.PERSON_CONNECTION:
            return await self._handle_person_connection(request, intent, extracted_params, llm_provider)

        elif intent == RetrievalIntent.SEMANTIC_SEARCH:
            return await self._handle_semantic_search(request, intent, llm_provider)

        # Should not reach here
        return RetrievalResponse(
            query=request.query,
            intent=intent.value,
            results=[],
            result_count=0,
            strategy="none",
            metadata={"reason": "Unhandled intent."},
        )

    # ------------------------------------------------------------------
    # Intent handlers
    # ------------------------------------------------------------------

    async def _handle_employee_lookup(
        self, request: RetrievalRequest, intent: RetrievalIntent, extracted_params: dict = None, llm_provider: str | None = None
    ) -> RetrievalResponse:
        """Handle employee_lookup intent."""
        resolved = await self.resolver.resolve_employee(request.query, extracted_params, llm_provider)
        results = _serialize_results(resolved.matches)

        return RetrievalResponse(
            query=request.query,
            intent=intent.value,
            resolved_entities=[resolved],
            results=results,
            result_count=len(results),
            strategy="employee_lookup",
            metadata={"resolution_status": resolved.status.value},
        )

    async def _handle_all_employees(
        self, request: RetrievalRequest, intent: RetrievalIntent
    ) -> RetrievalResponse:
        """Handle all_employees intent by searching broadly."""
        # Empty string with the standard lookup returns the top N employees
        raw_results = await self.strategies.lookup_employee_by_name("", limit=request.limit)
        results = _serialize_results(raw_results)

        return RetrievalResponse(
            query=request.query,
            intent=intent.value,
            results=results,
            result_count=len(results),
            strategy="all_employees",
        )

    async def _handle_graph_discovery(
        self, request: RetrievalRequest, intent: RetrievalIntent
    ) -> RetrievalResponse:
        """Handle graph_discovery intent (help/discovery queries)."""
        return RetrievalResponse(
            query=request.query,
            intent=intent.value,
            results=[{
                "AegisGraph_Help": "AegisGraph is a secure Graph-RAG system over the Enron email dataset.",
                "Schema": "It contains Employees, Emails, text Chunks, and named Entities.",
                "Capabilities": "Users can explore employees, their sent/received emails, email chunks, entities mentioned in chunks, and entity co-occurrence relationships."
            }],
            result_count=1,
            strategy="graph_discovery",
            metadata={"reason": "User requested graph discovery or help."},
        )

    async def _handle_employee_emails(
        self, request: RetrievalRequest, intent: RetrievalIntent, direction: str, extracted_params: dict = None, llm_provider: str | None = None
    ) -> RetrievalResponse:
        """Handle sent_emails or received_emails intent."""
        resolved = await self.resolver.resolve_employee(request.query, extracted_params, llm_provider)

        if resolved.status == ResolutionStatus.NOT_FOUND:
            return RetrievalResponse(
                query=request.query,
                intent=intent.value,
                resolved_entities=[resolved],
                results=[],
                result_count=0,
                strategy=f"{direction}_emails",
                metadata={
                    "resolution_status": resolved.status.value,
                    "reason": f"No employee found matching the query.",
                },
            )

        if resolved.status == ResolutionStatus.AMBIGUOUS:
            return RetrievalResponse(
                query=request.query,
                intent=intent.value,
                resolved_entities=[resolved],
                results=[],
                result_count=0,
                strategy=f"{direction}_emails",
                metadata={
                    "resolution_status": resolved.status.value,
                    "reason": "Multiple employees matched. Please be more specific.",
                    "candidates": _serialize_results(resolved.matches),
                },
            )

        # Exactly one match
        employee_email = resolved.matches[0]["email"]
        if direction == "sent":
            raw_results = await self.strategies.get_sent_emails(
                employee_email, limit=request.limit
            )
        else:
            raw_results = await self.strategies.get_received_emails(
                employee_email, limit=request.limit
            )

        results = _serialize_results(raw_results)

        return RetrievalResponse(
            query=request.query,
            intent=intent.value,
            resolved_entities=[resolved],
            results=results,
            result_count=len(results),
            strategy=f"{direction}_emails",
            metadata={
                "resolution_status": resolved.status.value,
                "email": employee_email,
                "limit_applied": request.limit,
            },
        )

    async def _handle_email_chunks(
        self, request: RetrievalRequest, intent: RetrievalIntent
    ) -> RetrievalResponse:
        """Handle email_chunks intent."""
        return RetrievalResponse(
            query=request.query,
            intent=intent.value,
            results=[],
            result_count=0,
            strategy="email_chunks",
            metadata={
                "reason": "Email chunks are not supported by the current graph schema."
            },
        )

    async def _handle_chunk_entities(
        self, request: RetrievalRequest, intent: RetrievalIntent
    ) -> RetrievalResponse:
        """Handle chunk_entities intent."""
        return RetrievalResponse(
            query=request.query,
            intent=intent.value,
            results=[],
            result_count=0,
            strategy="chunk_entities",
            metadata={
                "reason": "Chunk entities are not supported by the current graph schema."
            },
        )

    async def _handle_entity_relationships(
        self, request: RetrievalRequest, intent: RetrievalIntent
    ) -> RetrievalResponse:
        """Handle entity_relationships intent."""
        return RetrievalResponse(
            query=request.query,
            intent=intent.value,
            results=[],
            result_count=0,
            strategy="entity_relationships",
            metadata={
                "reason": "Entity relationships are not supported by the current graph schema."
            },
        )

    async def _handle_frequent_communication(
        self, request: RetrievalRequest, intent: RetrievalIntent, extracted_params: dict = None, llm_provider: str | None = None
    ) -> RetrievalResponse:
        resolved = await self.resolver.resolve_employee(request.query, extracted_params, llm_provider)
        if resolved.status != ResolutionStatus.FOUND:
            return RetrievalResponse(
                query=request.query,
                intent=intent.value,
                resolved_entities=[resolved],
                results=[],
                result_count=0,
                strategy="frequent_communication",
                metadata={"reason": "Could not uniquely resolve employee."}
            )
        employee_email = resolved.matches[0]["email"]
        raw_results = await self.strategies.get_frequent_communication(employee_email, limit=request.limit)
        results = _serialize_results(raw_results)
        return RetrievalResponse(
            query=request.query,
            intent=intent.value,
            resolved_entities=[resolved],
            results=results,
            result_count=len(results),
            strategy="frequent_communication"
        )

    async def _handle_topical_footprint(
        self, request: RetrievalRequest, intent: RetrievalIntent, extracted_params: dict = None, llm_provider: str | None = None
    ) -> RetrievalResponse:
        resolved = await self.resolver.resolve_employee(request.query, extracted_params, llm_provider)
        if resolved.status != ResolutionStatus.FOUND:
            return RetrievalResponse(
                query=request.query,
                intent=intent.value,
                resolved_entities=[resolved],
                results=[],
                result_count=0,
                strategy="topical_footprint",
                metadata={"reason": "Could not uniquely resolve employee."}
            )
        employee_email = resolved.matches[0]["email"]
        raw_results = await self.strategies.get_topical_footprint(employee_email, limit=request.limit)
        results = _serialize_results(raw_results)
        return RetrievalResponse(
            query=request.query,
            intent=intent.value,
            resolved_entities=[resolved],
            results=results,
            result_count=len(results),
            strategy="topical_footprint"
        )

    async def _handle_organization_info(
        self, request: RetrievalRequest, intent: RetrievalIntent
    ) -> RetrievalResponse:
        """Handle organization_info intent."""
        return RetrievalResponse(
            query=request.query,
            intent=intent.value,
            results=[],
            result_count=0,
            strategy="organization_info",
            metadata={
                "reason": "Organization info is not supported by the current graph schema."
            },
        )

    async def _handle_person_connection(
        self, request: RetrievalRequest, intent: RetrievalIntent, extracted_params: dict = None, llm_provider: str | None = None
    ) -> RetrievalResponse:
        import re
        # Attempt to find two names. Use a simple split on ' and ' or ' with '
        match = re.search(r"(?:between|connect(?:ion|ed)\s+(?:to|between))\s+(.*?)\s+(?:and|with)\s+(.*)", request.query, re.IGNORECASE)
        
        if not match:
             return RetrievalResponse(
                query=request.query,
                intent=intent.value,
                results=[],
                result_count=0,
                strategy="person_connection",
                metadata={"reason": "Could not identify two distinct names in query."}
            )
            
        name1 = match.group(1).strip()
        name2 = match.group(2).strip()
        
        # We don't pass extracted_params to both because extracted_params typically extracts one primary_person 
        # or search terms, which might be mixed. For now, try deterministic for both, and if it fails, maybe we can't do connections yet via single fallback.
        resolved1 = await self.resolver.resolve_employee(name1)
        resolved2 = await self.resolver.resolve_employee(name2)
        
        if resolved1.status != ResolutionStatus.FOUND or resolved2.status != ResolutionStatus.FOUND:
             return RetrievalResponse(
                query=request.query,
                intent=intent.value,
                resolved_entities=[resolved1, resolved2],
                results=[],
                result_count=0,
                strategy="person_connection",
                metadata={"reason": "Could not uniquely resolve both employees."}
            )
            
        email1 = resolved1.matches[0]["email"]
        email2 = resolved2.matches[0]["email"]

        # Depth still gates whether this traversal is permitted at all (a
        # low policy depth blocks the query entirely), but the *number of
        # rows returned* is governed by request.limit, not depth — depth and
        # row-count are different things and shouldn't be conflated.
        if request.max_depth < 1:
             return RetrievalResponse(
                query=request.query,
                intent=intent.value,
                resolved_entities=[resolved1, resolved2],
                results=[],
                result_count=0,
                strategy="person_connection",
                metadata={"reason": "Graph depth limit prevents path traversal."}
            )

        raw_results = await self.strategies.get_person_connection(email1, email2, request.limit)
        results = _serialize_results(raw_results)
        return RetrievalResponse(
            query=request.query,
            intent=intent.value,
            resolved_entities=[resolved1, resolved2],
            results=results,
            result_count=len(results),
            strategy="person_connection"
        )

    async def _handle_semantic_search(
        self, request: RetrievalRequest, intent: RetrievalIntent, llm_provider: str | None = None
    ) -> RetrievalResponse:
        """Handle semantic_search intent by embedding the query and doing vector search."""
        try:
            from app.llm.provider_factory import resolve_provider_name
            if resolve_provider_name(llm_provider) == "ollama":
                from app.llm.ollama_provider import OllamaProvider
                embedding = await OllamaProvider().embed_query(request.query)
            else:
                # No Ollama: use the local sentence-transformers model (same all-MiniLM family).
                from app.security.embeddings import EmbeddingProvider
                embedding = await EmbeddingProvider().get_embedding(request.query)

            if not embedding:
                raise ValueError("Received empty embedding.")
            
            # Use bounded limit for semantic search based on effective context limit
            safe_limit = request.limit
            
            # Execute vector search
            raw_results = await self.strategies.semantic_graph_search(embedding, limit=safe_limit)
            results = _serialize_results(raw_results)
            
            return RetrievalResponse(
                query=request.query,
                intent=intent.value,
                results=results,
                result_count=len(results),
                strategy="semantic_graph_search",
                metadata={"limit_applied": safe_limit}
            )
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return RetrievalResponse(
                query=request.query,
                intent=intent.value,
                results=[],
                result_count=0,
                strategy="semantic_graph_search",
                metadata={"reason": "Vector search failed or index is not ready."}
            )

# Module-level singleton
retrieval_service = RetrievalService()
