"""Citation serialization helpers."""
from __future__ import annotations
from ..models import Citation


def citation_to_dict(citation: Citation) -> dict:
    evidence_span = citation.evidence_json
    if isinstance(evidence_span, dict):
        evidence_span = evidence_span.get("text")
    elif evidence_span is not None and not isinstance(evidence_span, str):
        evidence_span = str(evidence_span)

    return {
        "id":              citation.id,
        "documentId":      citation.document_id,
        "title":           citation.title,
        "x":               citation.x,
        "y":               citation.y,
        "citations":       citation.citations,
        "year":            citation.year,
        "trsScore":        citation.trs_score,
        "similarityScore": citation.similarity_score,
        "evidenceSpan":    evidence_span,
        "sourceModel":     citation.source_model,
        "createdAt":       citation.created_at.isoformat() if citation.created_at else None,
        "updatedAt":       citation.updated_at.isoformat() if citation.updated_at else None,
    }
