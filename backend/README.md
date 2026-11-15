# CiteAI Backend Service

This folder contains the Flask backend that powers authentication, document storage, citation management and chat persistence for the CiteAI platform.

For the full end-to-end runbook, see [NEXT_STEPS.md](./NEXT_STEPS.md). The canonical execution path is [legal_pipeline.py](./app/services/legal_pipeline.py): OCR/text extraction → graph and embedding materialization → InLegalBERT and sentence-transformer inference → pgvector retrieval → internal analysis and transparent scoring.

## Prerequisites

- Python 3.11+
- PostgreSQL 15+ with the `pgvector` extension
- Virtual environment tooling (`venv`, `conda`, etc.)

For scanned PDFs, install the system `tesseract-ocr` package as well. Embedded
PDF text is always attempted before the page-image OCR fallback.

Set `GEMINI_API_KEY` in `backend/.env` to enable passage-grounded document Q&A
and the detailed internal report. `GEMINI_MODEL` defaults to `gemini-2.5-flash`;
the Python SDK is included in `requirements.txt`. With no key, deterministic
internal review still runs, but chat Q&A returns a configuration error.

The upload screen offers two paths after saving a PDF:

- **Analyze document**: `POST /api/ocr/process/<id>` performs OCR, citations,
  embeddings, internal review, and corpus retrieval. It backfills old documents
  that have OCR/graph data but are missing downstream artifacts.
- **Add to db**: `POST /api/documents/<id>/add-to-db` performs OCR (including
  scanned-page Tesseract fallback), embeds chunks, and saves them to
  `corpus_documents`/`corpus_chunks` plus the owner's searchable `documents`
  row. It does not create citation graph nodes or citation rows. Manual corpus
  documents are owner-scoped and are removed when the upload is deleted.

## Quick start

1. Copy `.env.example` to `.env` and update the connection string and secret key:

   ```bash
   cp .env.example .env
   ```

2. Install dependencies and run the development server:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows PowerShell
   pip install -r requirements.txt
   python init_db.py
   flask --app manage run --port 8000
   ```

   The API will be available at `http://127.0.0.1:8000`.

3. (Optional) Seed demo data:

   ```bash
   flask seed
   ```

Set `CORS_ORIGINS` in `.env` if the frontend runs on a different origin (comma-separated list, defaults to local Next.js dev URLs).

## Project structure

```
backend/
├── app/
│   ├── __init__.py          # Application factory
│   ├── config.py            # Environment specific settings
│   ├── extensions.py        # SQLAlchemy, JWT, Bcrypt instances
│   ├── models/              # SQLAlchemy models
│   ├── routes/              # Blueprint routes (auth, documents, chats, ...)
│   ├── schemas/             # Response serializers
│   └── services/            # Business logic helpers
├── manage.py                # Flask CLI entry point
├── requirements.txt         # Python dependencies
└── README.md
```

## Database initialisation

`python init_db.py` is the supported bootstrap command. It creates the main and
auth schemas separately, enables PostgreSQL extensions, creates vector/FTS
indexes, and seeds backend corpus fixtures. Do not use the historical Alembic
chain: it predates the split auth database and UUID/pgvector schema.

## Authentication

Authentication relies on JWT access and refresh tokens returned by `/api/auth/login`. The frontend stores the `accessToken` for API requests and can call `/api/auth/refresh` to obtain a fresh token when required.

## Available endpoints

- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/refresh`
- `GET /api/auth/me`
- `POST /api/auth/logout`
- `GET /api/documents`
- `POST /api/documents`
- `POST /api/documents/upload`
- `GET /api/documents/<id>`
- `PUT /api/documents/<id>`
- `DELETE /api/documents/<id>`
- `POST /api/ocr/process/<id>` — complete extraction, embedding, analysis, and retrieval pipeline
- `GET /api/ocr/internal-analysis/<id>`
- `POST /api/ocr/query/<id>` — evidence-only query over persisted OCR text
- `GET /api/ocr/citation-graph/<id>`
- `POST /api/inference/similar/<id>`
- `GET /api/inference/similar/<id>`
- `GET /api/documents/<id>/citations`
- `POST /api/documents/<id>/citations`
- `DELETE /api/documents/<id>/citations/<citation_id>`
- `GET /api/chats`
- `POST /api/chats`
- `GET /api/chats/<id>`
- `POST /api/chats/<id>/messages`

## Precompute corpus for fast demos

To keep demo retrieval fast, preload your external corpus into PostgreSQL once,
then query it via pgvector during inference.

### 1) Where to keep files locally

- Legal PDFs (Constitution, IPC, CrPC, etc.): `CiteAI/corpus/legal_pdfs/`
- Bundled baseline material lives in `backend/resources/corpus/`.

### 2) Apply schema + install dependencies

```bash
cd backend
pip install -r requirements.txt
python init_db.py
```

### 3) Preload Hugging Face corpus

```bash
cd backend
python precompute_corpus.py --hf-dataset ninadn/indian-legal --hf-split train --domain legal
```

Use `--limit 1000` first for a quicker dry run.

### 4) Preload local legal PDFs

```bash
cd backend
python precompute_corpus.py --pdf-dir ../corpus/legal_pdfs --domain legal
```

### 5) Reset and rebuild one domain (optional)

```bash
cd backend
python precompute_corpus.py --domain legal --reset-domain --hf-dataset ninadn/indian-legal --pdf-dir ../corpus/legal_pdfs
```

This fills:
- `corpus_documents`: source metadata + full text
- `corpus_chunks`: chunk text + `sentence_embedding` (pgvector)

Your inference route (`POST /api/inference/similar/<document_id>`) then retrieves
from these precomputed vectors first, which removes per-request FAISS rebuild cost.
