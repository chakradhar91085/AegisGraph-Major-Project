"""
AegisGraph Phase 3A — Context Builder

Converts structured retrieval results (from Phase 2) into a compact,
deterministic text context for the LLM. Enforces size limits.
"""
from typing import List, Dict, Any
from app.retrieval.schemas import RetrievalResponse, ResolutionStatus
from app.core.config import settings
from app.security.masking import names_from_text
import logging

logger = logging.getLogger(__name__)


class ContextBuilder:
    def __init__(self):
        self.max_records = settings.MAX_RECORDS
        self.max_chunk_chars = settings.MAX_CHUNK_CHARS
        self.max_context_chars = settings.MAX_CONTEXT_CHARS

    def build_context(self, response: RetrievalResponse, effective_limit: int = None) -> str:
        """
        Takes a RetrievalResponse and formats it into a deterministic text block.
        Truncates according to limits and dynamic effective_limit.
        """
        if not response.results or response.result_count == 0:
            return "No relevant context found."

        # Determine active record limit
        limit = min(effective_limit, self.max_records) if effective_limit is not None else self.max_records
        
        # Truncate number of records
        results_to_process = response.results[:limit]
        
        context_parts = []
        strategy = response.strategy

        if strategy == "employee_lookup":
            context_parts.extend(self._format_employee(response, results_to_process))
        elif strategy in ("sent_emails", "received_emails"):
            context_parts.extend(self._format_emails(response, results_to_process))
        elif strategy == "email_chunks":
            context_parts.extend(self._format_chunks(response, results_to_process))
        elif strategy == "chunk_entities":
            context_parts.extend(self._format_entities(response, results_to_process))
        elif strategy == "entity_relationships":
            context_parts.extend(self._format_entity_relationships(response, results_to_process))
        elif strategy == "frequent_communication":
            context_parts.extend(self._format_frequent_communication(response, results_to_process))
        elif strategy == "topical_footprint":
            context_parts.extend(self._format_topical_footprint(response, results_to_process))
        elif strategy == "organization_info":
            context_parts.extend(self._format_organization_info(response, results_to_process))
        elif strategy == "person_connection":
            context_parts.extend(self._format_person_connection(response, results_to_process))
        else:
            # Fallback formatting
            context_parts.extend(self._format_generic(response, results_to_process))
            
        # Join and truncate total context length
        full_context = "\n\n".join(context_parts)
        
        if len(full_context) > self.max_context_chars:
            logger.warning(
                f"Context length ({len(full_context)}) exceeds MAX_CONTEXT_CHARS "
                f"({self.max_context_chars}). Truncating."
            )
            full_context = full_context[:self.max_context_chars] + "\n\n...[TRUNCATED due to length limits]"
            
        return full_context

    def _get_subject_header(self, response: RetrievalResponse) -> str:
        """Helper to extract subject info securely from resolved entities."""
        if not response.resolved_entities:
            return ""
        parts = []
        for i, entity in enumerate(response.resolved_entities):
            if entity.status == ResolutionStatus.FOUND and entity.matches:
                match = entity.matches[0]
                name = match.get("name") or match.get("entity_name") or entity.query_value
                typ = "Employee" if entity.type == "employee" else "Entity"
                if len(response.resolved_entities) > 1:
                    parts.append(f"Identified {typ} {i+1}: {name}")
                else:
                    parts.append(f"Identified {typ}: {name}")
        if parts:
            return "\n".join(parts)
        return ""

    def _format_employee(self, response: RetrievalResponse, results: List[Dict[str, Any]]) -> List[str]:
        parts = ["PERSON PROFILE"]
        asked_for = response.resolved_entities[0].query_value if response.resolved_entities else ""
        if asked_for and "@" not in asked_for:
            parts.append(f"Closest match in the graph for '{asked_for}':")
        for row in results:
            email = row.get('email') or 'Unknown'
            # Most Person nodes have no stored name; the email local part carries it.
            name = row.get('name') or next(iter(names_from_text(email)), '').title() or 'Unknown'
            parts.append(f"- Name: {name}\n- Email: {email}")
        return ["\n".join(parts)]

    def _format_emails(self, response: RetrievalResponse, results: List[Dict[str, Any]]) -> List[str]:
        header = self._get_subject_header(response)
        direction = "SENT" if response.strategy == "sent_emails" else "RECEIVED"
        parts = [f"EMAILS {direction} BY THE IDENTIFIED EMPLOYEE ({len(results)} most recent)"]
        if header:
            parts.append(header)
        for row in results:
            part = (
                f"- Subject: \"{row.get('subject', '')}\"\n"
                f"  Date: {row.get('timestamp', '')}\n"
                f"  Body: {str(row.get('body', 'No content available'))[:1000]}"
            )
            parts.append(part)
        return ["\n".join(parts)]

    def _format_chunks(self, response: RetrievalResponse, results: List[Dict[str, Any]]) -> List[str]:
        parts = ["REPRESENTATIVE EMAIL EXCERPTS"]
        for row in results:
            text = str(row.get('text', ''))
            if len(text) > self.max_chunk_chars:
                text = text[:self.max_chunk_chars] + "... [TRUNCATED]"
            part = f"- Excerpt:\n  \"{text}\""
            parts.append(part)
        return ["\n".join(parts)]

    def _format_entities(self, response: RetrievalResponse, results: List[Dict[str, Any]]) -> List[str]:
        parts = ["MENTIONED ENTITIES"]
        parts.append("The following entities were mentioned in the text:")
        for row in results:
            parts.append(
                f"  - {row.get('entity_name', '')} ({row.get('entity_type', '')}) — {row.get('mention_count', '')} mentions"
            )
        return ["\n".join(parts)]

    def _format_entity_relationships(self, response: RetrievalResponse, results: List[Dict[str, Any]]) -> List[str]:
        header = self._get_subject_header(response)
        parts = ["ENTITY RELATIONSHIPS"]
        if header:
            parts.append(header)
        parts.append("Observed co-occurrences:")
        for row in results:
            parts.append(
                f"  - {row.get('entity_name', '')} ({row.get('entity_type', '')}) — {row.get('co_occurrence_count', '')} co-occurrences"
            )
        return ["\n".join(parts)]

    def _format_generic(self, response: RetrievalResponse, results: List[Dict[str, Any]]) -> List[str]:
        header = self._get_subject_header(response)
        parts = ["RETRIEVED GRAPH RECORDS"]
        if header:
            parts.append(header)
        for row in results:
            prop_str = ", ".join(f"{k}: {v}" for k, v in row.items())
            parts.append(f"- {prop_str}")
        return ["\n".join(parts)]

    def _format_frequent_communication(self, response: RetrievalResponse, results: List[Dict[str, Any]]) -> List[str]:
        header = self._get_subject_header(response)
        parts = ["COMMUNICATION PATTERNS"]
        if header:
            parts.append(header)
        parts.append("Most frequent communication partners:")
        for row in results:
            name = row.get('name') or row.get('email', '')
            parts.append(
                f"  - {name} — {row.get('email_count', '')} observed interactions"
            )
        return ["\n".join(parts)]

    def _format_topical_footprint(self, response: RetrievalResponse, results: List[Dict[str, Any]]) -> List[str]:
        header = self._get_subject_header(response)
        parts = ["TOPICS"]
        if header:
            parts.append(header)
        parts.append("Frequently discussed topics:")
        for row in results:
            parts.append(
                f"  - {row.get('topic_name', '')} — {row.get('count', '')} related emails"
            )
        return ["\n".join(parts)]

    def _format_organization_info(self, response: RetrievalResponse, results: List[Dict[str, Any]]) -> List[str]:
        header = self._get_subject_header(response)
        parts = ["ORGANIZATION MEMBERSHIP"]
        if header:
            parts.append(header)
        for row in results:
            parts.append(
                f"- Organization: {row.get('organization_name', '')}"
            )
        return ["\n".join(parts)]

    def _format_person_connection(self, response: RetrievalResponse, results: List[Dict[str, Any]]) -> List[str]:
        header = self._get_subject_header(response)
        parts = ["COMMUNICATION PATHWAYS"]
        if header:
            parts.append(header)
        for row in results:
            from_email = row.get('from_email', 'Unknown')
            to_email = row.get('to_email', 'Unknown')
            subject = row.get('via_email_subject', '')
            parts.append(f"- Path: {from_email} -> {to_email} (via email: \"{subject}\")")
        return ["\n".join(parts)]

# Module-level singleton
context_builder = ContextBuilder()
