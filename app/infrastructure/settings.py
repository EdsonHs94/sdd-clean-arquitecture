"""Runtime settings at the outer boundary, with secret-safe representations."""

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    database_url: SecretStr
    jwt_secret: SecretStr
    s3_bucket: str = Field(min_length=1)
    jwt_issuer: str = Field(default="user-architecture-model", min_length=1)
    jwt_audience: str = Field(default="user-architecture-model-api", min_length=1)
    aws_region: str = "us-east-1"
    s3_endpoint_url: str | None = None

    @field_validator("database_url")
    @classmethod
    def require_postgresql(cls, value: SecretStr) -> SecretStr:
        try:
            url = make_url(value.get_secret_value())
        except ArgumentError:
            raise ValueError("Invalid database URL") from None
        if url.drivername != "postgresql+asyncpg" or not url.database:
            raise ValueError("Database URL must use postgresql+asyncpg")
        return value

    @field_validator("jwt_secret")
    @classmethod
    def require_signing_secret(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value().encode()) < 32:
            raise ValueError("Signing secret must contain at least 32 bytes")
        return value

    @field_validator("s3_bucket", "jwt_issuer", "jwt_audience")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Value must be nonempty")
        return value

    @field_validator("s3_endpoint_url", mode="before")
    @classmethod
    def empty_endpoint_is_absent(cls, value):
        return None if value == "" else value
