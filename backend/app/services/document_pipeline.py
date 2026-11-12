"""Single document processing pipeline.

Flow:
  1. OCR / text extract  (lexai.agents.ocr_agent.process_pdf)
  2. Citation graph      (CitationGraphBuilder.build_from_text)
  3. Persist Citation rows for graph nodes (positions + later scores)
  4. Internal analysis uses cached OCR text — never re-runs OCR
  5. External inference persists TRS / similarity onto Citation rows
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import current_app

from ..extensions import db
from ..models import Citation, Document
from .citation_graph_service import generate_citation_graph
from .paths import ensure_project_root


def _as_trs(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, dict):
        value = value.get("score")
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _norm_title(title: str) -> str:
    return " ".join((title or "").lower().split())


def persist_graph_citations(document: Document, graph: dict[str, Any]) -> int:
    """Upsert OCR graph nodes as Citation rows so scores/positions can be stored."""
    nodes = graph.get("nodes") or []
    edges = graph.get("edges") or []

    cited_counts: dict[str, int] = {}
    for edge in edges:
        tgt = edge.get("target")
        if tgt:
            cited_counts[tgt] = cited_counts.get(tgt, 0) + 1

    existing = Citation.query.filter_by(document_id=document.id, source_model="ocr").all()
    by_graph_id: dict[str, Citation] = {}
    for row in existing:
        evidence = row.evidence_json if isinstance(row.evidence_json, dict) else {}
        gid = evidence.get("graph_node_id")
        if gid:
            by_graph_id[gid] = row

    keep_ids: set[str] = set()
    for node in nodes:
        graph_id = str(node.get("id") or "")
        if not graph_id:
            continue
        keep_ids.add(graph_id)
        title = (node.get("title") or "Untitled").strip()[:512]
        year = node.get("year")
        try:
            year_val = int(year) if year is not None else None
        except (TypeError, ValueError):
            year_val = None

        evidence = {
            "graph_node_id": graph_id,
            "text": (node.get("text") or "")[:500],
        }
        row = by_graph_id.get(graph_id)
        if row is None:
            row = Citation(
                document_id=document.id,
                title=title,
                x=50.0,
                y=50.0,
                citations=cited_counts.get(graph_id, 0),
                year=year_val,
                source_model="ocr",
                evidence_json=evidence,
            )
            db.session.add(row)
        else:
            row.title = title
            row.citations = cited_counts.get(graph_id, 0)
            row.year = year_val
            row.evidence_json = evidence

    for graph_id, row in by_graph_id.items():
        if graph_id not in keep_ids:
            db.session.delete(row)

    return len(keep_ids)


def persist_inference_scores(
    document: Document,
    retrieved_cases: list[dict[str, Any]],
    *,
    overall: float,
    short_summary: str,
    source: str,
    top_k: int,
) -> None:
    """Save external-inference cases and overlay scores onto matching OCR citations."""
    Citation.query.filter_by(document_id=document.id, source_model="legalbert").delete(
        synchronize_session=False
    )

    ocr_rows = Citation.query.filter_by(document_id=document.id, source_model="ocr").all()
    ocr_by_title = {_norm_title(row.title): row for row in ocr_rows}

    for i, item in enumerate(retrieved_cases):
        title = (item.get("title") or item.get("case_name") or "Untitled case").strip()[:512]
        trs = _as_trs(item.get("trs"))
        try:
            similarity = float(item.get("similarity_score") or 0.0)
        except (TypeError, ValueError):
            similarity = 0.0
        if trs is None:
            trs = similarity

        year = item.get("year")
        try:
            year_val = int(year) if year is not None else None
        except (TypeError, ValueError):
            year_val = None

        evidence = {
            "case_id": item.get("case_id") or item.get("id") or f"case_{i + 1}",
            "justification": item.get("justification"),
            "spans": item.get("spans") or {},
            "context_fit": item.get("context_fit"),
            "jurisdiction": item.get("jurisdiction"),
            "jurisdiction_score": item.get("jurisdiction_score"),
            "internal_confidence": item.get("internal_confidence"),
            "uncertainty": item.get("uncertainty"),
            "alignment_type": item.get("alignment_type"),
            "trs": item.get("trs"),
        }
        db.session.add(
            Citation(
                document_id=document.id,
                title=title,
                x=50.0,
                y=50.0,
                citations=0,
                year=year_val,
                similarity_score=similarity,
                trs_score=trs,
                source_model="legalbert",
                evidence_json=evidence,
            )
        )

        ocr_row = ocr_by_title.get(_norm_title(title))
        if ocr_row is not None:
            ocr_row.similarity_score = similarity
            ocr_row.trs_score = trs

    meta = dict(document.ocr_metadata or {})
    meta["external_inference"] = {
        "overall_external_coherence_score": overall,
        "short_summary": short_summary,
        "source": source,
        "top_k": top_k,
    }
    document.ocr_metadata = meta


def cached_inference_payload(document: Document) -> dict[str, Any] | None:
    """Rebuild the frontend inference response from saved Citation rows."""
    meta = (document.ocr_metadata or {}).get("external_inference") or {}
    rows = (
        Citation.query.filter_by(document_id=document.id, source_model="legalbert")
        .order_by(Citation.trs_score.desc().nullslast())
        .all()
    )
    if not rows and not meta:
        return None

    retrieved = []
    for row in rows:
        evidence = row.evidence_json if isinstance(row.evidence_json, dict) else {}
        retrieved.append({
            "case_id": evidence.get("case_id") or str(row.id),
            "title": row.title,
            "year": row.year,
            "jurisdiction": evidence.get("jurisdiction", "unknown"),
            "similarity_score": row.similarity_score or 0.0,
            "context_fit": evidence.get("context_fit") or row.similarity_score or 0.0,
            "jurisdiction_score": evidence.get("jurisdiction_score") or 0.0,
            "internal_confidence": evidence.get("internal_confidence") or row.similarity_score or 0.0,
            "uncertainty": evidence.get("uncertainty") or 0.0,
            "trs": evidence.get("trs") if evidence.get("trs") is not None else (row.trs_score or 0.0),
            "alignment_type": evidence.get("alignment_type") or "neutral",
            "justification": evidence.get("justification") or "Retrieved by legal similarity search.",
            "spans": evidence.get("spans") or {"target_span": "", "candidate_span": ""},
        })

    overall = meta.get("overall_external_coherence_score")
    if overall is None and retrieved:
        overall = sum(float(c["similarity_score"]) for c in retrieved) / len(retrieved)

    return {
        "source": meta.get("source", "cache"),
        "retrieved": retrieved,
        "retrieved_cases": retrieved,
        "overall_external_coherence_score": float(overall or 0.0),
        "short_summary": meta.get("short_summary") or f"Cached {len(retrieved)} related cases.",
        "cached": True,
    }


def invalidate_stale_results(document: Document) -> None:
    """Drop anything computed from the document's *old* OCR text.

    Called before a forced re-OCR commits new text/metadata/graph, so that
    inference rows and internal analysis from the previous text are never
    served as if they came from the new one.
    """
    Citation.query.filter_by(document_id=document.id, source_model="legalbert").delete(
        synchronize_session=False
    )
    document.internal_analysis = None


def run_ocr_and_graph(document: Document, file_path: Path, *, force: bool = False) -> dict[str, Any]:
    """OCR + citation graph + persist graph citations. Does not run inference."""
    ensure_project_root()
    from lexai.agents.ocr_agent import process_pdf

    document.update_status("processing")
    db.session.commit()

    ocr_result = process_pdf(str(file_path))
    ocr_text = ocr_result.get("full_text") or ocr_result.get("raw_text") or ""
    citations = ocr_result.get("citations") or []
    articles = ocr_result.get("articles") or []
    keywords = ocr_result.get("keywords") or []
    stats = ocr_result.get("stats") or {
        "num_pages": len(ocr_result.get("pages") or []),
        "num_citations": len(citations),
        "num_articles": len(articles),
        "num_keywords": len(keywords),
    }

    citation_graph = generate_citation_graph(ocr_text, document.title)

    # If OCR is being re-run on a document that already has results, those
    # results (legalbert inference rows + internal analysis) were computed
    # from the OLD text. Invalidate them before the new text/graph is
    # committed, or they would be served as if they matched the new text.
    if force and (document.ocr_text or document.internal_analysis):
        invalidate_stale_results(document)

    document.ocr_text = ocr_text
    document.ocr_metadata = {
        "citations": citations,
        "articles": articles,
        "keywords": keywords,
        "stats": stats,
        "page_count": stats.get("num_pages", 0),
    }
    document.citation_graph = citation_graph
    persist_graph_citations(document, citation_graph)
    document.update_status("completed")
    db.session.commit()

    return {
        "ocr_metadata": document.ocr_metadata,
        "num_nodes": len(citation_graph.get("nodes") or []),
        "num_edges": len(citation_graph.get("edges") or []),
        "num_citations_saved": len(citation_graph.get("nodes") or []),
    }


def run_internal_analysis_from_text(document: Document) -> dict[str, Any] | None:
    """Compute internal coherence from cached OCR text and store it."""
    if not document.ocr_text:
        return None
    try:
        ensure_project_root()
        from lexai.agents.multi_model_internal_coherence_agent_light_pdf import (
            run_internal_coherence_from_text,
        )

        analysis = run_internal_coherence_from_text(
            document.ocr_text,
            title=document.title,
            file_name=document.title,
        )
        document.internal_analysis = analysis
        db.session.commit()
        return analysis
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("Internal analysis failed: %s", exc)
        return None
