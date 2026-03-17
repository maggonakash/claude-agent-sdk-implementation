from pydantic_settings import BaseSettings
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    WORKSPACE_DIR: Path = Path(os.getenv("WORKSPACE_DIR", "./workspace")).resolve()
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY")

    MONGODB_URI: str = os.getenv("MONGODB_URI")
    MONGODB_DB_NAME: str = os.getenv("MONGODB_DB_NAME")

    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "change-me-in-production")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_EXPIRE_DAYS: int = int(os.getenv("JWT_EXPIRE_DAYS", "7"))

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()
