from pydantic_settings import BaseSettings

# Origins allowed by CORSMiddleware. Referenced here so errors.py can add
# CORS headers to 500 responses without duplicating the list.
CORS_ORIGINS = [
    "http://localhost:3000",
    "https://podium-beta.vercel.app",
    "http://localhost:8000",
]

# Models available for selection. Provider drives which BYOK key is used.
AVAILABLE_MODELS: list[dict] = [
    {"id": "gpt-5-nano",        "label": "GPT-5 nano · fast",         "provider": "openai"},
    {"id": "gpt-5.4-nano",      "label": "GPT-5.4 nano · capable",    "provider": "openai"},
    {"id": "claude-sonnet-4-6", "label": "Claude Sonnet 4.6 · smart", "provider": "anthropic"},
    {"id": "claude-haiku-4-5",  "label": "Claude Haiku 4.5 · fast",   "provider": "anthropic"},
    # Ollama entries — always in config; filtered in list_models() when OLLAMA_BASE_URL unset
    {"id": "ollama/llama3.2",   "label": "Llama 3.2 (local)",         "provider": "ollama"},
    {"id": "ollama/mistral",    "label": "Mistral (local)",            "provider": "ollama"},
    {"id": "ollama/codellama",  "label": "Code Llama (local)",         "provider": "ollama"},
]

# Per-model capability flags. Models not listed default to tools=True.
MODEL_CAPABILITIES: dict[str, dict] = {
    "ollama/llama3.2": {"tools": False},
    "ollama/mistral": {"tools": False},
    "ollama/codellama": {"tools": False},
}


def provider_for_model(model_id: str) -> str:
    """Infer the provider from a model ID."""
    for m in AVAILABLE_MODELS:
        if m["id"] == model_id:
            return m["provider"]
    if model_id.startswith("claude"):
        return "anthropic"
    if model_id.startswith("ollama/"):
        return "ollama"
    return "openai"


def model_supports_tools(model_id: str) -> bool:
    return MODEL_CAPABILITIES.get(model_id, {}).get("tools", True)


class Settings(BaseSettings):
    database_url: str
    openai_api_key: str

    # Embedding
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    # Chunking
    chunk_size: int = 512
    chunk_overlap: int = 50

    # Retrieval
    retrieval_top_k: int = 5

    # Models
    chat_model: str = "gpt-5-nano"

    # Conversation history token budget
    memory_max_tokens: int = 2000
    context_max_tokens: int = 3000

    # Redis
    redis_url: str = "redis://localhost:6379"

    # S3 — empty means use local filesystem (dev mode)
    s3_bucket_name: str = ""
    aws_default_region: str = "us-east-1"

    # Auth (Clerk)
    clerk_secret_key: str = ""
    clerk_jwks_url: str = ""

    # KMS
    kms_key_id: str = ""

    # Rate limiting
    rate_limit_chat: str = "30/minute"
    rate_limit_chat_stream: str = "5/minute"
    rate_limit_read: str = "60/minute"

    # Guest sessions
    guest_jwt_secret: str = ""  # Required in prod. Generate: openssl rand -hex 32
    guest_session_duration_hours: int = 24
    guest_max_messages_per_session: int = 20

    # Demo seed corpus — documents visible to all guests
    seed_user_id: str = "demo_seed"

    # Agent / tools
    tavily_api_key: str = ""
    e2b_api_key: str = ""
    agent_max_iterations: int = 10

    # Memory extraction
    memory_extraction_model: str = "gpt-4o-mini"
    memory_retrieval_top_k: int = 5
    memory_core_always_inject: int = 10
    memory_extraction_delay: int = 60

    # Ollama — local/dev models; empty string = Ollama disabled
    ollama_base_url: str = ""  # e.g. http://localhost:11434

    model_config = {"env_file": ".env"}


settings = Settings()
