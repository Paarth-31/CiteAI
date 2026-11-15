"""Application configuration — dual PostgreSQL setup.

Two databases:
  AUTH_DATABASE_URL  → citeai_auth   (users table only)
  DATABASE_URL       → citeai_main   (everything else)

PostgreSQL features used:
  - JSONB columns   : indexed JSON for ocr_metadata, citation_graph, etc.
  - tsvector/GIN    : full-text search on ocr_text and baseline case text
  - pgvector        : 768-dim vectors for InLegalBERT embeddings (FAISS cache)
  - UUID primary keys: native uuid type, no string padding
  - ARRAY columns   : citation/keyword lists stored as text[]
  - Connection pool : pgBouncer-compatible pool_pre_ping + pool_recycle
"""
from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.absolute()


def _postgresql_url(url: str) -> str:
    """Keep bare PostgreSQL URLs on the psycopg2 driver we install.

    SQLAlchemy 2.1 changed the default for ``postgresql://`` to psycopg 3.
    Explicit driver URLs remain untouched.
    """
    prefix = "postgresql://"
    return f"postgresql+psycopg2://{url[len(prefix):]}" if url.startswith(prefix) else url


class BaseConfig:
    # ── Main database (citeai_main) ───────────────────────────────────────────
    # Stores: documents, citations, chats, messages, baseline_cases
    SQLALCHEMY_DATABASE_URI = _postgresql_url(os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://citeai:citeai_pass@localhost:5432/citeai_main",
    ))

    # ── Auth database (citeai_auth) ───────────────────────────────────────────
    # Stores: users only — isolated so auth data never touches main DB
    SQLALCHEMY_BINDS = {
        "auth": _postgresql_url(os.getenv(
            "AUTH_DATABASE_URL",
            "postgresql+psycopg2://citeai:citeai_pass@localhost:5432/citeai_auth",
        ))
    }

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Pool tuned for PostgreSQL (ignored by SQLite)
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping":    True,   # validates connections before use
        "pool_recycle":     1800,   # drop connections older than 30 min
        "pool_size":        10,     # keep 10 connections ready
        "max_overflow":     20,     # allow 20 extra under burst load
        "connect_args": {
            "connect_timeout": 10,
            "application_name": "citeai_backend",
        },
    }

    # ── JWT ───────────────────────────────────────────────────────────────────
    JWT_SECRET_KEY             = os.getenv("JWT_SECRET_KEY", "change-me-before-production")
    JWT_TOKEN_LOCATION         = ["headers"]
    JWT_HEADER_TYPE            = "Bearer"
    JWT_ACCESS_TOKEN_EXPIRES   = timedelta(minutes=int(os.getenv("JWT_ACCESS_MINUTES", "30")))
    JWT_REFRESH_TOKEN_EXPIRES  = timedelta(days=int(os.getenv("JWT_REFRESH_DAYS", "7")))
    PROPAGATE_EXCEPTIONS       = True

    # ── File upload ───────────────────────────────────────────────────────────
    UPLOAD_FOLDER       = os.getenv("UPLOAD_FOLDER", str(PROJECT_ROOT / "storage" / "uploads"))
    MAX_CONTENT_LENGTH  = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50")) * 1024 * 1024

    # ── CORS ──────────────────────────────────────────────────────────────────
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")

    # ── Model registry ────────────────────────────────────────────────────────
    MODEL_DEVICE         = os.getenv("MODEL_DEVICE", "auto")
    LEGALBERT_MODEL_NAME = os.getenv("LEGALBERT_MODEL_NAME", "law-ai/InLegalBERT")
    LEGALBERT_MAX_LENGTH = int(os.getenv("LEGALBERT_MAX_LENGTH", "512"))

    SENTENCE_MODEL_NAME = os.getenv(
        "SENTENCE_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2"
    )

    # ── FAISS ─────────────────────────────────────────────────────────────────
    FAISS_INDEX_DIR = os.getenv(
        "FAISS_INDEX_DIR", str(PROJECT_ROOT / "storage" / "faiss_indexes")
    )
    FAISS_TOP_K = int(os.getenv("FAISS_TOP_K", "20"))


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class ProductionConfig(BaseConfig):
    DEBUG = False
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=int(os.getenv("JWT_ACCESS_MINUTES", "15")))
    # Tighter pool for production
    SQLALCHEMY_ENGINE_OPTIONS = {
        **BaseConfig.SQLALCHEMY_ENGINE_OPTIONS,
        "pool_size":    20,
        "max_overflow": 40,
    }


class TestingConfig(BaseConfig):
    TESTING = True
    # SQLite cannot compile PostgreSQL JSONB/TSVECTOR/pgvector columns. Tests
    # must use an isolated PostgreSQL database with the same extensions.
    SQLALCHEMY_DATABASE_URI = _postgresql_url(os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+psycopg2://citeai:citeai_pass@localhost:5432/citeai_main_test",
    ))
    SQLALCHEMY_BINDS = {
        "auth": _postgresql_url(os.getenv(
            "TEST_AUTH_DATABASE_URL",
            "postgresql+psycopg2://citeai:citeai_pass@localhost:5432/citeai_auth_test",
        ))
    }


config_by_name = {
    "development": DevelopmentConfig,
    "production":  ProductionConfig,
    "testing":     TestingConfig,
    "default":     DevelopmentConfig,
}
