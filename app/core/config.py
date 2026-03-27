"""
Configuration Module
===================
Manages all application configuration using environment variables.
Uses Pydantic Settings for validation and type safety.

Environment variables are loaded from .env file in development.

Author: Political Communication Platform Team
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List
from pathlib import Path


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    All sensitive data (keys, passwords) must be set via environment.
    """
    
    # Application settings
    APP_NAME: str = Field(default="Political Communication Platform", description="Application name")
    API_V1_PREFIX: str = Field(default="/api/v1", description="API version prefix")
    DEBUG: bool = Field(default=False, description="Debug mode flag")
    
    # Security settings
    SECRET_KEY: str = Field(..., description="Secret key for JWT encoding (REQUIRED)")
    ALGORITHM: str = Field(default="HS256", description="JWT algorithm")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=1440, description="Token expiry in minutes (24 hours)")
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, description="Refresh token expiry in days")
    
    # Password hashing
    PWD_BCRYPT_ROUNDS: int = Field(default=12, description="Bcrypt rounds for password hashing")
    
    # MongoDB settings
    MONGODB_URL: str = Field(..., description="MongoDB connection URL (REQUIRED)")
    MONGODB_DB_NAME: str = Field(default="political_platform", description="Database name")
    
    # CORS settings
    ALLOWED_ORIGINS: List[str] = Field(
        default=["*"],  # Allow all origins for development/mobile
        description="Allowed CORS origins"
    )
    
    # Pagination defaults
    DEFAULT_PAGE_SIZE: int = Field(default=20, description="Default items per page")
    MAX_PAGE_SIZE: int = Field(default=100, description="Maximum items per page")
    
    # File upload settings
    MAX_UPLOAD_SIZE_MB: int = Field(default=5, description="Maximum file upload size in MB")
    ALLOWED_IMAGE_TYPES: List[str] = Field(
        default=["image/jpeg", "image/png", "image/jpg"],
        description="Allowed image MIME types"
    )
    
    # Notification settings
    ENABLE_PUSH_NOTIFICATIONS: bool = Field(default=False, description="Enable push notifications")
    ENABLE_EMAIL_NOTIFICATIONS: bool = Field(default=False, description="Enable email notifications")
    
    # Analytics settings
    SENTIMENT_ANALYSIS_ENABLED: bool = Field(default=False, description="Enable sentiment analysis")

    # Bedrock / LLM settings
    gpt_model: str = Field(
        default="bedrock/amazon.nova-lite-v1:0",
        validation_alias="GPT_MODEL",
        description="Bedrock model id (env: GPT_MODEL)",
    )
    AWS_ACCESS_KEY_ID: str = Field(default="", description="AWS access key")
    AWS_SECRET_ACCESS_KEY: str = Field(default="", description="AWS secret key")
    AWS_DEFAULT_REGION: str = Field(default="", description="AWS default region")
    
    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = Field(default=60, description="API rate limit per minute per user")
    
    class Config:
        """Pydantic configuration"""
        env_file = str(Path(__file__).resolve().parents[2] / ".env")
        env_file_encoding = "utf-8"
        case_sensitive = True


# Create global settings instance
settings = Settings()
