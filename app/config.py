from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    openai_api_key: str

    # Embedding config
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    # Chunking config
    chunk_size: int = 512
    chunk_overlap: int = 50

    # Retrieval config
    retrieval_top_k: int = 5

    # Chat model
    chat_model: str = "gpt-4o-mini"

    # Memory config
    memory_max_tokens: int = 2000        # Max tokens for conversation history
    context_max_tokens: int = 3000       # Max tokens for retrieved chunks

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Tell Pydantic to load .env as the env file. replaces load_dotenv()
    model_config = {"env_file": ".env"}

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

    # Agent / tools
    tavily_api_key: str = ""
    e2b_api_key: str = ""
    agent_max_iterations: int = 10

    # Memory extraction
    memory_extraction_model: str = "gpt-4o-mini"
    memory_retrieval_top_k: int = 5
    memory_core_always_inject: int = 10
    memory_extraction_delay: int = 60


settings = Settings()