from fastapi import FastAPI
from app.api.health import router as health_router
from app.api.chat import router as chat_router
from app.api.audit import router as audit_router
from app.core.config import settings

from fastapi.middleware.cors import CORSMiddleware

import logging
from contextlib import asynccontextmanager
from app.db.postgres import init_db
import os
if os.getenv("USE_POSTGRES_RETRIEVAL", "false").lower() == "true":
    from app.retrieval.postgres_strategies import postgres_retrieval_strategies as retrieval_strategies
else:
    from app.retrieval.strategies import retrieval_strategies

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables on startup
    await init_db()
    try:
        await retrieval_strategies.ensure_person_fuzzy_index()
    except Exception as e:
        logger.warning(f"Could not ensure Neo4j fuzzy name index (is Neo4j running?): {e}")
    yield

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

# Include routers
app.include_router(health_router, prefix=settings.API_V1_STR, tags=["health"])
app.include_router(chat_router, prefix=settings.API_V1_STR, tags=["chat"])
app.include_router(audit_router, prefix=settings.API_V1_STR, tags=["audit"])

@app.get("/")
async def root():
    return {"message": "Welcome to AegisGraph API"}
