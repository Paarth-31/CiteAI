"""Add precomputed corpus vector tables

Revision ID: c9f3e1d2a7b4
Revises: a1b2c3d4e5f6
Create Date: 2026-05-01 15:20:00.000000
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "c9f3e1d2a7b4"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "corpus_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("domain", sa.String(length=32), server_default=sa.text("'legal'"), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("full_text", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("keywords", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("citations", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_type", "source_id", name="uq_corpus_source"),
    )
    op.create_index("ix_corpus_documents_domain", "corpus_documents", ["domain"], unique=False)
    op.create_index("ix_corpus_documents_title", "corpus_documents", ["title"], unique=False)
    op.create_index(
        "ix_corpus_documents_metadata",
        "corpus_documents",
        ["metadata_json"],
        unique=False,
        postgresql_using="gin",
    )

    op.create_table(
        "corpus_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("corpus_document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("sentence_embedding", Vector(384), nullable=False),
        sa.Column("legal_embedding", Vector(768), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["corpus_document_id"], ["corpus_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("corpus_document_id", "chunk_index", name="uq_corpus_chunk_order"),
    )
    op.create_index("ix_corpus_chunks_document_id", "corpus_chunks", ["corpus_document_id"], unique=False)
    op.create_index(
        "ix_corpus_chunks_sentence_emb",
        "corpus_chunks",
        ["sentence_embedding"],
        unique=False,
        postgresql_using="ivfflat",
        postgresql_with={"lists": 200},
        postgresql_ops={"sentence_embedding": "vector_cosine_ops"},
    )
    op.create_index(
        "ix_corpus_chunks_legal_emb",
        "corpus_chunks",
        ["legal_embedding"],
        unique=False,
        postgresql_using="ivfflat",
        postgresql_with={"lists": 100},
        postgresql_ops={"legal_embedding": "vector_cosine_ops"},
    )


def downgrade():
    op.drop_index("ix_corpus_chunks_legal_emb", table_name="corpus_chunks", postgresql_using="ivfflat")
    op.drop_index("ix_corpus_chunks_sentence_emb", table_name="corpus_chunks", postgresql_using="ivfflat")
    op.drop_index("ix_corpus_chunks_document_id", table_name="corpus_chunks")
    op.drop_table("corpus_chunks")

    op.drop_index("ix_corpus_documents_metadata", table_name="corpus_documents", postgresql_using="gin")
    op.drop_index("ix_corpus_documents_title", table_name="corpus_documents")
    op.drop_index("ix_corpus_documents_domain", table_name="corpus_documents")
    op.drop_table("corpus_documents")
