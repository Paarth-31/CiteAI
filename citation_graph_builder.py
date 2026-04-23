"""Citation Graph Builder for Legal Cases.

Builds directed citation graphs from plain-text or OCR-extracted legal
judgments. Each node is a legal case; each edge represents a citation.

Changes from previous version:
  - Nodes now carry an optional `embedding` field that the GraphBuilder
    (lexai/graph_builder.py) fills in with InLegalBERT or BioBERT vectors.
    This decouples graph construction from embedding — you can build the
    graph without loading any BERT model.
  - Edge deduplication: duplicate source→target edges are silently skipped.
  - `build_from_text()` class method for building from a raw string directly
    (used by citation_graph_service.py — no temp file needed).
  - CLI output format unchanged so test_graph_builder.py still passes.

Usage (CLI):
    python citation_graph_builder.py \\
        --input lexai/data/lecai_baseline \\
        --output lexai/data/graphs/citation_graph.json \\
        --png outputs/graph.png

Usage (from Python / Flask service):
    builder = CitationGraphBuilder.build_from_text(text, document_title)
    graph   = {"nodes": builder.nodes, "edges": builder.edges}
"""
from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── Regex patterns ────────────────────────────────────────────────────────────
_CITATION_PATTERNS = [
    # "X v. Y (YEAR) N SCC M"
    r"([A-Z][A-Za-z\s&,\.]+?)\s+v\.?\s+([A-Za-z\s&,\.]+?)(?:\s*\((\d{4})\))?\s+(\d+)\s+SCC\s+\d+",
    # "X v Y (YEAR)"
    r"([A-Z][A-Za-z\s&,\.]+?)\s+v\.?\s+([A-Za-z\s&,\.]+?)\s*\((\d{4})\)",
    # "X vs. Y" or "X v. Y"
    r"([A-Z][A-Za-z\s&,\.]{3,30}?)\s+v[s]?\.?\s+([A-Za-z\s&,\.]{3,30}?)(?=\s|,|\.|\()",
]


class CitationGraphBuilder:
    """Build citation graphs from legal documents."""

    def __init__(self) -> None:
        self.nodes: list[dict[str, Any]] = []
        self.edges: list[dict[str, str]] = []
        self.node_map: dict[str, dict[str, Any]] = {}   # id → node data
        self._edge_set: set[tuple[str, str]] = set()    # deduplication

    # ── Class-method factory ──────────────────────────────────────────────────

    @classmethod
    def build_from_text(
        cls, text: str, document_title: str = ""
    ) -> "CitationGraphBuilder":
        """Build a citation graph from a raw text string.

        Used by citation_graph_service.py — no temp file, no disk I/O.
        """
        builder = cls()
        year    = builder.extract_year(text)
        title   = document_title if document_title and document_title != "Untitled" \
                  else builder.extract_title(text)
        node_id = builder.generate_node_id(title, year)

        snippet = text[:200].replace("\n", " ")
        builder.add_node(node_id, title, year, snippet)

        for citation_text, citation_year in builder.extract_citations(text):
            target_id = builder.find_matching_node(citation_text, citation_year)
            if not target_id:
                target_id = builder.generate_node_id(citation_text, citation_year)
                if target_id not in builder.node_map:
                    builder.add_node(target_id, citation_text, citation_year, "")
            builder.add_edge(node_id, target_id)

        return builder

    # ── Text helpers ──────────────────────────────────────────────────────────

    def normalize_text(self, text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"[,\.]", "", text)
        return text

    def extract_year(self, text: str) -> Optional[int]:
        match = re.search(r"\b(19\d{2}|20\d{2})\b", text)
        return int(match.group(1)) if match else None

    def extract_title(self, text: str) -> str:
        snippet = text[:500]
        patterns = [
            r"([A-Z][A-Za-z\s&,\.]+?)\s+v\.?\s+([A-Za-z\s&,\.]+?)(?=\s*\(|\s*$|\n)",
            r"^([A-Z][A-Za-z\s&,\.\-]+?)$",
        ]
        for pat in patterns:
            m = re.search(pat, snippet, re.MULTILINE)
            if m:
                title = m.group(0).strip()
                if 10 < len(title) < 200:
                    return title
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        for line in lines[:10]:
            if len(line) > 10 and "SUPREME COURT" not in line and "JUDGMENT" not in line:
                return line[:150]
        return "Untitled Case"

    def extract_citations(self, text: str) -> list[tuple[str, Optional[int]]]:
        """Extract (citation_text, year) tuples using regex patterns."""
        results: list[tuple[str, Optional[int]]] = []
        seen: set[str] = set()

        for pattern in _CITATION_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                if len(match.groups()) >= 2:
                    party1 = match.group(1).strip()
                    party2 = match.group(2).strip()
                    citation_text = f"{party1} v. {party2}"
                    year: Optional[int] = None
                    if len(match.groups()) >= 3 and match.group(3):
                        try:
                            year = int(match.group(3))
                        except ValueError:
                            pass
                    normalized = self.normalize_text(citation_text)
                    if normalized not in seen and len(normalized) > 10:
                        seen.add(normalized)
                        results.append((citation_text, year))
        return results

    def generate_node_id(self, title: str, year: Optional[int] = None) -> str:
        slug = re.sub(r"\s+", "_", self.normalize_text(title))
        slug = re.sub(r"[^\w_]", "", slug)[:50]
        return f"{slug}_{year}" if year else slug

    # ── Graph mutation ────────────────────────────────────────────────────────

    def add_node(
        self,
        node_id: str,
        title: str,
        year: Optional[int],
        text_snippet: str,
    ) -> None:
        """Add a node if it doesn't exist.

        The `embedding` field is intentionally left None here.
        lexai/graph_builder.py (GraphBuilder) fills it in with BERT vectors
        after the graph is constructed, keeping concerns separated.
        """
        if node_id not in self.node_map:
            node: dict[str, Any] = {
                "id":        node_id,
                "title":     title,
                "year":      year,
                "text":      text_snippet[:200],
                "embedding": None,   # populated by GraphBuilder when needed
            }
            self.nodes.append(node)
            self.node_map[node_id] = node

    def add_edge(self, source_id: str, target_id: str) -> None:
        """Add an edge, silently skipping duplicates and self-loops."""
        if source_id == target_id:
            return
        key = (source_id, target_id)
        if key not in self._edge_set:
            self._edge_set.add(key)
            self.edges.append({"source": source_id, "target": target_id})

    def find_matching_node(
        self, citation_text: str, year: Optional[int]
    ) -> Optional[str]:
        candidate_id = self.generate_node_id(citation_text, year)
        if candidate_id in self.node_map:
            return candidate_id
        normalized = self.normalize_text(citation_text)
        for node_id, node in self.node_map.items():
            norm_title = self.normalize_text(node["title"])
            if normalized in norm_title or norm_title in normalized:
                if year is None or node["year"] is None or year == node["year"]:
                    return node_id
        return None

    # ── Directory-based build (CLI / standalone) ──────────────────────────────

    def process_document(self, file_path: Path) -> tuple[str, str, Optional[int], str]:
        text = file_path.read_text(encoding="utf-8")
        title = self.extract_title(text)
        year  = self.extract_year(text)
        return self.generate_node_id(title, year), title, year, text

    def build_graph(self, input_dir: Path) -> tuple[int, int]:
        if not input_dir.exists():
            raise FileNotFoundError(f"Input directory not found: {input_dir}")
        text_files = list(input_dir.glob("*.txt"))
        if not text_files:
            raise ValueError(f"No .txt files found in {input_dir}")

        logger.info("Building citation graph from %d documents", len(text_files))

        doc_data: dict[str, str] = {}
        for fp in text_files:
            try:
                node_id, title, year, text = self.process_document(fp)
                self.add_node(node_id, title, year, text[:200].replace("\n", " "))
                doc_data[node_id] = text
            except Exception as exc:
                logger.warning("Skipped %s: %s", fp.name, exc)

        for source_id, text in doc_data.items():
            for citation_text, year in self.extract_citations(text):
                target_id = self.find_matching_node(citation_text, year)
                if not target_id:
                    target_id = self.generate_node_id(citation_text, year)
                    if target_id not in self.node_map:
                        self.add_node(target_id, citation_text, year, "")
                self.add_edge(source_id, target_id)

        return len(self.nodes), len(self.edges)

    # ── Serialisation ─────────────────────────────────────────────────────────

    def save_json(self, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        # Strip embedding arrays before serialising (they're numpy / large)
        nodes_serialisable = [
            {k: v for k, v in n.items() if k != "embedding"}
            for n in self.nodes
        ]
        data = {"nodes": nodes_serialisable, "edges": self.edges}
        output_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def save_png(self, output_path: Path) -> None:
        try:
            import networkx as nx
            import matplotlib.pyplot as plt
        except ImportError:
            logger.warning("networkx/matplotlib not available — PNG skipped.")
            return

        G = nx.DiGraph()
        for node in self.nodes:
            label = node["title"][:30] + ("..." if len(node["title"]) > 30 else "")
            G.add_node(node["id"], label=label, year=node["year"])
        for edge in self.edges:
            G.add_edge(edge["source"], edge["target"])

        plt.figure(figsize=(16, 12))
        pos    = nx.spring_layout(G, k=2, iterations=50, seed=42)
        labels = nx.get_node_attributes(G, "label")
        nx.draw_networkx_nodes(G, pos, node_color="lightblue", node_size=1500, alpha=0.9)
        nx.draw_networkx_edges(G, pos, edge_color="gray", arrows=True, arrowsize=20, alpha=0.5)
        nx.draw_networkx_labels(G, pos, labels, font_size=8)
        plt.title("Legal Citation Graph", fontsize=16)
        plt.axis("off")
        plt.tight_layout()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close()
        logger.info("PNG saved: %s", output_path)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Build citation graph from legal documents")
    parser.add_argument("--input",  required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--png",    type=Path)
    args = parser.parse_args()

    builder = CitationGraphBuilder()
    try:
        num_nodes, num_edges = builder.build_graph(args.input)
        builder.save_json(args.output)
        print(f"graph saved: {args.output} ({num_nodes} nodes, {num_edges} edges)")
        if args.png:
            builder.save_png(args.png)
    except Exception as exc:
        print(f"Error: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
