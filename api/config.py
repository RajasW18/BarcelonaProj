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
    openai_base_url: str = "http://localhost:11434/v1"
    groq_api_key: str = ""
    groq_vision_model: str = "meta-llama/llama-4-scout-17b-16e-instruct"
    ollama_vision_model: str = "llava"
    model: str = "gpt-4o"
    embedding_model: str = "text-embedding-3-small"

    # football-data.org
    football_data_api_key: str = ""
    football_data_base_url: str = "https://api.football-data.org/v4"

    # Database
    database_url: str = "postgresql://barca:barca@localhost:5432/barcadb"

    # RAG
    rag_top_k: int = 5

    # Authentication
    auth_secret: str = "replace-this-auth-secret"
    auth_session_days: int = 30
    auth_cookie_secure: bool = False
    auth_cookie_samesite: str = "lax"
    frontend_url: str = "http://localhost:5173"
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/auth/google/callback"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""


settings = Settings()
