"""
AegisGraph — Abstract LLM Provider Interface.

All LLM providers (Ollama) must implement this interface.
This ensures the rest of the application can swap providers without
touching retrieval, security, or RAG logic.
"""
from abc import ABC, abstractmethod
from typing import Optional


class BaseLLMProvider(ABC):
    """Abstract base class for all LLM providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return a human-readable provider identifier (e.g., 'ollama')."""
        ...

    @abstractmethod
    async def generate(self, prompt: str, system_prompt: str = None) -> str:
        """
        Generate a natural-language response.

        Args:
            prompt: The user query / instruction.
            system_prompt: Optional system-level context (e.g., retrieved evidence).

        Returns:
            The generated text response.

        Raises:
            Exception on unrecoverable failure.
        """
        ...

    async def stream(self, prompt: str, system_prompt: str = None):
        """Yield the response in pieces as it is generated. Providers that cannot
        stream fall back to one piece, the whole answer."""
        yield await self.generate(prompt, system_prompt)

    @abstractmethod
    async def extract_query_parameters(self, query: str, allowed_intents: list[str]) -> dict:
        """
        Extract structured query parameters for the retrieval pipeline.

        Must return a dict with at minimum:
            - intent: str (one of allowed_intents, or 'unsupported_intent')
            - primary_person: Optional[str]
            - search_terms: list[str]

        Args:
            query: The raw user query.
            allowed_intents: List of valid intent strings.

        Returns:
            Structured extraction result dict.
        """
        ...

    @abstractmethod
    async def check_health(self) -> bool:
        """Return True if the provider is reachable and functional."""
        ...
