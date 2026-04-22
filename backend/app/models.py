"""Database models for CiteAI.

Current state: SQLite-compatible via SQLAlchemy.

TODO (after FAISS + model layer update):
  - Switch SQLALCHEMY_DATABASE_URI to PostgreSQL in config.py and .env
  - Add pgvector extension for storing FAISS embedding vectors natively
  - Add indexes on frequently queried columns (user_id, status, created_at)
  - Add full-text search index on ocr_text using PostgreSQL tsvector
  - Migrate with: flask db migrate -m "postgres-migration" && flask db upgrade
"""
from __future__ import annotations

from datetime import datetime
import uuid

from .extensions import bcrypt, db


# ─────────────────────────────────────────────────────────────────────────────
# TODO: PostgreSQL-specific additions (implement after DB layer finalised)
# ─────────────────────────────────────────────────────────────────────────────
#
#   from sqlalchemy.dialects.postgresql import UUID, JSONB, TSVECTOR
#   from pgvector.sqlalchemy import Vector
#
#   Replace db.Column(db.String(36)) IDs with UUID(as_uuid=True) for Postgres.
#   Replace db.Column(db.JSON) with JSONB for indexed JSON queries.
#   Add Vector column to Document for storing FAISS embedding cache:
#       embedding_vector = db.Column(Vector(384))   # for sentence-transformer
#       legal_embedding  = db.Column(Vector(768))   # for InLegalBERT
#       bio_embedding    = db.Column(Vector(768))   # for BioBERT (when enabled)
#
# ─────────────────────────────────────────────────────────────────────────────


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(
        db.String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    documents = db.relationship(
        "Document", backref="user", lazy="dynamic", cascade="all, delete-orphan"
    )
    chats = db.relationship(
        "Chat", backref="user", lazy="dynamic", cascade="all, delete-orphan"
    )

    def set_password(self, password: str) -> None:
        self.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")

    def check_password(self, password: str) -> bool:
        return bcrypt.check_password_hash(self.password_hash, password)

    def __repr__(self) -> str:
        return f"<User {self.email}>"


class Document(db.Model):
    __tablename__ = "documents"

    id = db.Column(
        db.String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    title = db.Column(db.String(255), nullable=False)
    file_url = db.Column(db.String(512), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(50), default="pending", nullable=False, index=True)

    # OCR + analysis cache — populated by /api/ocr/process/<id>
    ocr_text = db.Column(db.Text)
    ocr_metadata = db.Column(db.JSON)           # titles, citations[], articles[]
    citation_graph = db.Column(db.JSON)         # {nodes, edges}
    internal_analysis = db.Column(db.JSON)      # coherence report

    # TODO (PostgreSQL): replace JSON columns above with JSONB for index support
    # TODO (PostgreSQL + FAISS): add embedding vector columns (see header TODOs)
    # faiss_index_key = db.Column(db.String(128))  # key into persistent FAISS store

    upload_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user_id = db.Column(
        db.String(36), db.ForeignKey("users.id"), nullable=False, index=True
    )
    citations = db.relationship(
        "Citation", backref="document", lazy=True, cascade="all, delete-orphan"
    )
    chats = db.relationship(
        "Chat", backref="document", lazy=True
    )

    def update_status(self, new_status: str) -> None:
        self.status = new_status
        self.updated_at = datetime.utcnow()

    def __repr__(self) -> str:
        return f"<Document {self.title} [{self.status}]>"


class Citation(db.Model):
    __tablename__ = "citations"

    id = db.Column(
        db.String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    document_id = db.Column(
        db.String(36), db.ForeignKey("documents.id"), nullable=False, index=True
    )

    # Graph node fields (from citation graph builder)
    title = db.Column(db.String(512), nullable=False)
    x = db.Column(db.Float, default=50.0)       # layout position 0–100
    y = db.Column(db.Float, default=50.0)
    citations = db.Column(db.Integer, default=0) # in-degree count
    year = db.Column(db.Integer)

    # TRS scores from inference agents
    similarity_score = db.Column(db.Float)
    trs_score = db.Column(db.Float)
    evidence_span = db.Column(db.Text)          # ≤40-word extracted span (FR 4)

    # Source model that generated this citation result
    # Values: "legalbert" | "biobert" | "sentence-transformer"
    source_model = db.Column(db.String(50))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<Citation {self.title} [{self.year}]>"


class Chat(db.Model):
    __tablename__ = "chats"

    id = db.Column(
        db.String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    title = db.Column(db.String(255), default="Conversation")
    user_id = db.Column(
        db.String(36), db.ForeignKey("users.id"), nullable=False, index=True
    )
    document_id = db.Column(
        db.String(36), db.ForeignKey("documents.id"), nullable=True
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    messages = db.relationship(
        "Message", backref="chat", lazy=True, cascade="all, delete-orphan",
        order_by="Message.created_at"
    )

    def __repr__(self) -> str:
        return f"<Chat {self.title}>"


class Message(db.Model):
    __tablename__ = "messages"

    id = db.Column(
        db.String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    chat_id = db.Column(
        db.String(36), db.ForeignKey("chats.id"), nullable=False, index=True
    )
    role = db.Column(db.String(20), nullable=False)     # user | assistant | system
    content = db.Column(db.Text, nullable=False)
    metadata_json = db.Column(db.JSON)                  # optional structured data

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<Message {self.role} [{self.chat_id}]>"
