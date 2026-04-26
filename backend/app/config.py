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


class BaseConfig:
    # ── Main database (citeai_main) ───────────────────────────────────────────
    # Stores: documents, citations, chats, messages, baseline_cases
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://citeai:citeai_pass@localhost:5432/citeai_main",
    )

    # ── Auth database (citeai_auth) ───────────────────────────────────────────
    # Stores: users only — isolated so auth data never touches main DB
    SQLALCHEMY_BINDS = {
        "auth": os.getenv(
            "AUTH_DATABASE_URL",
            "postgresql+psycopg2://citeai:citeai_pass@localhost:5432/citeai_auth",
        )
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
    MODEL_DEVICE        = os.getenv("MODEL_DEVICE", "auto")
    LEGALBERT_MODEL_NAME = os.getenv("LEGALBERT_MODEL_NAME", "law-ai/InLegalBERT")
    LEGALBERT_MAX_LENGTH = int(os.getenv("LEGALBERT_MAX_LENGTH", "512"))

    BIOBERT_ENABLED    = os.getenv("BIOBERT_ENABLED", "0") == "1"
    BIOBERT_MODEL_NAME = os.getenv("BIOBERT_MODEL_NAME", "dmis-lab/biobert-base-cased-v1.2")
    BIOBERT_MAX_LENGTH = int(os.getenv("BIOBERT_MAX_LENGTH", "512"))

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
    # Use SQLite in-memory for tests — override per-test if needed
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_BINDS        = {"auth": "sqlite:///:memory:"}
    BIOBERT_ENABLED         = False


config_by_name = {
    "development": DevelopmentConfig,
    "production":  ProductionConfig,
    "testing":     TestingConfig,
    "default":     DevelopmentConfig,
}
