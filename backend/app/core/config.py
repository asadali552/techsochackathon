from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.schemas.heatmap import CellSize

ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_ENV, env_ignore_empty=True, extra="ignore")

    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    supabase_service_role_key: SecretStr | None = None
    database_url: SecretStr | None = None
    llm_provider: str | None = None
    llm_api_key: SecretStr | None = None
    llm_model: str | None = None
    llm_base_url: str | None = None
    llm_timeout_seconds: float = Field(default=8, ge=1, le=15)
    llm_moderator_ids: frozenset[UUID] = frozenset()
    gemini_api_key: SecretStr | None = None
    gemini_model: str = Field(default="gemini-3.5-flash-lite", pattern=r"^gemini-[A-Za-z0-9]+(?:[.-][A-Za-z0-9]+)*$")
    assistant_gemini_in_demo: bool = False
    assistant_timeout_seconds: float = Field(default=5, ge=1, le=12)
    assistant_max_output_tokens: int = Field(default=650, ge=200, le=1500)
    geocoding_service_url: str | None = None
    routing_service_url: str | None = None
    heatmap_timezone: str = "Asia/Karachi"
    heatmap_cell_size: CellSize = 750
    heatmap_min_reports: int = Field(default=2, ge=2, le=20)
    heatmap_moderate_threshold: int = Field(default=25, ge=1, lt=100)
    heatmap_elevated_threshold: int = Field(default=60, ge=2, le=100)

    @field_validator("cors_origins")
    @classmethod
    def validate_origins(cls, origins: list[str]) -> list[str]:
        for origin in origins:
            url = urlsplit(origin)
            if (url.scheme not in {"http", "https"} or not url.hostname or url.username is not None or url.password is not None
                    or "*" in origin or any(character.isspace() for character in origin)
                    or origin != f"{url.scheme}://{url.netloc}"):
                raise ValueError("CORS origins must be exact HTTP(S) origins without a path or wildcard")
            _ = url.port
        return origins

    @field_validator("heatmap_timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Use an IANA time zone") from exc
        return value

    @field_validator("heatmap_cell_size", mode="before")
    @classmethod
    def read_cell_size(cls, value: object) -> object:
        if isinstance(value, str) and value.isdecimal():
            return int(value)
        return value

    @model_validator(mode="after")
    def validate_thresholds(self) -> "Settings":
        if self.heatmap_moderate_threshold >= self.heatmap_elevated_threshold:
            raise ValueError("The elevated heatmap threshold must exceed the moderate threshold")
        return self


settings = Settings()


def get_settings() -> Settings:
    return settings
