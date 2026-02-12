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

    model_config = {"env_file": ".env"}


settings = Settings()