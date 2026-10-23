from functools import lru_cache

from pydantic import Field, PostgresDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "catalog-api"
    environment: str = "production"
    log_level: str = "INFO"

    database_url: PostgresDsn | str
    db_pool_size: int = Field(default=10, ge=1)
    db_max_overflow: int = Field(default=10, ge=0)
    db_pool_timeout: float = Field(default=10.0, gt=0)

    s3_endpoint_url: str
    s3_access_key: SecretStr
    s3_secret_key: SecretStr
    s3_bucket: str = "products"
    s3_region: str = "us-east-1"

    # Base URL the browser uses to load images. Relative by default because the
    # gateway serves the bucket under /media on the same origin as the catalog.
    media_public_url: str = "/media"

    # Shared secret for service-to-service calls (bot -> api) on write endpoints.
    service_token: SecretStr

    max_image_size_mb: int = Field(default=10, ge=1, le=50)
    max_image_pixels: int = Field(default=40_000_000, ge=1)

    page_size_default: int = Field(default=20, ge=1)
    page_size_max: int = Field(default=100, ge=1)

    @property
    def max_image_size_bytes(self) -> int:
        return self.max_image_size_mb * 1024 * 1024

    @property
    def database_dsn(self) -> str:
        return str(self.database_url)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
