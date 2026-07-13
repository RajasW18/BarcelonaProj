"""
Application configuration — reads from .env file.
All settings are typed and validated via pydantic-settings.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv(".env")

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM
    openai_api_key: str
    model: str = "gpt-4o"
    embedding_model: str = "text-embedding-3-small"

    # football-data.org
    football_data_api_key: str = ""
    football_data_base_url: str = "https://api.football-data.org/v4"

    # Database
    database_url: str = "postgresql://barca:barca@localhost:5432/barcadb"

    # RAG
    rag_top_k: int = 5


settings = Settings()
