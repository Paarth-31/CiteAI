"""Citation graph generation — thin wrapper around CitationGraphBuilder."""
from __future__ import annotations

from typing import Any

from .legal_pipeline import build_citation_graph


def generate_citation_graph(ocr_text: str, document_title: str) -> dict[str, Any]:
    """Build a citation graph from OCR text.

    Returns:
        {"nodes": [...], "edges": [...]}
    """
    return build_citation_graph(document_title, ocr_text, [])
