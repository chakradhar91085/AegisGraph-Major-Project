import asyncio
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.api.audit import router as audit_router
from app.core.config import settings
from app.db.postgres import init_db
from app.llm.ollama_provider import KEEP_ALIVE
from app.retrieval import mcp_agent
from app.security.embeddings import embedding_provider

logger = logging.getLogger(__name__)

async def _warm_up() -> None:
    """Load the slow-to-start parts now, so the first question is not the slow one:
    the local answer model (into the GPU), the Neo4j MCP server + graph schema, and
    the embedding model the risk engine uses."""
    async def ollama():
        async with httpx.AsyncClient(timeout=120) as client:
            await client.post(f"{settings.OLLAMA_BASE_URL}/api/generate",
                              json={"model": settings.OLLAMA_MODEL, "keep_alive": KEEP_ALIVE})

    jobs = [("Ollama model", ollama()), ("embedding model", embedding_provider.get_embedding("warm up")),
            ("Neo4j MCP server", mcp_agent.neo4j_mcp.schema())]
    for (name, _), result in zip(jobs, await asyncio.gather(*(j for _, j in jobs), return_exceptions=True)):
        logger.info(f"Warm-up {name}: {'failed: ' + repr(result) if isinstance(result, Exception) else 'ready'}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables on startup
    await init_db()
    warm = asyncio.create_task(_warm_up())  # background: startup does not wait for it
    yield
    warm.cancel()

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router, prefix=settings.API_V1_STR, tags=["chat"])
app.include_router(audit_router, prefix=settings.API_V1_STR, tags=["audit"])
