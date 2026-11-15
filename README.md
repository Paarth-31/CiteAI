# CiteAI

CiteAI is a backend-first legal document analysis service. The supported runtime is [backend/](./backend); frontend integration is intentionally out of scope for this backend pass.

## Canonical pipeline

```text
PDF upload
  -> page-aware text extraction
  -> normalized OCR metadata + citation graph
  -> sentence-transformer and InLegalBERT embeddings
  -> persisted pgvector-ready document material
  -> deterministic internal coherence review
  -> pgvector corpus retrieval + transparent TRS scoring
  -> persisted analysis result
```

The pipeline is implemented in [legal_pipeline.py](./backend/app/services/legal_pipeline.py) and is invoked by `POST /api/ocr/process/<document_id>`.

The OCR stage also persists normalized text, page metadata, citation-graph material, and sentence embeddings so the later InLegalBERT, pgvector, retrieval, and scoring stages consume one consistent document record. LexAI is no longer a separate runtime.

## Backend setup

Use Python 3.11 or newer, PostgreSQL 15+ with pgvector, and Tesseract OCR for scanned PDFs.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env with real database URLs and a strong JWT_SECRET_KEY
python init_db.py
python precompute_corpus.py --pdf-dir ../corpus/legal_pdfs
flask --app manage run --port 8000
```

See [backend/README.md](./backend/README.md) for the endpoint list and [NEXT_STEPS.md](./backend/NEXT_STEPS.md) for the complete setup, model warm-up, corpus preparation, API smoke test, and release checklist.
