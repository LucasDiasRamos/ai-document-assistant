from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Document Assistant"
    app_environment: Literal["development", "production"] = "development"
    cors_allowed_origins: list[str] = Field(default_factory=list)
    chat_requests_per_minute: int = Field(default=20, gt=0)
    upload_requests_per_minute: int = Field(default=5, gt=0)
    rate_limit_window_seconds: int = Field(default=60, gt=0)
    database_url: str
    storage_root: Path = Path("../storage")
    max_upload_size_bytes: int = Field(default=10 * 1024 * 1024, gt=0)
    chunk_size: int = Field(default=800, gt=0)
    chunk_overlap: int = Field(default=120, ge=0)
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"
    embedding_timeout_seconds: float = Field(default=30.0, gt=0)
    retrieval_top_k: int = Field(default=5, ge=1, le=20)
    retrieval_min_similarity: float = Field(default=0.70, ge=0.0, le=1.0)
    llm_provider: str = "openai"
    llm_model: str
    llm_timeout_seconds: float = Field(default=60.0, gt=0)
    openai_api_key: SecretStr | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @model_validator(mode="after")
    def validate_chunk_window(self) -> "Settings":
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE")
        if not self.llm_model.strip():
            raise ValueError("LLM_MODEL must not be empty")
        for origin in self.cors_allowed_origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
                or "*" in origin
            ):
                raise ValueError(
                    "CORS_ALLOWED_ORIGINS must contain exact HTTP(S) origins"
                )
            if self.app_environment == "production" and parsed.scheme != "https":
                raise ValueError("Production CORS origins must use HTTPS")

        if self.app_environment == "production" and not self.cors_allowed_origins:
            raise ValueError(
                "Production requires explicit CORS_ALLOWED_ORIGINS"
            )
        return self


settings = Settings()
