from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "AegisGraph"
    API_V1_STR: str = "/api/v1"

    # Comma-separated list of allowed frontend origins for CORS.
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Neo4j Settings
    NEO4J_URI: str
    NEO4J_USERNAME: str
    NEO4J_PASSWORD: str
    NEO4J_DATABASE: str = "aegisgraph"

    # LLM Settings
    LLM_PROVIDER: str = "ollama"
    
    # Ollama Settings
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1:8b"

    # OpenRouter Settings (used when LLM_PROVIDER=openrouter)
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = "qwen/qwen3.7-flash"

    # Context Builder Settings
    MAX_RECORDS: int = 20
    MAX_CHUNK_CHARS: int = 1500
    MAX_CONTEXT_CHARS: int = 8000

    # Postgres Configuration (required: set in .env, never hardcode credentials)
    DATABASE_URL: str

    # Authentication: the frontend signs users in with Clerk; the backend
    # verifies the Clerk session token. CLERK_ISSUER is the Clerk "Frontend API
    # URL", e.g. https://primary-cow-3262.clerk.accounts.dev
    CLERK_ISSUER: str = ""
    # Comma-separated "clerk_user_id:Role" pairs (Role = Auditor | Analyst | Standard).
    # Any signed-in user not listed here is "Standard". Auditor is also the admin role.
    SECURITY_USER_ROLES: str = ""
    # Demo convenience: lets a signed-in user reset their own remembered risk
    # (the "New Session" button). Keep False outside local demos.
    DEMO_ALLOW_RISK_RESET: bool = False

    # Admin security alerts. A channel is off while its settings are blank.
    # Telegram: token from @BotFather; chat id of the admin's chat with the bot.
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    # Email via SMTP (Gmail: an App Password, not the account password).
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    ALERT_EMAIL_TO: str = ""

    # Security & Telemetry Settings
    # Server-only secret used to sign session tickets (required: set in .env).
    SECURITY_SESSION_SECRET: str
    # A user's remembered risk halves after this many idle seconds.
    SECURITY_RISK_HALF_LIFE_SECONDS: float = 300.0

    # Research-aligned semantic drift model
    SECURITY_EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    # Number of recent queries (including the current one) considered when
    # computing the semantic-focus signal (paper Eq. 1's sliding window W).
    SECURITY_SEMANTIC_WINDOW_SIZE: int = 5
    SECURITY_TEMPORAL_WINDOW_SECONDS: int = 60
    SECURITY_ALPHA_TEMP: float = 0.05
    SECURITY_TEMPORAL_THRESHOLD: int = 5
    SECURITY_GRAPH_MAX_DEPTH: int = 5
    SECURITY_GRAPH_MAX_NODES: int = 50
    SECURITY_GRAPH_WEIGHT: float = 0.5
    
    # Risk Fusion Weights (alpha, beta, gamma, delta)
    SECURITY_WEIGHT_SEMANTIC: float = 0.25
    SECURITY_WEIGHT_TEMPORAL: float = 0.25
    SECURITY_WEIGHT_ENTITY: float = 0.25
    SECURITY_WEIGHT_GRAPH: float = 0.25
    
    SECURITY_EWMA_LAMBDA: float = 0.4
    
    # Adaptive Response Policy Parameters
    SECURITY_THETA_MID: float = 0.55
    SECURITY_THETA_SLOPE: float = 10.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()
