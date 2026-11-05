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

    # The local model that writes every answer (Ollama)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1:8b"

    # The agent's LLM, which writes read-only Cypher through the Neo4j MCP server.
    # NVIDIA build.nvidia.com, ~40 requests/min free.
    AGENT_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    AGENT_API_KEY: str = ""
    AGENT_MODEL: str = "nvidia/nemotron-3-ultra-550b-a55b"
    AGENT_MAX_STEPS: int = 4
    # Read-only Neo4j login (role "reader") the MCP server connects with.
    NEO4J_READER_USERNAME: str = ""
    NEO4J_READER_PASSWORD: str = ""

    # Context Builder Settings
    MAX_RECORDS: int = 20
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
    # Comma-separated "clerk_user_id:Display Name" pairs, shown in the admin pages
    # instead of the raw id (e.g. user_3Jz...:Admin).
    SECURITY_USER_NAMES: str = ""
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
    # Slack incoming-webhook URL (secret: anyone holding it can post to the channel).
    SLACK_WEBHOOK_URL: str = ""

    # Security & Telemetry Settings
    # Server-only secret used to sign session tickets (required: set in .env).
    SECURITY_SESSION_SECRET: str
    # A user's remembered risk halves after this many idle seconds.
    SECURITY_RISK_HALF_LIFE_SECONDS: float = 900.0

    # Research-aligned semantic drift model
    SECURITY_EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    # Number of recent queries (including the current one) considered when
    # computing the semantic-focus signal (paper Eq. 1's sliding window W).
    SECURITY_SEMANTIC_WINDOW_SIZE: int = 5
    # Queries further back than this no longer count towards behaviour signals.
    SECURITY_TEMPORAL_WINDOW_SECONDS: int = 900
    # Cosine similarity at or below FLOOR is unrelated (0); at or above CEIL it is repetition (1).
    SECURITY_SEMANTIC_FLOOR: float = 0.3
    SECURITY_SEMANTIC_CEIL: float = 0.8
    # Earlier queries inside RATE_WINDOW; RATE_MAX of them gives a full rate signal.
    SECURITY_RATE_WINDOW_SECONDS: int = 300
    SECURITY_RATE_MAX: int = 20
    # This many separate queries touching one person gives full entity focus.
    SECURITY_ENTITY_MAX_QUERIES: int = 5
    SECURITY_GRAPH_MAX_DEPTH: int = 5
    SECURITY_GRAPH_MAX_NODES: int = 50

    # How far each signal alone can push risk (0-1), combined by noisy-OR in risk.py.
    # ponytail: hand-set; fit these on a labelled session set once one exists.
    SECURITY_WEIGHT_SEMANTIC: float = 0.35
    SECURITY_WEIGHT_TEMPORAL: float = 0.35
    SECURITY_WEIGHT_ENTITY: float = 0.45
    SECURITY_WEIGHT_GRAPH: float = 0.35
    SECURITY_WEIGHT_SENSITIVITY: float = 0.60

    # Sensitivity exposure (5th signal): sensitive data a user has pulled, fading with
    # this half-life; the signal reaches ~63% once SCALE units have been pulled
    # (one unit = one fully sensitive email about a top executive).
    SECURITY_SENSITIVITY_HALF_LIFE_SECONDS: float = 900.0
    SECURITY_SENSITIVITY_SCALE: float = 3.0
    # Sensitive data a user may receive before risk is floored at Block: Mask starts at 35% of
    # this, Block at 65%. Roughly 15 and 30 sensitive emails for ordinary senders.
    # ponytail: hand-set; calibrate with labelled sessions. Lost on restart, like all risk memory.
    SECURITY_RATCHET_BUDGET: float = 20.0
    SECURITY_RATCHET_WINDOW_SECONDS: int = 86400
    # "How many" questions a user may ask per window.
    SECURITY_COUNT_BUDGET: int = 10
    SECURITY_COUNT_WINDOW_SECONDS: int = 3600
    
    # Risk rises quickly and falls slowly, so innocent queries cannot hide probing.
    SECURITY_EWMA_RISE: float = 0.6
    SECURITY_EWMA_FALL: float = 0.2
    
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
