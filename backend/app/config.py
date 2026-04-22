"""Application configuration settings."""
from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.absolute()


class BaseConfig:
    # ── Database ──────────────────────────────────────────────────────────────
    # SQLite used until PostgreSQL integration is finalised after FAISS update.
    # To switch: set DATABASE_URL=postgresql+psycopg2://user:pass@host/dbname
    #
    # TODO: replace SQLite default with PostgreSQL once DB layer is ready.
    _db_path = PROJECT_ROOT / "instance" / "citeai.db"
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", f"sqlite:///{_db_path.as_posix()}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Pool settings — relevant once PostgreSQL is live, ignored by SQLite.
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,      # drop stale connections before use
        "pool_recycle": 1800,       # recycle connections every 30 min
    }

    # ── JWT ───────────────────────────────────────────────────────────────────
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-before-production")
    JWT_TOKEN_LOCATION = ["headers"]
    JWT_HEADER_TYPE = "Bearer"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        minutes=int(os.getenv("JWT_ACCESS_MINUTES", "30"))
    )
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(
        days=int(os.getenv("JWT_REFRESH_DAYS", "7"))
    )
    PROPAGATE_EXCEPTIONS = True

    # ── File upload ───────────────────────────────────────────────────────────
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", str(PROJECT_ROOT / "storage" / "uploads"))
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50")) * 1024 * 1024

    # ── CORS ──────────────────────────────────────────────────────────────────
    CORS_ORIGINS = os.getenv(
        "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    )

    # ── Model registry ────────────────────────────────────────────────────────
    # Inference device: "cuda", "cpu", or "auto" (auto-detects GPU).
    MODEL_DEVICE = os.getenv("MODEL_DEVICE", "auto")

    # InLegalBERT — primary legal embedding model
    LEGALBERT_MODEL_NAME = os.getenv(
        "LEGALBERT_MODEL_NAME", "law-ai/InLegalBERT"
    )
    LEGALBERT_MAX_LENGTH = int(os.getenv("LEGALBERT_MAX_LENGTH", "512"))

    # BioBERT — secondary biomedical model (team integrating alongside InLegalBERT)
    # Set BIOBERT_ENABLED=1 in .env once FAISS integration is ready.
    BIOBERT_ENABLED = os.getenv("BIOBERT_ENABLED", "0") == "1"
    BIOBERT_MODEL_NAME = os.getenv(
        "BIOBERT_MODEL_NAME", "dmis-lab/biobert-base-cased-v1.2"
    )
    BIOBERT_MAX_LENGTH = int(os.getenv("BIOBERT_MAX_LENGTH", "512"))

    # Sentence-transformer used by ExternalInferenceAgent (TRS / FAISS)
    SENTENCE_MODEL_NAME = os.getenv(
        "SENTENCE_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2"
    )

    # ── FAISS ─────────────────────────────────────────────────────────────────
    # Directory where persistent FAISS indexes are stored.
    # Once FAISS layer is updated, the backend will load/save indexes here
    # instead of rebuilding from scratch on every request.
    FAISS_INDEX_DIR = os.getenv(
        "FAISS_INDEX_DIR", str(PROJECT_ROOT / "storage" / "faiss_indexes")
    )
    # Number of FAISS search results to retrieve before TRS re-ranking.
    FAISS_TOP_K = int(os.getenv("FAISS_TOP_K", "20"))


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class ProductionConfig(BaseConfig):
    DEBUG = False
    # Tighten JWT expiry in production
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        minutes=int(os.getenv("JWT_ACCESS_MINUTES", "15"))
    )


class TestingConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:")
    # Keep models off in tests unless explicitly enabled
    BIOBERT_ENABLED = False


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
