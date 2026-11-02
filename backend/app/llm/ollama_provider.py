"""The local answer model, served by Ollama."""
import json
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Ollama unloads an idle model after 5 minutes by default, and loading it again costs
# ~20 s on the next question. Keep it resident while the app is in use.
KEEP_ALIVE = "30m"


async def stream_answer(prompt: str, system_prompt: str):
    """Yield the answer in pieces as the model writes it."""
    payload = {
        "model": settings.OLLAMA_MODEL,
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
        "stream": True,
        "keep_alive": KEEP_ALIVE,
    }
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            async with client.stream("POST", f"{settings.OLLAMA_BASE_URL}/api/chat", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    chunk = json.loads(line)
                    if text := chunk.get("message", {}).get("content", ""):
                        yield text
                    if chunk.get("done"):
                        break
    except httpx.ConnectError:
        logger.error("Ollama service is not running or unreachable.")
        raise ConnectionError("Local Ollama service is unavailable. Start Ollama.")
    except httpx.TimeoutException:
        logger.error("Ollama stream timed out.")
        raise TimeoutError("Local Ollama model timed out. The model may be loading or overloaded.")
