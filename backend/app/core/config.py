"""Application Configuration.

Centralized configuration using Pydantic Settings for type safety and validation.
"""

import os
from typing import Any

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "Global Credit Core"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = Field(default="development", env="ENVIRONMENT")
    DEBUG: bool = Field(default=True, env="DEBUG")

    # API
    API_V1_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: str = Field(
        default="postgresql://credit_user:credit_pass@localhost:5432/credit_db",
        env="DATABASE_URL"
    )

    # Redis
    REDIS_URL: str = Field(
        default="redis://localhost:6379",
        env="REDIS_URL"
    )

    # JWT Security
    JWT_SECRET: str = Field(
        default="dev-jwt-secret-key-change-in-production-min-32-chars",
        env="JWT_SECRET",
        description="JWT secret key for token signing. Must be set via environment variable in production."
    )
    JWT_ALGORITHM: str = Field(default="HS256", env="JWT_ALGORITHM")
    JWT_EXPIRATION_MINUTES: int = Field(default=60, env="JWT_EXPIRATION_MINUTES")

    # Webhook Security
    WEBHOOK_SECRET: str = Field(
        default="dev-webhook-secret-key-change-in-production-min-32-chars",
        env="WEBHOOK_SECRET",
        description="Webhook secret for signature verification. Must be set via environment variable in production."
    )

    # PII Encryption (pgcrypto)
    ENCRYPTION_KEY: str = Field(
        default="dev-encryption-key-change-in-production-min-32-chars-for-pgcrypto",
        env="ENCRYPTION_KEY",
        description="Encryption key for pgcrypto PII encryption at rest. Must be set via environment variable in production."
    )

    # CORS
    CORS_ORIGINS: list = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://frontend:5173"
    ]

    # Logging
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")

    # Distributed Tracing
    TRACING_ENABLED: bool = Field(
        default=False,
        env="TRACING_ENABLED",
        description="Enable distributed tracing with OpenTelemetry"
    )
    TRACING_EXPORTER: str = Field(
        default="console",
        env="TRACING_EXPORTER",
        description="Tracing exporter: 'console' for development, 'otlp' for production"
    )
    TRACING_OTLP_ENDPOINT: str = Field(
        default="http://localhost:4318/v1/traces",
        env="TRACING_OTLP_ENDPOINT",
        description="OTLP endpoint for trace export (Jaeger, Zipkin, etc.)"
    )

    # Security - Payload size limits
    MAX_PAYLOAD_SIZE_MB: int = Field(
        default=2,
        env="MAX_PAYLOAD_SIZE_MB",
        description="Maximum request payload size in MB to prevent DoS attacks"
    )

    @model_validator(mode='before')
    @classmethod
    def handle_empty_secrets(cls, data: Any) -> Any:
        """Handle empty string environment variables by using defaults in development and test."""
        if isinstance(data, dict):
            environment = data.get('ENVIRONMENT', os.environ.get('ENVIRONMENT', 'development'))

            jwt_secret_default = "dev-jwt-secret-key-change-in-production-min-32-chars"
            webhook_secret_default = "dev-webhook-secret-key-change-in-production-min-32-chars"
            encryption_key_default = "dev-encryption-key-change-in-production-min-32-chars-for-pgcrypto"

            is_non_production = environment in ('development', 'test')

            if 'JWT_SECRET' in data and data['JWT_SECRET'] == '':
                if is_non_production:
                    data['JWT_SECRET'] = jwt_secret_default

            if 'WEBHOOK_SECRET' in data and data['WEBHOOK_SECRET'] == '':
                if is_non_production:
                    data['WEBHOOK_SECRET'] = webhook_secret_default

            if 'ENCRYPTION_KEY' in data and data['ENCRYPTION_KEY'] == '':
                if is_non_production:
                    data['ENCRYPTION_KEY'] = encryption_key_default

        return data

    @field_validator('JWT_SECRET', mode='after')
    @classmethod
    def validate_jwt_secret(cls, v, info):
        """Validate JWT_SECRET meets security requirements."""
        if not v:
            raise ValueError(
                "JWT_SECRET must be set via environment variable. "
                "It cannot be empty for security reasons."
            )

        environment = info.data.get('ENVIRONMENT', 'development')

        if environment == 'production' and len(v) < 32:
            raise ValueError(
                "JWT_SECRET must be at least 32 characters long in production for security."
            )

        return v

    @field_validator('WEBHOOK_SECRET', mode='after')
    @classmethod
    def validate_webhook_secret(cls, v, info):
        """Validate WEBHOOK_SECRET meets security requirements."""
        if not v:
            raise ValueError(
                "WEBHOOK_SECRET must be set via environment variable. "
                "It cannot be empty for security reasons."
            )

        environment = info.data.get('ENVIRONMENT', os.environ.get('ENVIRONMENT', 'development'))

        if environment == 'production' and len(v) < 32:
            raise ValueError(
                "WEBHOOK_SECRET must be at least 32 characters long in production for security."
            )

        return v

    @field_validator('ENCRYPTION_KEY', mode='after')
    @classmethod
    def validate_encryption_key(cls, v, info):
        """Validate ENCRYPTION_KEY meets security requirements."""
        if not v:
            raise ValueError(
                "ENCRYPTION_KEY must be set via environment variable. "
                "It cannot be empty for security reasons."
            )

        environment = info.data.get('ENVIRONMENT', 'development')

        if environment == 'production' and len(v) < 32:
            raise ValueError(
                "ENCRYPTION_KEY must be at least 32 characters long in production for security."
            )

        return v

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
