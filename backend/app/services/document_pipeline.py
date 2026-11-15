"""Persistence boundary for the canonical backend document pipeline."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import current_app

from ..extensions import db
from ..models import Citation, Document
from .legal_pipeline import (
    build_citation_graph, build_embedding_material, chunk_text, extract_pdf,
    detailed_internal_analysis, internal_score, retrieve_and_score,
)


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
    Citation.query.filter_by(document_id=document.id, source_model="legal-pipeline").delete(
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
                source_model="legal-pipeline",
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
        Citation.query.filter_by(document_id=document.id, source_model="legal-pipeline")
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
    Citation.query.filter_by(document_id=document.id, source_model="legal-pipeline").delete(
        synchronize_session=False
    )
    document.internal_analysis = None


def run_document_pipeline(document: Document, file_path: Path, *, force: bool = False, top_k: int = 20) -> dict[str, Any]:
    """Run every analysis stage exactly once and persist one coherent result."""
    from ..extensions import model_registry
    from ..models import CorpusChunk, CorpusDocument
    document.update_status("processing")
    db.session.commit()
    if document.ocr_text and not force and "citations" in (document.ocr_metadata or {}):
        old = document.ocr_metadata or {}
        ocr_result = {
            "title": old.get("title") or document.title,
            "full_text": document.ocr_text,
            "pages": old.get("pages") or [],
            "citations": old.get("citations") or [],
            "articles": old.get("articles") or [],
            "keywords": old.get("keywords") or [],
            "stats": old.get("stats") or {},
        }
    else:
        ocr_result = extract_pdf(file_path)
    ocr_text = ocr_result["full_text"]
    citations = ocr_result.get("citations") or []
    articles = ocr_result.get("articles") or []
    keywords = ocr_result.get("keywords") or []
    stats = ocr_result.get("stats") or {
        "num_pages": len(ocr_result.get("pages") or []),
        "num_citations": len(citations),
        "num_articles": len(articles),
        "num_keywords": len(keywords),
    }

    citation_graph = build_citation_graph(ocr_result["title"], ocr_text, citations)
    chunks = chunk_text(ocr_text)
    embeddings = build_embedding_material(ocr_text, model_registry)
    internal = detailed_internal_analysis(ocr_text, internal_score(chunks, model_registry))
    try:
        external = retrieve_and_score(
            ocr_text, document.title, keywords, internal, model_registry, db.session,
            CorpusChunk, CorpusDocument, top_k, owner_id=document.user_id,
        )
    except Exception as exc:  # corpus setup must not invalidate completed OCR artifacts
        current_app.logger.warning("Corpus retrieval unavailable for %s: %s", document.id, exc)
        external = {
            "source": "pgvector-unavailable", "retrieved_cases": [],
            "overall_external_coherence_score": 0.0,
            "short_summary": "OCR, graph, embeddings, and internal analysis completed; corpus retrieval is not configured.",
        }

    # If OCR is being re-run on a document that already has results, those
    # results (external-inference rows + internal analysis) were computed
    # from the OLD text. Invalidate them before the new text/graph is
    # committed, or they would be served as if they matched the new text.
    if force and (document.ocr_text or document.internal_analysis):
        invalidate_stale_results(document)

    document.ocr_text = ocr_text
    document.ocr_metadata = {
        "schema_version": 1,
        "title": ocr_result["title"],
        "citations": citations,
        "articles": articles,
        "keywords": keywords,
        "stats": stats,
        "page_count": stats.get("num_pages", 0),
        "pages": ocr_result.get("pages", []),
        "chunks": [{key: value for key, value in chunk.items() if key != "text"} for chunk in chunks],
        "embedding": embeddings["metadata"],
    }
    document.citation_graph = citation_graph
    document.sentence_embedding = embeddings["sentence_embedding"]
    document.legal_embedding = embeddings["legal_embedding"]
    document.internal_analysis = internal
    persist_graph_citations(document, citation_graph)
    persist_inference_scores(
        document, external["retrieved_cases"], overall=external["overall_external_coherence_score"],
        short_summary=external["short_summary"], source=external["source"], top_k=top_k,
    )
    document.update_status("completed")
    db.session.commit()

    return {
        "ocr_metadata": document.ocr_metadata,
        "num_nodes": len(citation_graph.get("nodes") or []),
        "num_edges": len(citation_graph.get("edges") or []),
        "num_citations_saved": len(citation_graph.get("nodes") or []),
        "internal_analysis": internal,
        "external_inference": external,
    }


# Compatibility name used by the OCR route while clients migrate.
run_ocr_and_graph = run_document_pipeline


def run_internal_analysis_from_text(document: Document) -> dict[str, Any] | None:
    """Recompute only the internal stage from cached canonical OCR text."""
    if not document.ocr_text:
        return None
    try:
        from ..extensions import model_registry
        analysis = detailed_internal_analysis(document.ocr_text, internal_score(chunk_text(document.ocr_text), model_registry))
        document.internal_analysis = analysis
        db.session.commit()
        return analysis
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("Internal analysis failed: %s", exc)
        return None


def add_document_to_corpus(document: Document, file_path: Path) -> dict[str, Any]:
    """OCR and index an owned PDF, deliberately skipping citation generation."""
    from ..extensions import model_registry
    from ..models import CorpusChunk, CorpusDocument

    document.update_status("processing")
    db.session.commit()
    extracted = extract_pdf(file_path, include_citations=False)
    text = extracted["full_text"]
    pieces = chunk_text(text)
    if not pieces:
        raise ValueError("No text chunks could be indexed")
    embeddings = build_embedding_material(text, model_registry)
    sentence_model = model_registry.get_sentence_model()
    vectors = sentence_model.encode([piece["text"] for piece in pieces], convert_to_numpy=True)

    corpus = CorpusDocument.query.filter_by(source_type="manual", source_id=str(document.id)).one_or_none()
    if corpus is None:
        corpus = CorpusDocument(source_type="manual", source_id=str(document.id), domain="legal")
        db.session.add(corpus)
        db.session.flush()
    else:
        CorpusChunk.query.filter_by(corpus_document_id=corpus.id).delete(synchronize_session=False)
    corpus.title = document.title
    corpus.full_text = text
    corpus.summary = None
    corpus.keywords = extracted.get("keywords") or []
    corpus.citations = []
    corpus.metadata_json = {"owner_user_id": document.user_id, "document_id": str(document.id),
                            "page_count": len(extracted.get("pages") or []), "embedding": embeddings["metadata"]}
    for piece, vector in zip(pieces, vectors):
        db.session.add(CorpusChunk(
            corpus_document_id=corpus.id, chunk_index=piece["index"], chunk_text=piece["text"],
            sentence_embedding=vector.tolist(),
            metadata_json={"start_char": piece["start_char"], "end_char": piece["end_char"],
                           "owner_user_id": document.user_id},
        ))
    document.ocr_text = text
    document.ocr_metadata = {"schema_version": 1, "title": extracted["title"],
                             "pages": extracted.get("pages") or [], "stats": extracted.get("stats") or {},
                             "keywords": extracted.get("keywords") or [], "embedding": embeddings["metadata"],
                             "processing_mode": "database_only", "corpus_document_id": str(corpus.id)}
    document.sentence_embedding = embeddings["sentence_embedding"]
    document.legal_embedding = embeddings["legal_embedding"]
    document.citation_graph = None
    document.internal_analysis = None
    Citation.query.filter_by(document_id=document.id).delete(synchronize_session=False)
    document.update_status("completed")
    db.session.commit()
    return {"document_id": str(document.id), "corpus_document_id": str(corpus.id),
            "chunks_indexed": len(pieces), "pages_ocrd": len(extracted.get("pages") or [])}
