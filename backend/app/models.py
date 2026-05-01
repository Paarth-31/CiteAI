"""Database models — PostgreSQL edition.

Two databases via SQLALCHEMY_BINDS:
  __bind_key__ = "auth"   → citeai_auth  (User only)
  __bind_key__ = None     → citeai_main  (everything else)

PostgreSQL features used per model:
  User          — UUID PK, indexed email
  BaselineCase  — TSVECTOR GIN index for full-text search, ARRAY keywords/citations
  Document      — JSONB for ocr_metadata/citation_graph/internal_analysis,
                  TSVECTOR GIN on ocr_text, pgvector 768-dim for InLegalBERT embeddings
  Citation      — JSONB evidence, float arrays for scores
  Chat/Message  — JSONB metadata
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Index, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR, UUID
from pgvector.sqlalchemy import Vector

from .extensions import bcrypt, db


# ─────────────────────────────────────────────────────────────────────────────
# AUTH DATABASE  (bind = "auth"  →  citeai_auth)
# ─────────────────────────────────────────────────────────────────────────────

class User(db.Model):
    """Auth-only model.  Lives exclusively in citeai_auth."""
    __tablename__ = "users"
    __bind_key__  = "auth"

    id            = db.Column(UUID(as_uuid=True), primary_key=True,
                              server_default=text("gen_random_uuid()"))
    name          = db.Column(db.String(120), nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at    = db.Column(db.DateTime(timezone=True),
                              server_default=text("NOW()"), nullable=False)
    updated_at    = db.Column(db.DateTime(timezone=True),
                              server_default=text("NOW()"),
                              onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_users_email", "email"),   # fast login lookup
    )

    def set_password(self, password: str) -> None:
        self.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")

    def check_password(self, password: str) -> bool:
        return bcrypt.check_password_hash(self.password_hash, password)

    # user_id is stored as a plain str UUID in citeai_main tables.
    # Cross-DB FK enforcement is done in application code, not at DB level.
    @property
    def id_str(self) -> str:
        return str(self.id)

    def __repr__(self) -> str:
        return f"<User {self.email}>"


# ─────────────────────────────────────────────────────────────────────────────
# MAIN DATABASE  (bind = None  →  citeai_main)
# ─────────────────────────────────────────────────────────────────────────────

class BaselineCase(db.Model):
    """Pre-seeded legal cases from lexai/data/processed/ JSON files.

    PostgreSQL features:
      - full_text_tsv  : TSVECTOR column auto-updated by trigger; GIN indexed
                         → enables fast full-text search with ranking
      - citations/keywords/articles : TEXT ARRAY → can be searched with ANY()
      - stats          : JSONB → supports key-based filtering
    """
    __tablename__ = "baseline_cases"

    id         = db.Column(UUID(as_uuid=True), primary_key=True,
                            server_default=text("gen_random_uuid()"))
    slug       = db.Column(db.String(128), unique=True, nullable=False)
    title      = db.Column(db.String(512),  nullable=False)
    full_text  = db.Column(db.Text,          nullable=False)
    # TSVECTOR maintained by PostgreSQL trigger (created in init_db.py)
    full_text_tsv = db.Column(TSVECTOR, nullable=True)

    citations  = db.Column(ARRAY(db.Text), default=list)   # list of citation strings
    articles   = db.Column(ARRAY(db.Text), default=list)   # list of article strings
    keywords   = db.Column(ARRAY(db.Text), default=list)   # list of keyword strings
    stats      = db.Column(JSONB,           default=dict)   # {num_citations, …}
    created_at = db.Column(db.DateTime(timezone=True), server_default=text("NOW()"))

    __table_args__ = (
        # GIN index on tsvector for sub-millisecond full-text search
        Index("ix_baseline_cases_fts", "full_text_tsv", postgresql_using="gin"),
        Index("ix_baseline_cases_slug", "slug"),
        # GIN index on JSONB stats for key-based queries
        Index("ix_baseline_cases_stats", "stats", postgresql_using="gin"),
    )

    def __repr__(self) -> str:
        return f"<BaselineCase {self.slug}>"


class Document(db.Model):
    """User-uploaded document.

    PostgreSQL features:
      - ocr_metadata / citation_graph / internal_analysis : JSONB
        → allows queries like Document.citation_graph['nodes'] without full scan
      - ocr_text_tsv  : TSVECTOR GIN — full-text search across all OCR'd docs
      - legal_embedding : pgvector Vector(768) — InLegalBERT embedding cached
                          here so FAISS rebuild is not needed on every request
      - sentence_embedding : Vector(384) — sentence-transformer embedding
    """
    __tablename__ = "documents"

    id          = db.Column(UUID(as_uuid=True), primary_key=True,
                             server_default=text("gen_random_uuid()"))
    title       = db.Column(db.String(255), nullable=False)
    file_url    = db.Column(db.String(512), nullable=False)
    file_size   = db.Column(db.Integer,     nullable=False)
    status      = db.Column(db.String(50),  nullable=False,
                             server_default=text("'pending'"))

    # OCR output
    ocr_text        = db.Column(db.Text)
    ocr_text_tsv    = db.Column(TSVECTOR, nullable=True)   # auto-updated by trigger
    ocr_metadata    = db.Column(JSONB)   # {pages, stats:{num_pages,num_citations}}

    # Processed outputs — JSONB so JS objects land without serialisation overhead
    citation_graph    = db.Column(JSONB)  # {nodes:[…], edges:[…]}
    internal_analysis = db.Column(JSONB)  # coherence report

    # pgvector embeddings — eliminates FAISS rebuild on every API call
    # Populated by /api/inference/similar/<id> after first run
    legal_embedding    = db.Column(Vector(768),  nullable=True)   # InLegalBERT
    sentence_embedding = db.Column(Vector(384),  nullable=True)   # sentence-transformer

    upload_date = db.Column(db.DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    created_at  = db.Column(db.DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    updated_at  = db.Column(db.DateTime(timezone=True), server_default=text("NOW()"),
                             onupdate=datetime.utcnow)

    # user_id is a UUID string referencing citeai_auth.users.id
    # No FK constraint because cross-database FKs are not supported in PostgreSQL
    user_id = db.Column(db.String(36), nullable=False)

    citations = db.relationship("Citation", backref="document",
                                 lazy=True, cascade="all, delete-orphan")
    chats     = db.relationship("Chat", backref="document", lazy=True)

    __table_args__ = (
        Index("ix_documents_user_id",  "user_id"),
        Index("ix_documents_status",   "status"),
        Index("ix_documents_ocr_fts",  "ocr_text_tsv", postgresql_using="gin"),
        # Partial index — only index completed documents for search
        Index("ix_documents_completed", "user_id", "status",
              postgresql_where=text("status = 'completed'")),
        # JSONB index — allows fast queries on citation_graph structure
        Index("ix_documents_citation_graph", "citation_graph",
              postgresql_using="gin"),
        # pgvector IVFFlat index — approximate nearest-neighbour on embeddings
        # lists=100 is a reasonable default; tune after data volume is known
        Index("ix_documents_legal_emb", "legal_embedding",
              postgresql_using="ivfflat",
              postgresql_with={"lists": 100},
              postgresql_ops={"legal_embedding": "vector_cosine_ops"}),
    )

    def update_status(self, new_status: str) -> None:
        self.status     = new_status
        self.updated_at = datetime.utcnow()

    def __repr__(self) -> str:
        return f"<Document {self.title} [{self.status}]>"


class Citation(db.Model):
    """Individual citation node extracted from a document.

    PostgreSQL features:
      - evidence_json : JSONB — structured evidence span with offsets,
                        replaces plain Text so the frontend can render
                        highlighted spans directly
    """
    __tablename__ = "citations"

    id          = db.Column(UUID(as_uuid=True), primary_key=True,
                             server_default=text("gen_random_uuid()"))
    document_id = db.Column(UUID(as_uuid=True), db.ForeignKey("documents.id"),
                             nullable=False)

    title            = db.Column(db.String(512), nullable=False)
    x                = db.Column(db.Float, server_default=text("50.0"))
    y                = db.Column(db.Float, server_default=text("50.0"))
    citations        = db.Column(db.Integer, server_default=text("0"))
    year             = db.Column(db.Integer)
    similarity_score = db.Column(db.Float)
    trs_score        = db.Column(db.Float)

    # Replaces plain Text — stores {text, start_char, end_char, page} so
    # the frontend can highlight the exact evidence span in the PDF viewer
    evidence_json = db.Column(JSONB)
    source_model  = db.Column(db.String(50))

    created_at = db.Column(db.DateTime(timezone=True), server_default=text("NOW()"))
    updated_at = db.Column(db.DateTime(timezone=True), server_default=text("NOW()"),
                            onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_citations_document_id", "document_id"),
        Index("ix_citations_trs_score",   "trs_score"),
    )

    def __repr__(self) -> str:
        return f"<Citation {self.title} [{self.year}]>"


class CorpusDocument(db.Model):
    """Precomputed external corpus document used for retrieval.

    Stores legal/bio corpora (HF rows, PDFs, statutes) in PostgreSQL so
    demo-time retrieval does not depend on rebuilding FAISS in memory.
    """
    __tablename__ = "corpus_documents"

    id = db.Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    domain = db.Column(db.String(32), nullable=False, server_default=text("'legal'"))
    source_type = db.Column(db.String(32), nullable=False)  # hf_dataset | local_pdf | manual
    source_id = db.Column(db.String(255), nullable=False)   # stable row/file identifier

    title = db.Column(db.String(512), nullable=False)
    full_text = db.Column(db.Text, nullable=False)
    summary = db.Column(db.Text)
    keywords = db.Column(ARRAY(db.Text), default=list)
    citations = db.Column(ARRAY(db.Text), default=list)
    metadata_json = db.Column(JSONB, default=dict)
    created_at = db.Column(db.DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        server_default=text("NOW()"),
        onupdate=datetime.utcnow,
    )

    chunks = db.relationship(
        "CorpusChunk",
        backref="corpus_document",
        lazy=True,
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("source_type", "source_id", name="uq_corpus_source"),
        Index("ix_corpus_documents_domain", "domain"),
        Index("ix_corpus_documents_title", "title"),
        Index("ix_corpus_documents_metadata", "metadata_json", postgresql_using="gin"),
    )

    def __repr__(self) -> str:
        return f"<CorpusDocument {self.source_type}:{self.source_id}>"


class CorpusChunk(db.Model):
    """Chunk-level vectors for fast pgvector nearest-neighbor retrieval."""
    __tablename__ = "corpus_chunks"

    id = db.Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    corpus_document_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("corpus_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index = db.Column(db.Integer, nullable=False)
    chunk_text = db.Column(db.Text, nullable=False)
    metadata_json = db.Column(JSONB, default=dict)

    # sentence-transformer vector for fast retrieval
    sentence_embedding = db.Column(Vector(384), nullable=False)
    # optional legal-domain embedding if precomputed later
    legal_embedding = db.Column(Vector(768), nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), server_default=text("NOW()"), nullable=False)

    __table_args__ = (
        UniqueConstraint("corpus_document_id", "chunk_index", name="uq_corpus_chunk_order"),
        Index("ix_corpus_chunks_document_id", "corpus_document_id"),
        Index(
            "ix_corpus_chunks_sentence_emb",
            "sentence_embedding",
            postgresql_using="ivfflat",
            postgresql_with={"lists": 200},
            postgresql_ops={"sentence_embedding": "vector_cosine_ops"},
        ),
        Index(
            "ix_corpus_chunks_legal_emb",
            "legal_embedding",
            postgresql_using="ivfflat",
            postgresql_with={"lists": 100},
            postgresql_ops={"legal_embedding": "vector_cosine_ops"},
        ),
    )

    def __repr__(self) -> str:
        return f"<CorpusChunk doc={self.corpus_document_id} idx={self.chunk_index}>"


class Chat(db.Model):
    __tablename__ = "chats"

    id          = db.Column(UUID(as_uuid=True), primary_key=True,
                             server_default=text("gen_random_uuid()"))
    title       = db.Column(db.String(255), server_default=text("'Conversation'"))
    user_id     = db.Column(db.String(36),  nullable=False)
    document_id = db.Column(UUID(as_uuid=True), db.ForeignKey("documents.id"),
                             nullable=True)
    created_at  = db.Column(db.DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    updated_at  = db.Column(db.DateTime(timezone=True), server_default=text("NOW()"),
                             onupdate=datetime.utcnow)

    messages = db.relationship("Message", backref="chat", lazy=True,
                                cascade="all, delete-orphan",
                                order_by="Message.created_at")

    __table_args__ = (
        Index("ix_chats_user_id",     "user_id"),
        Index("ix_chats_document_id", "document_id"),
    )

    def __repr__(self) -> str:
        return f"<Chat {self.title}>"


class Message(db.Model):
    __tablename__ = "messages"

    id            = db.Column(UUID(as_uuid=True), primary_key=True,
                               server_default=text("gen_random_uuid()"))
    chat_id       = db.Column(UUID(as_uuid=True), db.ForeignKey("chats.id"), nullable=False)
    role          = db.Column(db.String(20), nullable=False)   # user|assistant|system
    content       = db.Column(db.Text,       nullable=False)
    metadata_json = db.Column(JSONB)   # optional structured payload

    created_at = db.Column(db.DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=text("NOW()"),
                            onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_messages_chat_id", "chat_id"),
    )

    def __repr__(self) -> str:
        return f"<Message {self.role} [{self.chat_id}]>"
