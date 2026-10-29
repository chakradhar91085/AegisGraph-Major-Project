"""
AegisGraph — OpenRouter LLM Provider.

OpenAI-compatible chat completions over HTTPS. Used when no local Ollama is available.
"""
import json
import logging
import httpx
from app.llm.base_provider import BaseLLMProvider
from app.core.config import settings

logger = logging.getLogger(__name__)


class OpenRouterProvider(BaseLLMProvider):
    def __init__(self):
        if not settings.OPENROUTER_API_KEY:
            raise RuntimeError("OPENROUTER_API_KEY is not set")
        self.base_url = settings.OPENROUTER_BASE_URL.rstrip("/")
        self.model = settings.OPENROUTER_MODEL
        self.headers = {"Authorization": f"Bearer {settings.OPENROUTER_API_KEY}"}

    @property
    def provider_name(self) -> str:
        return "openrouter"

    async def _chat(self, messages: list[dict], timeout: float, json_mode: bool = False) -> str:
        payload = {"model": self.model, "messages": messages, "stream": False,
                   "reasoning": {"enabled": False}}  # skip thinking tokens: faster, cheaper
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions", json=payload, headers=self.headers
            )
            response.raise_for_status()
            data = response.json()
            return (data["choices"][0]["message"].get("content") or "").strip()

    async def generate(self, prompt: str, system_prompt: str = None) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        try:
            return await self._chat(messages, timeout=90.0)
        except httpx.TimeoutException:
            logger.error("OpenRouter request timed out after 90s.")
            raise TimeoutError("LLM request timed out.")
        except Exception as e:
            logger.error(f"OpenRouter generation error: {e}")
            raise

    async def stream(self, prompt: str, system_prompt: str = None):
        messages = ([{"role": "system", "content": system_prompt}] if system_prompt else []) + [
            {"role": "user", "content": prompt}]
        payload = {"model": self.model, "messages": messages, "stream": True, "reasoning": {"enabled": False}}
        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                async with client.stream("POST", f"{self.base_url}/chat/completions", json=payload,
                                         headers=self.headers) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue  # SSE comments / keep-alives
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        choices = json.loads(data).get("choices") or []
                        if choices and (text := (choices[0].get("delta") or {}).get("content")):
                            yield text
        except httpx.TimeoutException:
            logger.error("OpenRouter stream timed out.")
            raise TimeoutError("LLM request timed out.")

    async def extract_query_parameters(self, query: str, allowed_intents: list[str]) -> dict:
        system_prompt = (
            "You are an information extraction engine for the AegisGraph Graph-RAG pipeline.\n"
            "Analyze the user's query and extract the following structured data:\n"
            "1. 'intent': Must be EXACTLY one of the following:\n"
            f"{allowed_intents}\n"
            "2. 'primary_person': The full name of the primary person the user is asking about (if any).\n"
            "3. 'search_terms': A list of possible name fragments or identifiers for the person.\n\n"
            "### EXAMPLES ###\n"
            "Query: 'what emails in the system dicuss about the california energy crisis'\n"
            'Output: {"intent": "semantic_search", "primary_person": null, "search_terms": []}\n\n'
            "Query: 'find emails sent by John Smith'\n"
            'Output: {"intent": "sent_emails", "primary_person": "John Smith", "search_terms": ["John", "Smith"]}\n\n'
            "Query: 'who is communicating with Ken Lay?'\n"
            'Output: {"intent": "frequent_communication", "primary_person": "Ken Lay", "search_terms": ["Ken", "Lay"]}\n\n'
            "### END EXAMPLES ###\n\n"
            "Respond ONLY with a valid JSON object in this exact format:\n"
            '{"intent": "<value>", "primary_person": "<name>", "search_terms": ["<name>"]}\n'
            "If no person is identified, primary_person should be null and search_terms empty.\n"
            "Do not include any other text, explanation, or markdown formatting."
        )
        fallback = {"intent": "unsupported_intent", "search_terms": [], "primary_person": None}
        try:
            content = await self._chat(
                [{"role": "system", "content": system_prompt}, {"role": "user", "content": query}],
                timeout=30.0,
                json_mode=True,
            )
            start, end = content.find("{"), content.rfind("}")
            result = json.loads(content[start:end + 1])
            if result.get("intent") not in allowed_intents:
                logger.warning(f"OpenRouter returned invalid intent: {result.get('intent')}")
                result["intent"] = "unsupported_intent"
            if not isinstance(result.get("search_terms"), list):
                result["search_terms"] = []
            return result
        except Exception as e:
            logger.error(f"OpenRouter extraction error: {e}")
            return fallback

    async def check_health(self) -> bool:
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                r = await client.get(f"{self.base_url}/key", headers=self.headers)
                r.raise_for_status()
                return True
            except Exception:
                return False
