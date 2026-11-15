"""Inference routes for model selection and similarity retrieval."""
from __future__ import annotations

from http import HTTPStatus
from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import current_user, jwt_required

from ..extensions import db, model_registry
from ..models import CorpusChunk, CorpusDocument, Document
from ..services.document_pipeline import cached_inference_payload, persist_inference_scores, run_internal_analysis_from_text
from ..services.legal_pipeline import retrieve_and_score

bp = Blueprint("inference", __name__, url_prefix="/api/inference")


# ── Available models ──────────────────────────────────────────────────────────
@bp.get("/models")
def list_models():
    """Return which models are available and loaded."""
    models = [
        {
            "key":     "legal-pipeline",
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
    try:
        top_k = int(payload.get("top_k") or current_app.config.get("FAISS_TOP_K", 20))
    except (TypeError, ValueError):
        return jsonify({"error": "top_k must be an integer"}), HTTPStatus.BAD_REQUEST
    if not 1 <= top_k <= 100:
        return jsonify({"error": "top_k must be between 1 and 100"}), HTTPStatus.BAD_REQUEST
    force = bool(payload.get("force")) or request.args.get("force") in {"1", "true", "True"}

    if not force:
        cached = cached_inference_payload(doc)
        saved_k = ((doc.ocr_metadata or {}).get("external_inference") or {}).get("top_k")
        if cached and cached.get("retrieved_cases") and (saved_k is None or int(saved_k) == top_k):
            return jsonify({
                "document_id": document_id,
                "top_k": top_k,
                "results": {"legal": cached},
            })

    try:
        internal = doc.internal_analysis or run_internal_analysis_from_text(doc) or {"coherence_score": 0.0}
        keywords = (doc.ocr_metadata or {}).get("keywords") or []
        result = retrieve_and_score(
            doc.ocr_text, doc.title, keywords, internal, model_registry, db.session,
            CorpusChunk, CorpusDocument, top_k, owner_id=doc.user_id,
        )
        persist_inference_scores(
            doc, result["retrieved_cases"], overall=result["overall_external_coherence_score"],
            short_summary=result["short_summary"], source=result["source"], top_k=top_k,
        )
        db.session.commit()
        results = {"legal": {**result, "cached": False}}
    except Exception as exc:
        current_app.logger.exception("Corpus inference failed: %s", exc)
        db.session.rollback()
        results = {"legal": {"error": str(exc)}}

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
        "results": {"legal": cached},
    })
