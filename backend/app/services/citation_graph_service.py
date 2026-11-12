"""Citation graph generation — thin wrapper around CitationGraphBuilder."""
from __future__ import annotations

from typing import Any

from .paths import ensure_project_root


def generate_citation_graph(ocr_text: str, document_title: str) -> dict[str, Any]:
    """Build a citation graph from OCR text.

    Returns:
        {"nodes": [...], "edges": [...]}
    """
    ensure_project_root()
    from citation_graph_builder import CitationGraphBuilder

    builder = CitationGraphBuilder.build_from_text(ocr_text, document_title)
    return {"nodes": builder.nodes, "edges": builder.edges}
