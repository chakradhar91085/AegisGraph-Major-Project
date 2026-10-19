"""
AegisGraph — LLM Provider Factory.

Returns the correct provider singleton by name.
Providers are instantiated lazily on first request and cached.
"""
import logging
from app.llm.base_provider import BaseLLMProvider
from app.core.config import settings

logger = logging.getLogger(__name__)

# Lazy singletons
_providers: dict[str, BaseLLMProvider] = {}


SUPPORTED_PROVIDERS = ("ollama", "openrouter")


def resolve_provider_name(provider_name: str | None = None) -> str:
    """The requested provider if valid, else the configured default (ollama unless changed)."""
    name = (provider_name or "").lower()
    if name in SUPPORTED_PROVIDERS:
        return name
    default = settings.LLM_PROVIDER.lower()
    return default if default in SUPPORTED_PROVIDERS else "ollama"


def provider_available(name: str) -> bool:
    """OpenRouter needs an API key; Ollama is assumed reachable (see /health/llm)."""
    return name != "openrouter" or bool(settings.OPENROUTER_API_KEY)


def get_llm_provider(provider_name: str | None = None) -> BaseLLMProvider:
    """
    Return the LLM provider singleton: the one requested per call ("ollama" or
    "openrouter"), otherwise settings.LLM_PROVIDER, which defaults to ollama.
    """
    name = resolve_provider_name(provider_name)

    if name not in _providers:
        if name == "openrouter":
            from app.llm.openrouter_provider import OpenRouterProvider
            _providers[name] = OpenRouterProvider()
            logger.info(f"Initialized OpenRouterProvider ({settings.OPENROUTER_MODEL})")
        else:
            from app.llm.ollama_provider import OllamaProvider
            _providers[name] = OllamaProvider()
            logger.info(f"Initialized OllamaProvider ({settings.OLLAMA_MODEL})")

    return _providers[name]
