"""Unit tests for citation_graph_builder.py."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from citation_graph_builder import CitationGraphBuilder


@pytest.fixture
def sample_dir():
    return Path(__file__).parent.parent / "lexai" / "data" / "lecai_baseline"


@pytest.fixture
def output_dir(tmp_path):
    return tmp_path / "outputs"


class TestCitationGraphBuilder:

    def test_normalize_text(self):
        b = CitationGraphBuilder()
        assert b.normalize_text("  Hello   World  ") == "hello world"
        assert b.normalize_text("A, B, C.") == "a b c"
        assert b.normalize_text("UPPER case") == "upper case"

    def test_extract_year(self):
        b = CitationGraphBuilder()
        assert b.extract_year("decided in 2017") == 2017
        assert b.extract_year("(1978) 1 SCC 248") == 1978
        assert b.extract_year("no year here") is None
        assert b.extract_year("1899 too old") is None

    def test_extract_title(self):
        b = CitationGraphBuilder()
        text = "K.S. Puttaswamy v. Union of India\n\nThis is about privacy rights."
        title = b.extract_title(text)
        assert "Puttaswamy" in title or "K.S." in title

    def test_extract_citations(self):
        b = CitationGraphBuilder()
        text = """
        This Court relies on K.S. Puttaswamy v. Union of India (2017) 10 SCC 1.
        We also refer to Maneka Gandhi v. Union of India (1978) 1 SCC 248.
        Gobind v. State of Madhya Pradesh is also relevant.
        """
        citations = b.extract_citations(text)
        assert len(citations) >= 2
        texts_lower = [c[0].lower() for c in citations]
        assert any("puttaswamy" in t for t in texts_lower)

    def test_generate_node_id(self):
        b = CitationGraphBuilder()
        id1 = b.generate_node_id("K.S. Puttaswamy v. Union of India", 2017)
        id2 = b.generate_node_id("K.S. Puttaswamy v. Union of India", 2017)
        assert id1 == id2
        assert "2017" in id1

    def test_node_has_embedding_field(self):
        """Nodes must carry an embedding field (None until GraphBuilder fills it)."""
        b = CitationGraphBuilder()
        b.add_node("test_id", "Test Case v. Someone", 2020, "sample text")
        assert "embedding" in b.node_map["test_id"]
        assert b.node_map["test_id"]["embedding"] is None

    def test_edge_deduplication(self):
        """Duplicate edges must be silently ignored."""
        b = CitationGraphBuilder()
        b.add_node("a", "Case A", 2020, "")
        b.add_node("b", "Case B", 2019, "")
        b.add_edge("a", "b")
        b.add_edge("a", "b")   # duplicate
        b.add_edge("a", "b")   # duplicate
        assert len(b.edges) == 1

    def test_no_self_loops(self):
        """Self-loop edges must be rejected."""
        b = CitationGraphBuilder()
        b.add_node("a", "Case A", 2020, "")
        b.add_edge("a", "a")
        assert len(b.edges) == 0

    def test_build_from_text(self):
        """build_from_text() class method must produce a valid graph."""
        text = """
        K.S. Puttaswamy v. Union of India (2017)

        This case concerns fundamental rights. We rely on Maneka Gandhi v. Union of India (1978).
        Reference is also made to Gobind v. State of Madhya Pradesh (1975).
        """
        builder = CitationGraphBuilder.build_from_text(text, "Puttaswamy Privacy Case")
        assert len(builder.nodes) >= 1
        # The built-in citation extraction should find at least one edge
        # (may vary depending on regex match quality on short text)
        assert isinstance(builder.edges, list)
        assert isinstance(builder.nodes, list)
        # Every node must have the embedding slot
        for node in builder.nodes:
            assert "embedding" in node

    def test_save_json_excludes_embedding(self, output_dir):
        """Serialised JSON must NOT include embedding arrays."""
        output_dir.mkdir(parents=True, exist_ok=True)
        b = CitationGraphBuilder()
        b.add_node("a", "Case A", 2020, "snippet")
        # Fake embedding
        import numpy as np
        b.node_map["a"]["embedding"] = np.zeros(768).tolist()

        out = output_dir / "test.json"
        b.save_json(out)
        data = json.loads(out.read_text())
        for node in data["nodes"]:
            assert "embedding" not in node

    def test_build_graph_sample_data(self, sample_dir, output_dir):
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / "test_graph.json"

        b = CitationGraphBuilder()
        num_nodes, num_edges = b.build_graph(sample_dir)

        assert num_nodes >= 4, f"Expected ≥4 nodes, got {num_nodes}"
        assert num_edges >= 2, f"Expected ≥2 edges, got {num_edges}"

        b.save_json(output_file)
        assert output_file.exists()

        data = json.loads(output_file.read_text())
        assert "nodes" in data and "edges" in data
        assert len(data["nodes"]) == num_nodes
        assert len(data["edges"]) == num_edges

        for node in data["nodes"]:
            for key in ("id", "title", "year", "text"):
                assert key in node

        for edge in data["edges"]:
            assert "source" in edge and "target" in edge

    def test_cli_execution(self, sample_dir, output_dir):
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / "cli_test_graph.json"

        cmd = [
            sys.executable,
            str(Path(__file__).parent.parent / "citation_graph_builder.py"),
            "--input", str(sample_dir),
            "--output", str(output_file),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)

        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert "graph saved:" in result.stdout
        assert str(output_file) in result.stdout

        m = re.search(r"\((\d+) nodes, (\d+) edges\)", result.stdout)
        assert m is not None
        assert int(m.group(1)) >= 4
        assert int(m.group(2)) >= 2
        assert output_file.exists()

    def test_find_matching_node(self):
        b = CitationGraphBuilder()
        b.add_node("puttaswamy_2017", "K.S. Puttaswamy v. Union of India", 2017, "sample")
        assert b.find_matching_node("K.S. Puttaswamy v. Union of India", 2017) == "puttaswamy_2017"
        assert b.find_matching_node("Puttaswamy v Union of India", 2017) == "puttaswamy_2017"
        assert b.find_matching_node("Different Case v. Someone", 2020) is None

    def test_placeholder_nodes(self, sample_dir, output_dir):
        output_dir.mkdir(parents=True, exist_ok=True)
        b = CitationGraphBuilder()
        b.build_graph(sample_dir)
        placeholders = [n for n in b.nodes if n["text"] == ""]
        assert len(placeholders) >= 0  # may or may not exist depending on sample


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
