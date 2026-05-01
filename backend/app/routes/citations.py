"""Citation routes scoped to a document."""
from __future__ import annotations

from http import HTTPStatus

from flask import Blueprint, jsonify, request
from flask_jwt_extended import current_user, jwt_required

from ..extensions import db
from ..models import Citation, Document
from ..schemas import citation_to_dict

bp = Blueprint("citations", __name__, url_prefix="/api/documents/<document_id>/citations")


def _get_document_or_404(document_id: str) -> Document | None:
    return Document.query.filter_by(
        id=document_id, user_id=str(current_user.id)
    ).one_or_none()


@bp.get("")
@jwt_required()
def list_citations(document_id: str):
    doc = _get_document_or_404(document_id)
    if doc is None:
        return jsonify({"error": "Document not found"}), HTTPStatus.NOT_FOUND

    # Allow filtering by source model (legalbert / biobert)
    source_model = request.args.get("model")
    query = Citation.query.filter_by(document_id=doc.id)
    if source_model:
        query = query.filter_by(source_model=source_model)

    citations = query.order_by(
        Citation.trs_score.desc().nullslast(),
        Citation.year.desc().nullslast()
    ).all()
    return jsonify([citation_to_dict(c) for c in citations])


@bp.post("")
@jwt_required()
def create_citation(document_id: str):
    doc = _get_document_or_404(document_id)
    if doc is None:
        return jsonify({"error": "Document not found"}), HTTPStatus.NOT_FOUND

    payload = request.get_json(silent=True) or {}

    title = (payload.get("title") or "").strip()
    if not title:
        return jsonify({"error": "Title is required"}), HTTPStatus.BAD_REQUEST

    try:
        x_val    = float(payload.get("x", 50))
        y_val    = float(payload.get("y", 50))
    except (TypeError, ValueError):
        return jsonify({"error": "x and y must be numeric"}), HTTPStatus.BAD_REQUEST
    if not (0 <= x_val <= 100 and 0 <= y_val <= 100):
        return jsonify({"error": "x and y must be between 0 and 100"}), HTTPStatus.BAD_REQUEST

    try:
        count = int(payload.get("citations", 0))
        year  = int(payload.get("year", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "citations and year must be integers"}), HTTPStatus.BAD_REQUEST
    if count < 0:
        return jsonify({"error": "citations must be non-negative"}), HTTPStatus.BAD_REQUEST

    # Optional TRS/inference fields
    trs_score        = payload.get("trsScore")
    similarity_score = payload.get("similarityScore")
    evidence_span    = payload.get("evidenceSpan")
    source_model     = payload.get("sourceModel")

    citation = Citation(
        document_id      = doc.id,
        title            = title,
        x                = x_val,
        y                = y_val,
        citations        = count,
        year             = year,
        trs_score        = float(trs_score) if trs_score is not None else None,
        similarity_score = float(similarity_score) if similarity_score is not None else None,
        evidence_json    = evidence_span,
        source_model     = source_model,
    )
    db.session.add(citation)
    db.session.commit()
    return jsonify({"citation": citation_to_dict(citation)}), HTTPStatus.CREATED


@bp.put("/<citation_id>")
@jwt_required()
def update_citation(document_id: str, citation_id: str):
    doc = _get_document_or_404(document_id)
    if doc is None:
        return jsonify({"error": "Document not found"}), HTTPStatus.NOT_FOUND

    citation = Citation.query.filter_by(
        id=citation_id, document_id=doc.id
    ).one_or_none()
    if citation is None:
        return jsonify({"error": "Citation not found"}), HTTPStatus.NOT_FOUND

    payload = request.get_json(silent=True) or {}

    if "title" in payload:
        t = (payload["title"] or "").strip()
        if not t:
            return jsonify({"error": "Title cannot be empty"}), HTTPStatus.BAD_REQUEST
        citation.title = t

    for float_field in ("x", "y"):
        if float_field in payload:
            try:
                val = float(payload[float_field])
            except (TypeError, ValueError):
                return jsonify({"error": f"{float_field} must be numeric"}), HTTPStatus.BAD_REQUEST
            if not 0 <= val <= 100:
                return jsonify({"error": f"{float_field} must be between 0 and 100"}), HTTPStatus.BAD_REQUEST
            setattr(citation, float_field, val)

    if "citations" in payload:
        try:
            c = int(payload["citations"])
        except (TypeError, ValueError):
            return jsonify({"error": "citations must be an integer"}), HTTPStatus.BAD_REQUEST
        if c < 0:
            return jsonify({"error": "citations must be non-negative"}), HTTPStatus.BAD_REQUEST
        citation.citations = c

    if "year" in payload:
        try:
            citation.year = int(payload["year"])
        except (TypeError, ValueError):
            return jsonify({"error": "year must be an integer"}), HTTPStatus.BAD_REQUEST

    for opt_field in ("trsScore", "similarityScore"):
        model_field = "trs_score" if opt_field == "trsScore" else "similarity_score"
        if opt_field in payload:
            try:
                setattr(citation, model_field, float(payload[opt_field]))
            except (TypeError, ValueError):
                return jsonify({"error": f"{opt_field} must be numeric"}), HTTPStatus.BAD_REQUEST

    if "evidenceSpan" in payload:
        citation.evidence_json = payload["evidenceSpan"]
    if "sourceModel" in payload:
        citation.source_model = payload["sourceModel"]

    db.session.commit()
    return jsonify({"citation": citation_to_dict(citation)}), HTTPStatus.OK


@bp.delete("/<citation_id>")
@jwt_required()
def delete_citation(document_id: str, citation_id: str):
    doc = _get_document_or_404(document_id)
    if doc is None:
        return jsonify({"error": "Document not found"}), HTTPStatus.NOT_FOUND

    citation = Citation.query.filter_by(
        id=citation_id, document_id=doc.id
    ).one_or_none()
    if citation is None:
        return jsonify({"error": "Citation not found"}), HTTPStatus.NOT_FOUND

    db.session.delete(citation)
    db.session.commit()
    return jsonify({"success": True}), HTTPStatus.OK
