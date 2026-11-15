-- CiteAI PostgreSQL schema
--
-- This is a psql script for the current two-database backend layout.
-- Create the databases first, then run:
--
--   psql -d postgres -f backend/schema.sql
--
-- The database names below match backend/.env.example. If your names differ,
-- replace the two \connect targets or run the AUTH and MAIN sections separately
-- against the appropriate databases.

\set ON_ERROR_STOP on

-- ============================================================================
-- AUTH DATABASE: citeai_auth
-- ============================================================================
\connect citeai_auth

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS users (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name          varchar(120) NOT NULL,
    email         varchar(120) NOT NULL UNIQUE,
    password_hash varchar(256) NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_users_email ON users (email);

CREATE OR REPLACE FUNCTION citeai_auth_touch_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trig_users_updated_at ON users;
CREATE TRIGGER trig_users_updated_at
BEFORE UPDATE ON users
FOR EACH ROW EXECUTE FUNCTION citeai_auth_touch_updated_at();

-- ============================================================================
-- MAIN DATABASE: citeai_main
-- ============================================================================
\connect citeai_main

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS baseline_cases (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug          varchar(128) NOT NULL UNIQUE,
    title         varchar(512) NOT NULL,
    full_text     text NOT NULL,
    full_text_tsv tsvector,
    citations     text[] DEFAULT ARRAY[]::text[],
    articles      text[] DEFAULT ARRAY[]::text[],
    keywords      text[] DEFAULT ARRAY[]::text[],
    stats         jsonb DEFAULT '{}'::jsonb,
    created_at    timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS documents (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    title              varchar(255) NOT NULL,
    file_url           varchar(512) NOT NULL,
    file_size          integer NOT NULL,
    status             varchar(50) NOT NULL DEFAULT 'pending',
    ocr_text           text,
    ocr_text_tsv       tsvector,
    ocr_metadata       jsonb,
    citation_graph     jsonb,
    internal_analysis  jsonb,
    legal_embedding    vector(768),
    sentence_embedding vector(384),
    upload_date        timestamptz NOT NULL DEFAULT now(),
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),
    user_id            varchar(36) NOT NULL
);

CREATE TABLE IF NOT EXISTS citations (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id      uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    title            varchar(512) NOT NULL,
    x                double precision DEFAULT 50.0,
    y                double precision DEFAULT 50.0,
    citations        integer DEFAULT 0,
    year             integer,
    similarity_score double precision,
    trs_score        double precision,
    evidence_json    jsonb,
    source_model     varchar(50),
    created_at       timestamptz DEFAULT now(),
    updated_at       timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS corpus_documents (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    domain        varchar(32) NOT NULL DEFAULT 'legal',
    source_type   varchar(32) NOT NULL,
    source_id     varchar(255) NOT NULL,
    title         varchar(512) NOT NULL,
    full_text     text NOT NULL,
    summary       text,
    keywords      text[] DEFAULT ARRAY[]::text[],
    citations     text[] DEFAULT ARRAY[]::text[],
    metadata_json jsonb DEFAULT '{}'::jsonb,
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz DEFAULT now(),
    CONSTRAINT uq_corpus_source UNIQUE (source_type, source_id)
);

CREATE TABLE IF NOT EXISTS corpus_chunks (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    corpus_document_id uuid NOT NULL REFERENCES corpus_documents(id) ON DELETE CASCADE,
    chunk_index        integer NOT NULL,
    chunk_text         text NOT NULL,
    metadata_json      jsonb DEFAULT '{}'::jsonb,
    sentence_embedding vector(384) NOT NULL,
    legal_embedding    vector(768),
    created_at         timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_corpus_chunk_order UNIQUE (corpus_document_id, chunk_index)
);

CREATE TABLE IF NOT EXISTS chats (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    title       varchar(255) DEFAULT 'Conversation',
    user_id     varchar(36) NOT NULL,
    document_id uuid REFERENCES documents(id),
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS messages (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    chat_id       uuid NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    role          varchar(20) NOT NULL,
    content       text NOT NULL,
    metadata_json jsonb,
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz DEFAULT now()
);

-- Full-text search materialization used by the backend search routes.
CREATE OR REPLACE FUNCTION citeai_baseline_cases_fts_update()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.full_text_tsv :=
        setweight(to_tsvector('english', coalesce(NEW.title, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(NEW.full_text, '')), 'B');
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION citeai_documents_fts_update()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.ocr_text_tsv :=
        setweight(to_tsvector('english', coalesce(NEW.title, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(NEW.ocr_text, '')), 'B');
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trig_baseline_cases_fts ON baseline_cases;
CREATE TRIGGER trig_baseline_cases_fts
BEFORE INSERT OR UPDATE OF title, full_text ON baseline_cases
FOR EACH ROW EXECUTE FUNCTION citeai_baseline_cases_fts_update();

DROP TRIGGER IF EXISTS trig_documents_fts ON documents;
CREATE TRIGGER trig_documents_fts
BEFORE INSERT OR UPDATE OF title, ocr_text ON documents
FOR EACH ROW EXECUTE FUNCTION citeai_documents_fts_update();

-- Keep timestamps correct for direct SQL updates as well as ORM updates.
CREATE OR REPLACE FUNCTION citeai_touch_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trig_documents_updated_at ON documents;
CREATE TRIGGER trig_documents_updated_at
BEFORE UPDATE ON documents
FOR EACH ROW EXECUTE FUNCTION citeai_touch_updated_at();

DROP TRIGGER IF EXISTS trig_citations_updated_at ON citations;
CREATE TRIGGER trig_citations_updated_at
BEFORE UPDATE ON citations
FOR EACH ROW EXECUTE FUNCTION citeai_touch_updated_at();

DROP TRIGGER IF EXISTS trig_corpus_documents_updated_at ON corpus_documents;
CREATE TRIGGER trig_corpus_documents_updated_at
BEFORE UPDATE ON corpus_documents
FOR EACH ROW EXECUTE FUNCTION citeai_touch_updated_at();

DROP TRIGGER IF EXISTS trig_chats_updated_at ON chats;
CREATE TRIGGER trig_chats_updated_at
BEFORE UPDATE ON chats
FOR EACH ROW EXECUTE FUNCTION citeai_touch_updated_at();

DROP TRIGGER IF EXISTS trig_messages_updated_at ON messages;
CREATE TRIGGER trig_messages_updated_at
BEFORE UPDATE ON messages
FOR EACH ROW EXECUTE FUNCTION citeai_touch_updated_at();

-- Query and vector indexes. IVFFlat indexes are valid on empty tables and can
-- be rebuilt later with a tuned lists value as the corpus grows.
CREATE INDEX IF NOT EXISTS ix_baseline_cases_fts
    ON baseline_cases USING gin (full_text_tsv);
CREATE INDEX IF NOT EXISTS ix_baseline_cases_slug
    ON baseline_cases (slug);
CREATE INDEX IF NOT EXISTS ix_baseline_cases_stats
    ON baseline_cases USING gin (stats);

CREATE INDEX IF NOT EXISTS ix_documents_user_id ON documents (user_id);
CREATE INDEX IF NOT EXISTS ix_documents_status ON documents (status);
CREATE INDEX IF NOT EXISTS ix_documents_ocr_fts
    ON documents USING gin (ocr_text_tsv);
CREATE INDEX IF NOT EXISTS ix_documents_completed
    ON documents (user_id, status) WHERE status = 'completed';
CREATE INDEX IF NOT EXISTS ix_documents_citation_graph
    ON documents USING gin (citation_graph);
CREATE INDEX IF NOT EXISTS ix_documents_legal_emb
    ON documents USING ivfflat (legal_embedding vector_cosine_ops)
    WITH (lists = 100);

CREATE INDEX IF NOT EXISTS ix_citations_document_id ON citations (document_id);
CREATE INDEX IF NOT EXISTS ix_citations_trs_score ON citations (trs_score);

CREATE INDEX IF NOT EXISTS ix_corpus_documents_domain ON corpus_documents (domain);
CREATE INDEX IF NOT EXISTS ix_corpus_documents_title ON corpus_documents (title);
CREATE INDEX IF NOT EXISTS ix_corpus_documents_metadata
    ON corpus_documents USING gin (metadata_json);
CREATE INDEX IF NOT EXISTS ix_corpus_chunks_document_id
    ON corpus_chunks (corpus_document_id);
CREATE INDEX IF NOT EXISTS ix_corpus_chunks_sentence_emb
    ON corpus_chunks USING ivfflat (sentence_embedding vector_cosine_ops)
    WITH (lists = 200);
CREATE INDEX IF NOT EXISTS ix_corpus_chunks_legal_emb
    ON corpus_chunks USING ivfflat (legal_embedding vector_cosine_ops)
    WITH (lists = 100);

CREATE INDEX IF NOT EXISTS ix_chats_user_id ON chats (user_id);
CREATE INDEX IF NOT EXISTS ix_chats_document_id ON chats (document_id);
CREATE INDEX IF NOT EXISTS ix_messages_chat_id ON messages (chat_id);

