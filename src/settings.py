from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="YOKERU_",
        extra="ignore",
    )

    fhir_base_url: str = Field(
        default="https://fhir-open.cerner.com/r4/ec2458f2-1e24-41c8-b71b-0e701af7583d",
        description="Base URL for the upstream EHR FHIR server.",
    )
    yokeru_api_url: str = Field(
        default="https://httpbin.org/post",
        description="Yokeru voice-agent dispatch endpoint. httpbin used as a public stand-in for the demo.",
    )
    db_path: str = Field(
        default="integration_state.db",
        description="Path to the local SQLite buffer.",
    )

    http_connect_timeout_s: float = 5.0
    http_read_timeout_s: float = 10.0

    retry_max_attempts: int = 3
    retry_min_wait_s: float = 2.0
    retry_max_wait_s: float = 10.0

    breaker_failure_threshold: int = 3
    breaker_reset_timeout_s: float = 4.0

    webhook_signing_secret: str = Field(
        default="dev-secret-change-me",
        description="Shared secret used to verify HMAC signatures on inbound webhooks.",
    )

    log_level: str = "INFO"
    log_format: str = "json"


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Test helper — drop the cached singleton so env changes take effect."""
    global _settings
    _settings = None
