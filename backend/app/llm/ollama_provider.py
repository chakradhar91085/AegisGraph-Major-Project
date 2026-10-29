"""
AegisGraph — Ollama LLM Provider (Qwen 2.5 Coder 7B).

Implements the BaseLLMProvider interface for local Ollama inference.
Uses async HTTP requests to the Ollama API with sensible timeouts.
"""
import logging
import json
import httpx
from app.llm.base_provider import BaseLLMProvider
from app.core.config import settings

logger = logging.getLogger(__name__)

# Ollama unloads an idle model after 5 minutes by default, and loading it again costs
# ~20 s on the next question. Keep it resident while the app is in use.
KEEP_ALIVE = "30m"


class OllamaProvider(BaseLLMProvider):
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = settings.OLLAMA_MODEL  # "qwen2.5-coder:7b"

    @property
    def provider_name(self) -> str:
        return "ollama"

    async def generate(self, prompt: str, system_prompt: str = None) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "keep_alive": KEEP_ALIVE,
        }

        async with httpx.AsyncClient(timeout=90.0) as client:
            try:
                response = await client.post(f"{self.base_url}/api/chat", json=payload)
                response.raise_for_status()
                data = response.json()
                return data.get("message", {}).get("content", "")
            except httpx.ConnectError:
                logger.error("Ollama service is not running or unreachable.")
                raise ConnectionError(
                    "Local Ollama service is unavailable. Start Ollama."
                )
            except httpx.TimeoutException:
                logger.error("Ollama request timed out after 90s.")
                raise TimeoutError(
                    "Local Ollama model timed out. The model may be loading or overloaded."
                )
            except Exception as e:
                logger.error(f"Ollama generation error: {e}")
                raise

    async def extract_query_parameters(self, query: str, allowed_intents: list[str]) -> dict:
        system_prompt = (
            "You are an information extraction engine for the AegisGraph Graph-RAG pipeline.\n"
            "Analyze the user's query and extract the following structured data:\n"
            "1. 'intent': Must be EXACTLY one of the following:\n"
            f"{allowed_intents}\n"
            "2. 'primary_person': The full name of the primary person the user is asking about (if any).\n"
            "3. 'search_terms': A list of possible name fragments or identifiers for the person to help search the database.\n\n"
            "### EXAMPLES ###\n"
            "Query: 'what emails in the system dicuss about the california energy crisis'\n"
            'Output: {"intent": "semantic_search", "primary_person": null, "search_terms": []}\n\n'
            "Query: 'find emails sent by John Smith'\n"
            'Output: {"intent": "sent_emails", "primary_person": "John Smith", "search_terms": ["John", "Smith"]}\n\n'
            "Query: 'who is communicating with Ken Lay?'\n"
            'Output: {"intent": "frequent_communication", "primary_person": "Ken Lay", "search_terms": ["Ken", "Lay"]}\n\n'
            "Query: 'what are the emails talking about gas prices?'\n"
            'Output: {"intent": "semantic_search", "primary_person": null, "search_terms": []}\n\n'
            "### END EXAMPLES ###\n\n"
            "Respond ONLY with a valid JSON object in this exact format:\n"
            '{"intent": "<value>", "primary_person": "<name>", "search_terms": ["<name>"]}\n'
            "If no person is identified, primary_person should be null and search_terms empty.\n"
            "Do not include any other text, explanation, or markdown formatting."
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ],
            "stream": False,
            "format": "json",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(f"{self.base_url}/api/chat", json=payload)
                response.raise_for_status()
                data = response.json()
                content = data.get("message", {}).get("content", "").strip()

                result = json.loads(content)

                intent_val = result.get("intent", "unsupported_intent")
                if intent_val not in allowed_intents:
                    logger.warning(f"Ollama returned invalid intent: {intent_val}")
                    result["intent"] = "unsupported_intent"

                if not isinstance(result.get("search_terms"), list):
                    result["search_terms"] = []

                return result
            except httpx.ConnectError:
                logger.error("Ollama service is not running for extraction.")
                return {"intent": "unsupported_intent", "search_terms": [], "primary_person": None}
            except Exception as e:
                logger.error(f"Ollama extraction error: {e}")
                return {"intent": "unsupported_intent", "search_terms": [], "primary_person": None}

    async def embed_query(self, query: str) -> list[float]:
        """Generate an embedding vector for semantic search using all-minilm."""
        payload = {
            "model": "all-minilm",
            "prompt": query
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(f"{self.base_url}/api/embeddings", json=payload)
                response.raise_for_status()
                data = response.json()
                return data.get("embedding", [])
            except Exception as e:
                logger.error(f"Ollama embedding error: {e}")
                return []

    async def check_health(self) -> bool:
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                response = await client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                return True
            except Exception:
                return False
