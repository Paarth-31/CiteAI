"""Inference routes — model selection and similarity retrieval.

Exposes InLegalBERT and BioBERT (when enabled) through a unified endpoint
so the frontend can request results from either or both models.
Models are loaded once via ModelRegistry and reused across requests.

Endpoints:
  POST /api/inference/similar/<document_id>   — find similar cases
  GET  /api/inference/models                  — list available models
"""
from __future__ import annotations

import sys
from http import HTTPStatus
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import current_user, jwt_required

from ..extensions import model_registry
from ..models import Document

bp = Blueprint("inference", __name__, url_prefix="/api/inference")


def _ensure_project_root() -> None:
    project_root = Path(current_app.root_path).parent.parent
    root_str = str(project_root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)


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
    if current_app.config.get("BIOBERT_ENABLED", False):
        models.append({
            "key":     "biobert",
            "name":    current_app.config.get("BIOBERT_MODEL_NAME", "dmis-lab/biobert-base-cased-v1.2"),
            "enabled": True,
            "loaded":  "biobert" in model_registry.loaded_models(),
        })
    return jsonify({"models": models})


# ── Similarity retrieval ──────────────────────────────────────────────────────
@bp.post("/similar/<document_id>")
@jwt_required()
def find_similar(document_id: str):
    """Run similarity retrieval for a processed document.

    Body params:
      model   str   "legalbert" | "biobert" | "both"  (default: "legalbert")
      top_k   int   number of results  (default: from FAISS_TOP_K config)

    The document must already have ocr_text (i.e. been processed via
    POST /api/ocr/process/<id>) before calling this endpoint.
    """
    doc = Document.query.filter_by(
        id=document_id, user_id=current_user.id
    ).one_or_none()
    if doc is None:
        return jsonify({"error": "Document not found"}), HTTPStatus.NOT_FOUND

    if not doc.ocr_text:
        return jsonify({
            "error": "Document has no OCR text. Run /api/ocr/process/<id> first."
        }), HTTPStatus.BAD_REQUEST

    payload    = request.get_json(silent=True) or {}
    model_key  = (payload.get("model") or "legalbert").lower()
    top_k      = int(payload.get("top_k") or current_app.config.get("FAISS_TOP_K", 20))

    valid_keys = {"legalbert", "biobert", "both"}
    if model_key not in valid_keys:
        return jsonify({"error": f"model must be one of: {', '.join(valid_keys)}"}), HTTPStatus.BAD_REQUEST

    results = {}

    _ensure_project_root()

    # ── InLegalBERT ────────────────────────────────────────────────────────
    if model_key in ("legalbert", "both"):
        try:
            agent = model_registry.get_legalbert_agent()
            legalbert_results = _run_legalbert(agent, doc.ocr_text, top_k)
            results["legalbert"] = legalbert_results
        except Exception as exc:
            current_app.logger.exception("InLegalBERT inference failed: %s", exc)
            results["legalbert"] = {"error": str(exc)}

    # ── BioBERT ────────────────────────────────────────────────────────────
    if model_key in ("biobert", "both"):
        if not current_app.config.get("BIOBERT_ENABLED", False):
            results["biobert"] = {"error": "BioBERT is not enabled. Set BIOBERT_ENABLED=1 in .env."}
        else:
            try:
                agent = model_registry.get_biobert_agent()
                if agent is None:
                    results["biobert"] = {"error": "BioBERT failed to load"}
                else:
                    # TODO: Replace with team's BioBERT + FAISS retrieval once ready.
                    # The call should follow the same interface as _run_legalbert().
                    results["biobert"] = {
                        "status":  "pending",
                        "message": "BioBERT retrieval not yet implemented. "
                                   "Wire in team's updated agent here.",
                        "model":   agent.model_name,
                    }
            except Exception as exc:
                current_app.logger.exception("BioBERT inference failed: %s", exc)
                results["biobert"] = {"error": str(exc)}

    return jsonify({
        "document_id": document_id,
        "top_k":       top_k,
        "results":     results,
    })


# ── Internal helper ───────────────────────────────────────────────────────────
def _run_legalbert(agent, ocr_text: str, top_k: int) -> dict:
    """Run InLegalBERT retrieval on the document's OCR text.

    TODO: Once the team updates the FAISS layer, replace the in-memory
    dataset load here with a lookup against the persistent FAISS index
    stored in FAISS_INDEX_DIR. The agent should accept a pre-built index
    so we don't rebuild it on every call.
    """
    # Load the bundled baseline dataset for now.
    # This will be replaced by persistent FAISS index lookup.
    import json
    from pathlib import Path

    data_path = Path(__file__).resolve().parent.parent.parent.parent / "lexai" / "data" / "raw"
    candidates = []
    if data_path.exists():
        for jf in list(data_path.glob("*.json"))[:50]:  # limit for demo
            try:
                with open(jf, encoding="utf-8") as f:
                    candidates.append(json.load(f))
            except Exception:
                continue

    if not candidates:
        return {"warning": "No candidate documents found in lexai/data/raw/"}

    agent.load_dataset_from_dicts(candidates)
    agent.compute_all_embeddings(batch_size=8)

    # Use the OCR text as the query case
    query_case = {"text": ocr_text[:2000]}  # truncate for embedding
    retrieved = agent.retrieve_similar_cases(
        query_text=ocr_text[:2000], top_k=top_k
    )

    return {
        "candidates_searched": len(candidates),
        "retrieved":           retrieved[:top_k],
    }
