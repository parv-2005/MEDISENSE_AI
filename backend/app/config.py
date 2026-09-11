"""Application settings, loaded from environment variables / .env file."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    # --- Auth ---
    jwt_secret: str = "change-me-in-.env"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24

    # --- MongoDB ---
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db: str = "medisense"

    # --- Gemini ---
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.6-flash"
    gemini_embedding_model: str = "gemini-embedding-001"

    # --- Storage ---
    upload_dir: Path = BASE_DIR / "uploads"
    chroma_dir: Path = BASE_DIR / "chroma_db"
    max_upload_mb: int = 25

    # --- OCR ---
    tesseract_cmd: str = ""  # leave empty to use the binary on PATH
    ocr_dpi: int = 300
    min_chars_per_page_for_digital: int = 40

    # --- RAG ---
    chunk_size: int = 900
    chunk_overlap: int = 150
    rag_top_k: int = 5

    # --- CORS ---
    frontend_origin: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
