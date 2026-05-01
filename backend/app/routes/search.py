"""Global search — powered by PostgreSQL full-text search (tsvector/tsquery).

Endpoints:
  GET  /api/search?q=<term>             — search baseline cases + user docs
  GET  /api/search/baseline             — list all baseline cases (sidebar)
  GET  /api/search/baseline/<slug>      — full data for one baseline case
  GET  /api/search/baseline/<slug>/citation-nodes  — citation graph for a case
"""
from __future__ import annotations

import math
from http import HTTPStatus

import networkx as nx
from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import current_user, verify_jwt_in_request
from sqlalchemy import func, text

from ..extensions import db
from ..models import BaselineCase, Document

bp = Blueprint("search", __name__, url_prefix="/api/search")


# ── Global search ─────────────────────────────────────────────────────────────

@bp.get("")
def global_search():
    """
    Full-text search using PostgreSQL tsvector.

    Falls back to ILIKE trigram if query is too short for tsquery.
    Returns baseline cases always; user documents if JWT present.
    """
    q = (request.args.get("q") or "").strip()
    if not q or len(q) < 2:
        return jsonify({"error": "Query must be at least 2 characters"}), HTTPStatus.BAD_REQUEST

    results = []

    # ── Baseline cases — tsvector FTS with ranking ───────────────────────────
    try:
        # to_tsquery requires proper lexemes; websearch_to_tsquery is forgiving
        cases = (
            db.session.query(
                BaselineCase,
                func.ts_rank(
                    BaselineCase.full_text_tsv,
                    func.websearch_to_tsquery("english", q),
                ).label("rank"),
            )
            .filter(
                BaselineCase.full_text_tsv.op("@@")(
                    func.websearch_to_tsquery("english", q)
                )
            )
            .order_by(text("rank DESC"))
            .limit(10)
            .all()
        )
    except Exception:
        # Fallback to ILIKE if tsvector not yet populated
        cases = [
            (c, 0.0)
            for c in BaselineCase.query.filter(
                BaselineCase.title.ilike(f"%{q}%") |
                BaselineCase.full_text.ilike(f"%{q}%")
            ).limit(10).all()
        ]

    for case, rank in cases:
        snippet = _extract_snippet(case.full_text, q)
        results.append({
            "id":        str(case.id),
            "slug":      case.slug,
            "title":     case.title,
            "type":      "baseline",
            "rank":      float(rank),
            "snippet":   snippet,
            "stats":     case.stats or {},
            "citations": (case.citations or [])[:5],
            "keywords":  (case.keywords or [])[:6],
        })

    # ── User documents — only if authenticated ───────────────────────────────
    try:
        verify_jwt_in_request(optional=True)
        if current_user:
            uid = current_user.id_str
            try:
                docs = (
                    db.session.query(
                        Document,
                        func.ts_rank(
                            Document.ocr_text_tsv,
                            func.websearch_to_tsquery("english", q),
                        ).label("rank"),
                    )
                    .filter(
                        Document.user_id == uid,
                        Document.ocr_text_tsv.op("@@")(
                            func.websearch_to_tsquery("english", q)
                        ),
                    )
                    .order_by(text("rank DESC"))
                    .limit(10)
                    .all()
                )
            except Exception:
                docs = [
                    (d, 0.0)
                    for d in Document.query.filter(
                        Document.user_id == uid,
                        Document.title.ilike(f"%{q}%"),
                    ).limit(10).all()
                ]

            for doc, rank in docs:
                results.append({
                    "id":     str(doc.id),
                    "title":  doc.title,
                    "type":   "document",
                    "rank":   float(rank),
                    "status": doc.status,
                    "snippet": _extract_snippet(doc.ocr_text or "", q),
                })
    except Exception:
        pass   # unauthenticated — baseline results only

    # Sort combined results by rank
    results.sort(key=lambda r: r.get("rank", 0), reverse=True)

    return jsonify({"results": results, "count": len(results)})


# ── Baseline list (sidebar) ───────────────────────────────────────────────────

@bp.get("/baseline")
def list_baseline_cases():
    """Return all baseline cases ordered alphabetically — for document explorer."""
    cases = BaselineCase.query.order_by(BaselineCase.title).all()
    return jsonify([{
        "id":       str(c.id),
        "slug":     c.slug,
        "title":    c.title,
        "stats":    c.stats or {},
        "keywords": (c.keywords or [])[:8],
    } for c in cases])


# ── Single baseline case ──────────────────────────────────────────────────────

@bp.get("/baseline/<slug>")
def get_baseline_case(slug: str):
    """Return full text + metadata for one baseline case."""
    case = BaselineCase.query.filter_by(slug=slug).one_or_none()
    if not case:
        return jsonify({"error": "Case not found"}), HTTPStatus.NOT_FOUND

    return jsonify({
        "id":        str(case.id),
        "slug":      case.slug,
        "title":     case.title,
        "full_text": case.full_text,
        "citations": case.citations or [],
        "articles":  case.articles  or [],
        "keywords":  case.keywords  or [],
        "stats":     case.stats     or {},
    })


# ── Baseline citation graph ───────────────────────────────────────────────────

@bp.get("/baseline/<slug>/citation-nodes")
def baseline_citation_nodes(slug: str):
    """Build and return a positioned citation graph for a baseline case.

    Uses the same CitationGraphBuilder + NetworkX force-directed layout
    as the main /api/ocr/citation-nodes/<id> endpoint so the frontend
    receives identical shape regardless of source.
    """
    case = BaselineCase.query.filter_by(slug=slug).one_or_none()
    if not case:
        return jsonify({"error": "Case not found"}), HTTPStatus.NOT_FOUND

    try:
        from ..services.citation_graph_service import generate_citation_graph
        graph = generate_citation_graph(case.full_text, case.title)
    except Exception as exc:
        current_app.logger.exception("Citation graph generation failed for %s", slug)
        return jsonify({"error": f"Graph generation failed: {exc}"}), HTTPStatus.INTERNAL_SERVER_ERROR

    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    if not nodes:
        return jsonify({
            "nodes": [], "edges": [],
            "total_nodes": 0, "filtered_nodes": 0,
            "showing_top": 0, "has_more": False,
        })

    # Force-directed layout via NetworkX (same as ocr.py)
    G = nx.DiGraph()
    for n in nodes:
        G.add_node(n["id"])
    for e in edges:
        if e.get("source") and e.get("target"):
            G.add_edge(e["source"], e["target"])

    n_count = max(len(G), 1)
    k = 1.5 / math.sqrt(n_count)
    raw_pos = nx.spring_layout(G, k=k, iterations=200, seed=42, threshold=1e-4)

    positions: dict = {}
    if raw_pos:
        xs = [p[0] for p in raw_pos.values()]
        ys = [p[1] for p in raw_pos.values()]
        span_x = (max(xs) - min(xs)) or 1.0
        span_y = (max(ys) - min(ys)) or 1.0
        for nid, (px, py) in raw_pos.items():
            positions[nid] = {
                "x": max(5.0, min(95.0, 10 + 80 * (px - min(xs)) / span_x)),
                "y": max(5.0, min(95.0, 10 + 80 * (py - min(ys)) / span_y)),
            }

    citation_counts: dict = {}
    for e in edges:
        tgt = e.get("target")
        if tgt:
            citation_counts[tgt] = citation_counts.get(tgt, 0) + 1

    formatted = [
        {
            "id":        n["id"],
            "title":     n.get("title", "Unknown"),
            "x":         positions.get(n["id"], {"x": 50.0})["x"],
            "y":         positions.get(n["id"], {"y": 50.0})["y"],
            "citations": citation_counts.get(n["id"], 0),
            "year":      n.get("year") or 0,
        }
        for n in nodes
    ]

    return jsonify({
        "nodes":          formatted,
        "edges":          edges,
        "total_nodes":    len(nodes),
        "filtered_nodes": len(nodes),
        "showing_top":    len(nodes),
        "has_more":       False,
    })


# ── Vector similarity search (pgvector) ──────────────────────────────────────

@bp.get("/similar-documents/<document_id>")
def similar_documents(document_id: str):
    """Find documents whose InLegalBERT embedding is closest to this one.

    Uses pgvector cosine distance (<=>).
    Requires the document's legal_embedding to have been populated by
    POST /api/inference/similar/<id> first.
    """
    try:
        verify_jwt_in_request()
    except Exception:
        return jsonify({"error": "Authentication required"}), HTTPStatus.UNAUTHORIZED

    doc = Document.query.filter_by(
        id=document_id, user_id=current_user.id_str
    ).one_or_none()
    if not doc:
        return jsonify({"error": "Document not found"}), HTTPStatus.NOT_FOUND
    if doc.legal_embedding is None:
        return jsonify({
            "error": "No embedding yet. Run /api/inference/similar/<id> first."
        }), HTTPStatus.BAD_REQUEST

    limit = min(int(request.args.get("limit", 5)), 20)

    # cosine distance in pgvector: <=> operator
    similar = (
        db.session.query(
            Document,
            Document.legal_embedding.op("<=>")(doc.legal_embedding).label("distance"),
        )
        .filter(
            Document.id != doc.id,
            Document.user_id == current_user.id_str,
            Document.legal_embedding.isnot(None),
        )
        .order_by(text("distance ASC"))
        .limit(limit)
        .all()
    )

    return jsonify({
        "source_document": str(doc.id),
        "results": [
            {
                "id":       str(d.id),
                "title":    d.title,
                "status":   d.status,
                "distance": float(dist),
                "similarity": round(1 - float(dist), 4),
            }
            for d, dist in similar
        ],
    })


# ── Helper ────────────────────────────────────────────────────────────────────

def _extract_snippet(text: str, query: str, context: int = 150) -> str:
    """Return a short snippet around the first occurrence of query in text."""
    if not text:
        return ""
    idx = text.lower().find(query.lower())
    if idx < 0:
        return text[:context].strip() + "…"
    start = max(0, idx - context // 2)
    end   = min(len(text), idx + context // 2)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return prefix + text[start:end].strip() + suffix
