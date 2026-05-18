"""Application configuration

"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class InfraSettings(BaseSettings):
    """Infrastructure connection settings.

    Attributes:
        DATABASE_URL: PostgreSQL async connection string.
        CHROMA_HOST: ChromaDB server hostname.
        CHROMA_PORT: ChromaDB server port.
        REDIS_URL: Redis connection URL with password.
        REDIS_CONNECT_TIMEOUT: Redis socket connection timeout in seconds.
        REDIS_SOCKET_TIMEOUT: Redis socket read/write timeout in seconds.
        API_HOST: Host to bind the API server.
        API_PORT: Port to bind the API server.
        UPLOAD_DIR: Local directory for uploaded files.
        CORS_ORIGINS: List of allowed origins for CORS.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8000
    CHROMA_COLLECTION: str = "documents"
    REDIS_URL: str
    REDIS_CONNECT_TIMEOUT: float = 2.0
    REDIS_SOCKET_TIMEOUT: float = 2.0
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8080
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_BYTES: int = 26214400  # 25 MB
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]


class LLMSettings(BaseSettings):
    """LLM and embedding model settings.

    Attributes:
        EMBEDDING_MODEL: LiteLLM model identifier for embeddings.
        EMBEDDING_DIMENSIONS: Dimensionality of the embedding vectors.
    """

    model_config = SettingsConfigDict(
        env_prefix="LLM_", env_file=".env", extra="ignore"
    )

    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS: int = 1536


class SearchSettings(BaseSettings):
    """Search pipeline tuning parameters.

    Attributes:
        DEFAULT_TOP_K: Default number of results to return.
        RRF_K: Reciprocal Rank Fusion k parameter.
        RERANK_TOP_N: Number of candidates to pass to the reranker.
        CACHE_TTL_SECONDS: Redis cache TTL in seconds.
    """

    model_config = SettingsConfigDict(
        env_prefix="SEARCH_", env_file=".env", extra="ignore"
    )

    DEFAULT_TOP_K: int = 10
    RRF_K: int = 60
    RERANK_TOP_N: int = 20
    CACHE_TTL_SECONDS: int = 300
    CHUNK_SIZE: int = 1500
    CHUNK_OVERLAP: int = 190


infra_settings = InfraSettings()
llm_settings = LLMSettings()
search_settings = SearchSettings()
