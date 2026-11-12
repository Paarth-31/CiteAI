"""OCR, RAG query, and citation graph routes."""
from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
import math
import uuid as _uuid

import networkx as nx
from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import current_user, jwt_required

from ..extensions import db
from ..models import BaselineCase, Citation, Document
from ..services.citation_graph_service import generate_citation_graph
from ..services.document_pipeline import (
    persist_graph_citations,
    run_internal_analysis_from_text,
    run_ocr_and_graph,
)
from ..services.paths import ensure_project_root

bp = Blueprint("ocr", __name__, url_prefix="/api/ocr")


def get_document_file_path(document: Document) -> Path | None:
    """Resolve the file system path for a document upload."""
    if not document.file_url:
        return None
    if document.file_url.startswith("/uploads/"):
        filename = document.file_url.replace("/uploads/", "")
        upload_folder = Path(current_app.config["UPLOAD_FOLDER"])
        return upload_folder / filename
    return Path(document.file_url)


@bp.post("/process/<document_id>")
@jwt_required()
def process_document(document_id: str):
    """Run OCR + citation graph once, caching results and Citation rows."""
    document = Document.query.filter_by(id=document_id, user_id=str(current_user.id)).one_or_none()
    if document is None:
        return jsonify({"error": "Document not found"}), HTTPStatus.NOT_FOUND

    force = request.args.get("force") in {"1", "true", "True", "yes", "on"}
    if document.ocr_text and document.citation_graph and not force:
        if document.status != "completed":
            document.update_status("completed")
            db.session.commit()
        return jsonify({
            "success": True,
            "already_processed": True,
            "document_id": document.id,
            "ocr_metadata": document.ocr_metadata,
        })

    file_path = get_document_file_path(document)
    if file_path is None or not file_path.exists():
        return jsonify({"error": "File not found"}), HTTPStatus.NOT_FOUND

    try:
        result = run_ocr_and_graph(document, file_path, force=force)
        return jsonify({
            "success": True,
            "document_id": document.id,
            **result,
        })
    except Exception as e:  # noqa: BLE001
        current_app.logger.exception("OCR processing failed")
        document.update_status("failed")
        db.session.commit()
        return jsonify({"error": f"OCR processing failed: {e}"}), HTTPStatus.INTERNAL_SERVER_ERROR


@bp.post("/query/<document_id>")
@jwt_required()
def query_document(document_id: str):
    """Answer a query using cached OCR text (fallback to live OCR)."""
    document = Document.query.filter_by(id=document_id, user_id=str(current_user.id)).one_or_none()
    if document is None:
        return jsonify({"error": "Document not found"}), HTTPStatus.NOT_FOUND

    payload = request.get_json(silent=True) or {}
    query = (payload.get("query") or "").strip()
    if not query:
        return jsonify({"error": "Query text is required"}), HTTPStatus.BAD_REQUEST

    try:
        ensure_project_root()
        from lexai.agents.query_pdf_rag_ocr import query_pdf_with_ocr, query_rag_from_text

        if document.ocr_text:
            result = query_rag_from_text(document.ocr_text, query, document.title)
        else:
            file_path = get_document_file_path(document)
            if file_path is None or not file_path.exists():
                return jsonify({"error": "Document file not found"}), HTTPStatus.NOT_FOUND
            result = query_pdf_with_ocr(str(file_path), query)

        return jsonify({
            "success": True,
            "query": query,
            "answer": result.get("Answer", ""),
            "title": result.get("Title", document.title),
        })
    except Exception as e:  # noqa: BLE001
        current_app.logger.exception("Query processing failed")
        return jsonify({"error": f"Query processing failed: {e}"}), HTTPStatus.INTERNAL_SERVER_ERROR


@bp.get("/citation-graph/<document_id>")
@jwt_required()
def get_citation_graph(document_id: str):
    """Return raw citation graph JSON (nodes & edges). Generate if missing."""
    document = Document.query.filter_by(id=document_id, user_id=str(current_user.id)).one_or_none()
    if document is None:
        return jsonify({"error": "Document not found"}), HTTPStatus.NOT_FOUND

    if document.citation_graph:
        return jsonify({"success": True, "graph": document.citation_graph})

    if not document.ocr_text:
        return jsonify({"error": "No OCR data available. Process the document first."}), HTTPStatus.BAD_REQUEST

    try:
        citation_graph = generate_citation_graph(document.ocr_text, document.title)
        document.citation_graph = citation_graph
        persist_graph_citations(document, citation_graph)
        db.session.commit()
        return jsonify({"success": True, "graph": citation_graph})
    except Exception as e:  # noqa: BLE001
        current_app.logger.exception("Failed to generate citation graph")
        db.session.rollback()
        return jsonify({"error": f"Failed to generate citation graph: {e}"}), HTTPStatus.INTERNAL_SERVER_ERROR


def _citation_lookup(document: Document) -> dict[str, Citation]:
    rows = Citation.query.filter_by(document_id=document.id, source_model="ocr").all()
    by_graph_id: dict[str, Citation] = {}
    for row in rows:
        evidence = row.evidence_json if isinstance(row.evidence_json, dict) else {}
        gid = evidence.get("graph_node_id")
        if gid:
            by_graph_id[str(gid)] = row
    return by_graph_id


@bp.get("/citation-nodes/<document_id>")
@jwt_required()
def get_citation_nodes(document_id: str):
    """Return positioned citation nodes — works for both uploaded docs and baseline slugs."""
    document = None
    try:
        _uuid.UUID(document_id)
        document = Document.query.filter_by(id=document_id, user_id=str(current_user.id)).one_or_none()
    except (ValueError, Exception):
        pass

    saved_by_graph_id: dict[str, Citation] = {}
    if document is not None:
        if not document.citation_graph:
            if not document.ocr_text:
                return jsonify({"nodes": [], "edges": [], "total_nodes": 0}), HTTPStatus.OK
            try:
                graph = generate_citation_graph(document.ocr_text, document.title)
                document.citation_graph = graph
                persist_graph_citations(document, graph)
                db.session.commit()
            except Exception as e:
                current_app.logger.error(f"Citation graph generation failed: {e}")
                db.session.rollback()
                return jsonify({"nodes": [], "edges": [], "total_nodes": 0}), HTTPStatus.OK
        graph = document.citation_graph or {}
        saved_by_graph_id = _citation_lookup(document)
    else:
        case = BaselineCase.query.filter_by(slug=document_id).one_or_none()
        if case is None:
            return jsonify({"error": "Document not found"}), HTTPStatus.NOT_FOUND
        try:
            graph = generate_citation_graph(case.full_text, case.title)
        except Exception as e:
            current_app.logger.exception(f"Graph generation failed for {document_id}")
            return jsonify({"error": f"Graph generation failed: {e}"}), HTTPStatus.INTERNAL_SERVER_ERROR

    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    total_nodes = len(nodes)

    if total_nodes == 0:
        return jsonify({
            "nodes": [], "edges": [],
            "total_nodes": 0, "filtered_nodes": 0,
            "showing_top": 0, "has_more": False,
        })

    limit = min(max(request.args.get("limit", type=int) or 50, 1), 200)
    min_citations = request.args.get("min_citations", default=0, type=int) or 0
    year_filter = request.args.get("year", type=int)

    citation_counts: dict[str, int] = {}
    for edge in edges:
        src = edge.get("source")
        tgt = edge.get("target")
        if not src or not tgt:
            continue
        citation_counts[tgt] = citation_counts.get(tgt, 0) + 1

    for n in nodes:
        n["citation_count"] = citation_counts.get(n.get("id"), 0)

    filtered = [n for n in nodes if n.get("citation_count", 0) >= min_citations]
    if year_filter is not None:
        filtered = [n for n in filtered if n.get("year") == year_filter]

    filtered.sort(key=lambda n: n.get("citation_count", 0), reverse=True)
    visible = filtered[:limit]
    visible_ids = {n.get("id") for n in visible}

    G = nx.DiGraph()
    for n in visible:
        G.add_node(n.get("id"))
    for e in edges:
        src = e.get("source")
        tgt = e.get("target")
        if src in visible_ids and tgt in visible_ids:
            G.add_edge(src, tgt)

    n_count = max(len(G), 1)
    k = 1.5 / math.sqrt(n_count)
    pos = nx.spring_layout(G, k=k, iterations=200, seed=42, threshold=1e-4)
    positions: dict[str, dict[str, float]] = {}

    if pos:
        xs = [p[0] for p in pos.values()]
        ys = [p[1] for p in pos.values()]
        span_x = (max(xs) - min(xs)) or 1.0
        span_y = (max(ys) - min(ys)) or 1.0
        for nid, (px, py) in pos.items():
            positions[nid] = {
                "x": float(max(5, min(95, 10 + 80 * (px - min(xs)) / span_x))),
                "y": float(max(5, min(95, 10 + 80 * (py - min(ys)) / span_y))),
            }

    id_map: dict[str, str] = {}
    formatted_nodes = []
    for n in visible:
        gid = n.get("id")
        saved = saved_by_graph_id.get(str(gid))
        layout = positions.get(gid, {"x": 50.0, "y": 50.0})
        node_id = str(saved.id) if saved is not None else gid
        id_map[gid] = node_id
        x_val, y_val = layout["x"], layout["y"]
        if saved is not None and (saved.x, saved.y) != (50.0, 50.0):
            x_val, y_val = float(saved.x), float(saved.y)
        formatted_nodes.append({
            "id": node_id,
            "graphId": gid,
            "title": n.get("title", "Unknown"),
            "x": x_val,
            "y": y_val,
            "citations": n.get("citation_count", 0),
            "year": n.get("year") or 0,
            "trsScore": saved.trs_score if saved is not None else None,
            "similarityScore": saved.similarity_score if saved is not None else None,
        })

    visible_edges = []
    for e in edges:
        src = e.get("source")
        tgt = e.get("target")
        if src in visible_ids and tgt in visible_ids:
            visible_edges.append({
                "source": id_map.get(src, src),
                "target": id_map.get(tgt, tgt),
            })

    return jsonify({
        "nodes": formatted_nodes,
        "edges": visible_edges,
        "total_nodes": total_nodes,
        "filtered_nodes": len(filtered),
        "showing_top": len(visible),
        "has_more": len(filtered) > len(visible),
    })


@bp.get("/internal-analysis/<document_id>")
@jwt_required()
def get_internal_analysis(document_id: str):
    """Return internal coherence analysis. Compute from cached OCR text if needed."""
    document = Document.query.filter_by(id=document_id, user_id=str(current_user.id)).one_or_none()
    if document is None:
        return jsonify({"error": "Document not found"}), HTTPStatus.NOT_FOUND

    force = request.args.get("force") in {"1", "true", "True", "yes", "on"}

    if document.internal_analysis and not force:
        return jsonify({"success": True, "analysis": document.internal_analysis})

    if not document.ocr_text:
        return jsonify({
            "error": "No OCR data available. Process the document first.",
        }), HTTPStatus.BAD_REQUEST

    analysis = run_internal_analysis_from_text(document)
    if analysis is None:
        return jsonify({
            "error": "Internal analysis failed. Check GEMINI_API_KEY and try again.",
        }), HTTPStatus.INTERNAL_SERVER_ERROR

    return jsonify({"success": True, "analysis": analysis})
