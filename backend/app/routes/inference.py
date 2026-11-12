"""Inference routes for model selection and similarity retrieval."""
from __future__ import annotations

from http import HTTPStatus
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import current_user, jwt_required
from sqlalchemy import text

from ..extensions import db, model_registry
from ..models import CorpusChunk, CorpusDocument, Document
from ..services.document_pipeline import cached_inference_payload, persist_inference_scores
from ..services.paths import ensure_project_root

bp = Blueprint("inference", __name__, url_prefix="/api/inference")


# ── Available models ──────────────────────────────────────────────────────────
@bp.get("/models")
def list_models():
    """Return which models are available and loaded."""
    models = [
        {
            "key":     "legalbert",
            "name":    current_app.config.get("LEGALBERT_MODEL_NAME", "law-ai/InLegalBERT"),
            "enabled": True,
            "loaded":  "legalbert" in model_registry.loaded_models(),
        }
    ]
    return jsonify({"models": models})


# ── Similarity retrieval ──────────────────────────────────────────────────────
@bp.post("/similar/<document_id>")
@jwt_required()
def find_similar(document_id: str):
    """Run similarity retrieval for a processed document.

    Body params:
      top_k   int   number of results  (default: from FAISS_TOP_K config)

    The document must already have ocr_text (i.e. been processed via
    POST /api/ocr/process/<id>) before calling this endpoint.
    """
    doc = Document.query.filter_by(
        id=document_id, user_id=str(current_user.id)
    ).one_or_none()
    if doc is None:
        return jsonify({"error": "Document not found"}), HTTPStatus.NOT_FOUND

    if not doc.ocr_text:
        return jsonify({
            "error": "Document has no OCR text. Run /api/ocr/process/<id> first."
        }), HTTPStatus.BAD_REQUEST

    payload = request.get_json(silent=True) or {}
    top_k = int(payload.get("top_k") or current_app.config.get("FAISS_TOP_K", 20))
    force = bool(payload.get("force")) or request.args.get("force") in {"1", "true", "True"}

    if not force:
        cached = cached_inference_payload(doc)
        saved_k = ((doc.ocr_metadata or {}).get("external_inference") or {}).get("top_k")
        if cached and cached.get("retrieved_cases") and (saved_k is None or int(saved_k) == top_k):
            return jsonify({
                "document_id": document_id,
                "top_k": top_k,
                "results": {"legalbert": cached},
            })

    results = {}
    ensure_project_root()

    try:
        agent = model_registry.get_legalbert_agent()
        legalbert_results = _run_legalbert(agent, doc.ocr_text, top_k)

        # A warning/empty result (e.g. the file fallback found no candidates)
        # is not a successful run: don't persist it over previously saved
        # legalbert rows or replace the cached metadata with a zero score.
        if legalbert_results.get("warning") or not legalbert_results.get("retrieved_cases"):
            current_app.logger.warning(
                "InLegalBERT inference returned no results: %s",
                legalbert_results.get("warning") or "empty retrieved_cases",
            )
            results["legalbert"] = {
                "error": legalbert_results.get("warning")
                or "No related cases could be found for this document.",
            }
        else:
            persist_inference_scores(
                doc,
                legalbert_results.get("retrieved_cases") or [],
                overall=float(legalbert_results.get("overall_external_coherence_score") or 0.0),
                short_summary=legalbert_results.get("short_summary") or "",
                source=legalbert_results.get("source") or "legalbert",
                top_k=top_k,
            )
            db.session.commit()
            results["legalbert"] = {**legalbert_results, "cached": False}
    except Exception as exc:
        current_app.logger.exception("InLegalBERT inference failed: %s", exc)
        db.session.rollback()
        results["legalbert"] = {"error": str(exc)}

    return jsonify({
        "document_id": document_id,
        "top_k": top_k,
        "results": results,
    })


@bp.get("/similar/<document_id>")
@jwt_required()
def get_similar(document_id: str):
    """Return cached inference scores if they were already saved."""
    doc = Document.query.filter_by(
        id=document_id, user_id=str(current_user.id)
    ).one_or_none()
    if doc is None:
        return jsonify({"error": "Document not found"}), HTTPStatus.NOT_FOUND

    cached = cached_inference_payload(doc)
    if not cached:
        return jsonify({"error": "No cached inference. POST this endpoint first."}), HTTPStatus.NOT_FOUND

    return jsonify({
        "document_id": document_id,
        "results": {"legalbert": cached},
    })


# ── Internal helper ───────────────────────────────────────────────────────────
def _run_legalbert(agent, ocr_text: str, top_k: int) -> dict:
    """Run retrieval from PostgreSQL corpus vectors; fallback to in-memory file mode.

    Primary path uses precomputed pgvector rows in corpus_chunks/corpus_documents.
    Fallback path preserves old behavior if corpus preload is not done yet.
    """
    try:
        return _run_pgvector_corpus_retrieval(ocr_text, top_k)
    except Exception as exc:
        current_app.logger.warning("PG vector retrieval unavailable, using fallback: %s", exc)
        return _run_file_fallback(agent, ocr_text, top_k)


def _run_pgvector_corpus_retrieval(ocr_text: str, top_k: int) -> dict:
    sentence_model = model_registry.get_sentence_model()
    query_vector = sentence_model.encode([ocr_text[:4000]], convert_to_numpy=True)[0].tolist()

    # Pull extra chunk hits, then deduplicate by corpus doc with best distance.
    rows = (
        db.session.query(
            CorpusChunk,
            CorpusDocument,
            CorpusChunk.sentence_embedding.op("<=>")(query_vector).label("distance"),
        )
        .join(CorpusDocument, CorpusChunk.corpus_document_id == CorpusDocument.id)
        .filter(CorpusDocument.domain == "legal")
        .order_by(text("distance ASC"))
        .limit(max(top_k * 6, 30))
        .all()
    )

    if not rows:
        raise ValueError("No precomputed corpus vectors found in database")

    by_doc = {}
    for chunk, doc, dist in rows:
        d = float(dist)
        existing = by_doc.get(str(doc.id))
        if existing is None or d < existing["distance"]:
            by_doc[str(doc.id)] = {"chunk": chunk, "doc": doc, "distance": d}

    ordered = sorted(by_doc.values(), key=lambda x: x["distance"])[:top_k]
    retrieved_cases = []
    for item in ordered:
        doc = item["doc"]
        chunk = item["chunk"]
        similarity = max(0.0, min(1.0, 1.0 - item["distance"]))
        meta = doc.metadata_json or {}
        retrieved_cases.append({
            "case_id": str(doc.id),
            "title": doc.title,
            "year": meta.get("year"),
            "jurisdiction": meta.get("jurisdiction", "unknown"),
            "similarity_score": similarity,
            "context_fit": similarity,
            "jurisdiction_score": 0.7,
            "internal_confidence": similarity,
            "uncertainty": max(0.0, 1.0 - similarity),
            "trs": similarity,
            "alignment_type": "supports",
            "justification": "Retrieved from precomputed PostgreSQL vector corpus.",
            "spans": {
                "target_span": ocr_text[:240],
                "candidate_span": (chunk.chunk_text or "")[:240],
            },
        })

    overall = (
        sum(float(c["similarity_score"]) for c in retrieved_cases) / len(retrieved_cases)
        if retrieved_cases else 0.0
    )
    return {
        "source": "postgresql-pgvector",
        "candidates_searched": len(rows),
        "retrieved": retrieved_cases,
        "retrieved_cases": retrieved_cases,
        "overall_external_coherence_score": overall,
        "short_summary": f"Found {len(retrieved_cases)} related cases from precomputed corpus vectors.",
    }


def _run_file_fallback(agent, ocr_text: str, top_k: int) -> dict:
    import json

    data_path = Path(__file__).resolve().parent.parent.parent.parent / "lexai" / "data" / "raw"
    candidates = []
    if data_path.exists():
        for jf in list(data_path.glob("*.json"))[:50]:
            try:
                with open(jf, encoding="utf-8") as f:
                    candidates.append(json.load(f))
            except Exception:
                continue

    if not candidates:
        return {"warning": "No candidate documents found in lexai/data/raw/ and corpus vectors are empty."}

    agent.load_dataset_from_dicts(candidates)
    agent.compute_all_embeddings(batch_size=8)
    retrieved = agent.retrieve_similar_cases(query_text=ocr_text[:2000], top_k=top_k)

    retrieved_cases = []
    for i, item in enumerate(retrieved[:top_k]):
        similarity = float(item.get("similarity_score", 0.0) or 0.0)
        retrieved_cases.append({
            "case_id": item.get("case_id") or item.get("id") or f"case_{i + 1}",
            "title": item.get("title") or item.get("case_name") or "Untitled case",
            "year": item.get("year"),
            "jurisdiction": item.get("jurisdiction", "unknown"),
            "similarity_score": similarity,
            "context_fit": float(item.get("context_fit", similarity) or 0.0),
            "jurisdiction_score": float(item.get("jurisdiction_score", 0.0) or 0.0),
            "internal_confidence": float(item.get("internal_confidence", similarity) or 0.0),
            "uncertainty": float(item.get("uncertainty", max(0.0, 1.0 - similarity)) or 0.0),
            "trs": item.get("trs", similarity),
            "alignment_type": item.get("alignment_type", "neutral"),
            "justification": item.get("justification", "Retrieved by legal similarity search."),
            "spans": {
                "target_span": item.get("spans", {}).get("target_span", ""),
                "candidate_span": item.get("spans", {}).get("candidate_span", ""),
            },
        })

    overall = (
        sum(float(c["similarity_score"]) for c in retrieved_cases) / len(retrieved_cases)
        if retrieved_cases else 0.0
    )
    return {
        "source": "file-fallback",
        "candidates_searched": len(candidates),
        "retrieved": retrieved[:top_k],
        "retrieved_cases": retrieved_cases,
        "overall_external_coherence_score": overall,
        "short_summary": f"Found {len(retrieved_cases)} related cases using InLegalBERT fallback.",
    }
