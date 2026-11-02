"""Turns the agent's rows into a compact text context for the LLM, within size limits."""
import logging

from app.core.config import settings
from app.retrieval.schemas import RetrievalResponse

logger = logging.getLogger(__name__)


def build_context(response: RetrievalResponse, effective_limit: int) -> str:
    if not response.results:
        return "No relevant context found."

    # Agent rows often list only the answer (e.g. someone's contacts) without repeating
    # the person asked about, which small answer models read as "not found".
    parts = [f"RETRIEVED GRAPH RECORDS (fetched to answer: {response.query!r}; these rows ARE the answer data, "
             "even if they do not repeat the name that was asked about)"]
    if response.entities:
        parts.append("Identified people: " + ", ".join(response.entities))
    for row in response.results[:min(effective_limit, settings.MAX_RECORDS)]:
        parts.append("- " + ", ".join(f"{k}: {v}" for k, v in row.items()))
    context = "\n".join(parts)

    if len(context) > settings.MAX_CONTEXT_CHARS:
        logger.warning(f"Context length ({len(context)}) exceeds MAX_CONTEXT_CHARS. Truncating.")
        context = context[:settings.MAX_CONTEXT_CHARS] + "\n\n...[TRUNCATED due to length limits]"
    return context
