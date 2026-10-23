from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    log_level: str = "INFO"

    bot_token: SecretStr
    # Optional self-hosted Bot API server (e.g. to lift the 20 MB download limit).
    telegram_api_url: str | None = None
    # Comma separated Telegram user ids: ADMIN_IDS=111,222
    admin_ids: Annotated[frozenset[int], NoDecode] = frozenset()

    redis_url: str = "redis://redis:6379/0"

    api_base_url: str = "http://gateway:8081"
    service_token: SecretStr
    api_timeout: float = Field(default=15.0, gt=0)

    # Public HTTPS address of the catalog page opened as a Mini App.
    webapp_url: str

    # webhook: N stateless replicas behind the gateway (production).
    # polling: replicas elect a leader through Redis, only it talks to Telegram.
    bot_mode: Literal["webhook", "polling"] = "webhook"
    webhook_base_url: str = ""
    webhook_path: str = "/bot/webhook"
    webhook_secret: SecretStr = SecretStr("")

    server_host: str = "0.0.0.0"
    server_port: int = 8080

    max_photo_size_mb: int = Field(default=10, ge=1, le=20)

    @field_validator("admin_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, value: object) -> object:
        if isinstance(value, str):
            return frozenset(
                int(part) for part in value.replace(";", ",").split(",") if part.strip()
            )
        if isinstance(value, int):
            return frozenset({value})
        return value

    @field_validator("webapp_url", "webhook_base_url", "api_base_url")
    @classmethod
    def strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @model_validator(mode="after")
    def check_webhook_settings(self) -> "Settings":
        if self.bot_mode == "webhook":
            if not self.webhook_base_url.startswith("https://"):
                raise ValueError("WEBHOOK_BASE_URL must be an https:// URL in webhook mode")
            if len(self.webhook_secret.get_secret_value()) < 16:
                raise ValueError("WEBHOOK_SECRET must be at least 16 characters in webhook mode")
        return self

    @property
    def webhook_url(self) -> str:
        return f"{self.webhook_base_url}{self.webhook_path}"

    @property
    def max_photo_size_bytes(self) -> int:
        return self.max_photo_size_mb * 1024 * 1024

    def is_admin(self, user_id: int | None) -> bool:
        return user_id is not None and user_id in self.admin_ids


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
