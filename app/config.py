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



settings = Settings()