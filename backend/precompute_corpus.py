"""Precompute legal/bio corpus into PostgreSQL (pgvector).

Usage examples:
    # 1) load HuggingFace dataset directly
    python precompute_corpus.py --hf-dataset ninadn/indian-legal --domain legal --limit 2000

    # 2) load local PDFs (constitution/ipc/etc)
    python precompute_corpus.py --pdf-dir ../corpus/legal_pdfs --domain legal

    # 3) combine both in one run
    python precompute_corpus.py --hf-dataset ninadn/indian-legal --pdf-dir ../corpus/legal_pdfs --domain legal

Notes:
    - Requires pgvector extension enabled in PostgreSQL.
    - Stores document metadata in corpus_documents and chunk vectors in corpus_chunks.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter

import sys
from pathlib import Path

_BACKEND_ROOT  = Path(__file__).resolve().parent      # .../CiteAI/backend/
_CITEAI_ROOT   = _BACKEND_ROOT.parent                 # .../CiteAI/
_LEXAI_ROOT    = _CITEAI_ROOT / "lexai"               # .../CiteAI/lexai/

for _p in [str(_CITEAI_ROOT), str(_LEXAI_ROOT)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from app import create_app
from app.extensions import db, model_registry
from app.models import CorpusChunk, CorpusDocument


def _iter_hf_rows(dataset_name: str, split: str, limit: int | None):
    from datasets import load_dataset  # optional dependency, imported lazily

    ds = load_dataset(dataset_name, split=split)
    if limit:
        ds = ds.select(range(min(limit, len(ds))))
    for idx, row in enumerate(ds):
        text = str(row.get("Text") or row.get("text") or "").strip()
        summary = str(row.get("Summary") or row.get("summary") or "").strip()
        if not text:
            continue
        title = text.splitlines()[0][:240] or f"{dataset_name}-{idx}"
        yield {
            "source_type": "hf_dataset",
            "source_id": f"{dataset_name}:{split}:{idx}",
            "title": title,
            "full_text": text,
            "summary": summary or None,
            "metadata_json": {"dataset": dataset_name, "split": split, "row_index": idx},
        }


def _iter_pdf_rows(pdf_dir: Path):
    from lexai.agents.ocr_agent import (
        extract_citations,
        extract_keywords,
        extract_text_from_pdf,
        extract_title,
    )

    for pdf_file in sorted(pdf_dir.glob("*.pdf")):
        try:
            text = extract_text_from_pdf(str(pdf_file)).strip()
        except Exception:
            continue
        if not text:
            continue
        yield {
            "source_type": "local_pdf",
            "source_id": pdf_file.name,
            "title": extract_title(text)[:500],
            "full_text": text,
            "summary": None,
            "keywords": extract_keywords(text, top_n=40),
            "citations": extract_citations(text),
            "metadata_json": {"pdf_path": str(pdf_file)},
        }


def _upsert_document(domain: str, payload: dict) -> CorpusDocument:
    doc = CorpusDocument.query.filter_by(
        source_type=payload["source_type"],
        source_id=payload["source_id"],
    ).one_or_none()
    if doc is None:
        doc = CorpusDocument(
            domain=domain,
            source_type=payload["source_type"],
            source_id=payload["source_id"],
            title=payload["title"],
            full_text=payload["full_text"],
            summary=payload.get("summary"),
            keywords=payload.get("keywords") or [],
            citations=payload.get("citations") or [],
            metadata_json=payload.get("metadata_json") or {},
        )
        db.session.add(doc)
    else:
        doc.domain = domain
        doc.title = payload["title"]
        doc.full_text = payload["full_text"]
        doc.summary = payload.get("summary")
        doc.keywords = payload.get("keywords") or []
        doc.citations = payload.get("citations") or []
        doc.metadata_json = payload.get("metadata_json") or {}
        CorpusChunk.query.filter_by(corpus_document_id=doc.id).delete()
    return doc


def _build_chunks(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    return splitter.split_text(text)


def main():
    parser = argparse.ArgumentParser(description="Precompute corpus into PostgreSQL vectors")
    parser.add_argument("--domain", choices=["legal", "bio"], default="legal")
    parser.add_argument("--hf-dataset", default=None, help="HuggingFace dataset id, e.g. ninadn/indian-legal")
    parser.add_argument("--hf-split", default="train")
    parser.add_argument("--pdf-dir", default=None, help="Directory containing PDF files")
    parser.add_argument("--limit", type=int, default=None, help="Optional row limit for HF dataset")
    parser.add_argument("--chunk-size", type=int, default=900)
    parser.add_argument("--chunk-overlap", type=int, default=150)
    parser.add_argument("--reset-domain", action="store_true", help="Delete existing corpus rows in this domain first")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        if args.reset_domain:
            docs = CorpusDocument.query.filter_by(domain=args.domain).all()
            doc_ids = [d.id for d in docs]
            if doc_ids:
                CorpusChunk.query.filter(CorpusChunk.corpus_document_id.in_(doc_ids)).delete(synchronize_session=False)
            CorpusDocument.query.filter_by(domain=args.domain).delete(synchronize_session=False)
            db.session.commit()
            print(f"Reset done for domain={args.domain}")

        sentence_model = model_registry.get_sentence_model()
        total_docs = 0
        total_chunks = 0

        sources = []
        if args.hf_dataset:
            sources.append(_iter_hf_rows(args.hf_dataset, args.hf_split, args.limit))
        if args.pdf_dir:
            sources.append(_iter_pdf_rows(Path(args.pdf_dir)))
        if not sources:
            raise ValueError("Provide --hf-dataset and/or --pdf-dir")

        for source in sources:
            for payload in source:
                doc = _upsert_document(args.domain, payload)
                db.session.flush()  # ensure doc.id

                chunks = _build_chunks(doc.full_text, args.chunk_size, args.chunk_overlap)
                if not chunks:
                    continue
                vectors = sentence_model.encode(chunks, convert_to_numpy=True)

                for idx, (chunk_text, vector) in enumerate(zip(chunks, vectors)):
                    chunk = CorpusChunk(
                        corpus_document_id=doc.id,
                        chunk_index=idx,
                        chunk_text=chunk_text,
                        sentence_embedding=vector.tolist(),
                        metadata_json={"domain": args.domain},
                    )
                    db.session.add(chunk)
                    total_chunks += 1

                total_docs += 1
                if total_docs % 25 == 0:
                    db.session.commit()
                    print(f"Processed docs={total_docs}, chunks={total_chunks}")

        db.session.commit()
        print(f"Completed. docs={total_docs}, chunks={total_chunks}, domain={args.domain}")


if __name__ == "__main__":
    main()
