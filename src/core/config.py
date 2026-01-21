"""Application configuration using Pydantic settings."""

import json
from pathlib import Path
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_path: str = "data/climate_startups.db"

    # Search indexes
    faiss_index_path: str = "data/faiss_index.bin"
    embeddings_path: str = "data/embeddings/all_embeddings.npy"
    id_mapping_path: str = "data/embeddings/startup_id_mapping.json"

    # API keys
    crunchbase_api_key: str = ""

    # CORS
    allowed_origins: str = "http://localhost:3000,http://localhost:5173"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

    # Embedding configuration
    embedding_model: str = "sentence-transformers/all-mpnet-base-v2"
    embedding_batch_size: int = 16
    embedding_dim: int = 768

    # Search configuration
    semantic_weight: float = 0.6
    default_top_k: int = 20
    max_results_per_vertical: int = 3

    # Rate limiting
    rate_limit_requests: int = 30
    rate_limit_window: int = 60

    # Cache
    cache_max_size: int = 1000
    cache_ttl_seconds: int = 3600

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @property
    def allowed_origins_list(self) -> List[str]:
        """Parse allowed origins string into a list."""
        return [origin.strip() for origin in self.allowed_origins.split(",")]

    @property
    def config_dir(self) -> Path:
        """Path to the config directory."""
        return Path(__file__).parent.parent.parent / "config"

    @property
    def data_dir(self) -> Path:
        """Path to the data directory."""
        return Path(__file__).parent.parent.parent / "data"

    def get_climate_taxonomy(self) -> dict:
        """Load climate taxonomy from JSON file."""
        taxonomy_path = self.config_dir / "climate_taxonomy.json"
        if taxonomy_path.exists():
            with open(taxonomy_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"verticals": [], "query_synonyms": {}}

    def get_test_queries(self) -> dict:
        """Load test queries from JSON file."""
        queries_path = self.config_dir / "test_queries.json"
        if queries_path.exists():
            with open(queries_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"test_queries": [], "evaluation_config": {}}


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
