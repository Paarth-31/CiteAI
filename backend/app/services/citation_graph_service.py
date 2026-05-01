"""Citation graph generation service.

Optimisation over original:
  Removed the temp-file-write → read cycle. The CitationGraphBuilder
  now receives text directly, saving disk I/O on every document processed.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


def _ensure_project_root() -> None:
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    root_str = str(project_root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    lexai_str = str(project_root / "lexai")
    if lexai_str not in sys.path:
        sys.path.insert(0, lexai_str)


def generate_citation_graph(ocr_text: str, document_title: str) -> dict[str, Any]:
    """Build a citation graph from OCR text.

    Returns:
        {"nodes": [...], "edges": [...]}
    """
    _ensure_project_root()
    from citation_graph_builder import CitationGraphBuilder

    builder = CitationGraphBuilder()

    # Derive node_id and year directly from text — no temp file needed
    year    = builder.extract_year(ocr_text)
    title   = document_title if document_title and document_title != "Untitled" \
              else builder.extract_title(ocr_text)
    node_id = builder.generate_node_id(title, year)

    text_snippet = ocr_text[:200].replace("\n", " ")
    builder.add_node(node_id, title, year, text_snippet)

    citations = builder.extract_citations(ocr_text)
    for citation_text, citation_year in citations:
        target_id = builder.find_matching_node(citation_text, citation_year)
        if not target_id:
            target_id = builder.generate_node_id(citation_text, citation_year)
            if target_id not in builder.node_map:
                builder.add_node(target_id, citation_text, citation_year, "")
        builder.add_edge(node_id, target_id)

    return {"nodes": builder.nodes, "edges": builder.edges}
