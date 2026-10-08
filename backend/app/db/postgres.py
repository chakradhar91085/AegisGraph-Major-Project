from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from app.core.config import settings

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True
)

# Create sessionmaker
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

# Declarative base for models
Base = declarative_base()

async def get_db() -> AsyncSession:
    """Dependency for FastAPI endpoints if needed."""
    async with AsyncSessionLocal() as session:
        yield session

async def init_db():
    """Create tables if they don't exist, and widen existing ones for new columns."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for table, column, coltype in [
            ("audit_queries", "instantaneous_risk", "FLOAT"),
            ("audit_queries", "signals", "JSON"),
            ("audit_queries", "policy", "JSON"),
            ("audit_queries", "user_id", "VARCHAR"),
            ("audit_queries", "user_email", "VARCHAR"),
            ("audit_sessions", "user_id", "VARCHAR"),
            ("audit_sessions", "user_email", "VARCHAR"),
        ]:
            await conn.execute(text(
                f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {coltype}"
            ))
