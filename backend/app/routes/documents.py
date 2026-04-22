"""Document management routes.

Key change from previous version:
  File upload (POST /upload) now saves the file and returns immediately.
  OCR + citation graph processing is deferred — the frontend triggers it
  separately via POST /api/ocr/process/<id>. This removes the biggest
  latency bottleneck where a large PDF would block the upload response
  for 10–30 seconds.
"""
from __future__ import annotations

import uuid
from http import HTTPStatus
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import current_user, jwt_required
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models import Document
from ..schemas import document_to_dict

bp = Blueprint("documents", __name__, url_prefix="/api/documents")

_ALLOWED_MIME = {"application/pdf"}


# ── List ──────────────────────────────────────────────────────────────────────
@bp.get("")
@jwt_required()
def list_documents():
    query = Document.query.filter_by(user_id=current_user.id)

    search = request.args.get("search", "").strip()
    if search:
        query = query.filter(Document.title.ilike(f"%{search}%"))

    status = request.args.get("status", "").strip()
    if status:
        query = query.filter(Document.status == status)

    limit  = min(int(request.args.get("limit", 20)), 100)
    offset = max(int(request.args.get("offset", 0)), 0)

    docs = (
        query.order_by(Document.upload_date.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return jsonify([document_to_dict(d) for d in docs])


# ── Upload (fast path — OCR deferred) ─────────────────────────────────────────
@bp.post("/upload")
@jwt_required()
def upload_document_file():
    """Save uploaded PDF and return immediately.

    OCR, citation graph, and inference are NOT run here.
    Call POST /api/ocr/process/<id> after upload to trigger processing.
    This keeps upload response time under 500 ms regardless of file size.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file in request"}), HTTPStatus.BAD_REQUEST

    file = request.files["file"]
    if not file or file.filename == "":
        return jsonify({"error": "No file selected"}), HTTPStatus.BAD_REQUEST

    if file.mimetype not in _ALLOWED_MIME:
        return jsonify({"error": "Only PDF files are allowed"}), HTTPStatus.BAD_REQUEST

    upload_folder = Path(current_app.config["UPLOAD_FOLDER"])
    upload_folder.mkdir(parents=True, exist_ok=True)

    safe_name   = secure_filename(file.filename) or "document.pdf"
    stored_name = f"{uuid.uuid4().hex}_{safe_name}"
    storage_path = upload_folder / stored_name
    file.save(storage_path)

    document = Document(
        title    = safe_name.rsplit(".", 1)[0],
        file_url = f"/uploads/{stored_name}",
        file_size = storage_path.stat().st_size,
        status   = "pending",           # will move to "processing" → "completed"
        user_id  = current_user.id,
    )
    db.session.add(document)
    db.session.commit()

    return jsonify({
        "document": document_to_dict(document),
        "message":  "File uploaded. Call /api/ocr/process/<id> to start processing.",
    }), HTTPStatus.CREATED


# ── Create (URL-based, no file) ───────────────────────────────────────────────
@bp.post("")
@jwt_required()
def create_document():
    payload   = request.get_json(silent=True) or {}
    title     = (payload.get("title") or "").strip()
    file_url  = (payload.get("fileUrl") or "").strip()
    file_size = payload.get("fileSize")

    if not title:
        return jsonify({"error": "Title is required"}), HTTPStatus.BAD_REQUEST
    if not file_url:
        return jsonify({"error": "fileUrl is required"}), HTTPStatus.BAD_REQUEST

    try:
        file_size_val = int(file_size)
        if file_size_val <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "fileSize must be a positive integer"}), HTTPStatus.BAD_REQUEST

    doc = Document(
        title=title, file_url=file_url,
        file_size=file_size_val, user_id=current_user.id,
    )
    db.session.add(doc)
    db.session.commit()
    return jsonify({"document": document_to_dict(doc)}), HTTPStatus.CREATED


# ── Get ───────────────────────────────────────────────────────────────────────
@bp.get("/<document_id>")
@jwt_required()
def get_document(document_id: str):
    doc = _get_or_404(document_id)
    if doc is None:
        return jsonify({"error": "Document not found"}), HTTPStatus.NOT_FOUND
    return jsonify({"document": document_to_dict(doc, include_citations=True, include_ocr=True)})


# ── Update ────────────────────────────────────────────────────────────────────
@bp.put("/<document_id>")
@jwt_required()
def update_document(document_id: str):
    doc = _get_or_404(document_id)
    if doc is None:
        return jsonify({"error": "Document not found"}), HTTPStatus.NOT_FOUND

    payload = request.get_json(silent=True) or {}

    if "title" in payload:
        title = (payload["title"] or "").strip()
        if not title:
            return jsonify({"error": "Title cannot be empty"}), HTTPStatus.BAD_REQUEST
        doc.title = title

    if "status" in payload:
        status = (payload["status"] or "").strip()
        if not status:
            return jsonify({"error": "Status cannot be empty"}), HTTPStatus.BAD_REQUEST
        doc.update_status(status)

    db.session.commit()
    return jsonify({"document": document_to_dict(doc)}), HTTPStatus.OK


# ── Delete ────────────────────────────────────────────────────────────────────
@bp.delete("/<document_id>")
@jwt_required()
def delete_document(document_id: str):
    doc = _get_or_404(document_id)
    if doc is None:
        return jsonify({"error": "Document not found"}), HTTPStatus.NOT_FOUND

    # Remove stored file
    if doc.file_url and doc.file_url.startswith("/uploads/"):
        file_path = Path(current_app.config["UPLOAD_FOLDER"]) / doc.file_url.replace("/uploads/", "")
        if file_path.exists():
            try:
                file_path.unlink()
            except OSError:
                pass  # non-fatal

    db.session.delete(doc)
    db.session.commit()
    return jsonify({"success": True}), HTTPStatus.OK


# ── Helper ────────────────────────────────────────────────────────────────────
def _get_or_404(document_id: str):
    return Document.query.filter_by(
        id=document_id, user_id=current_user.id
    ).one_or_none()
