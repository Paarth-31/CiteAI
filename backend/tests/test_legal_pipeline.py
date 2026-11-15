"""Fast, model-free tests for canonical artifact construction."""
from app.services.legal_pipeline import answer_from_text, build_citation_graph, chunk_text
from app.services import legal_pipeline
import numpy as np
from pathlib import Path
import sys
from types import SimpleNamespace


def test_chunk_text_preserves_offsets_and_progresses():
    text = "alpha beta gamma delta " * 80
    chunks = chunk_text(text, chunk_size=100, overlap=20)
    assert len(chunks) > 1
    assert chunks[0]["start_char"] == 0
    assert all(a["end_char"] <= b["end_char"] for a, b in zip(chunks, chunks[1:]))


def test_graph_has_citation_evidence():
    text = "K.S. Puttaswamy v. Union of India (2017) 10 SCC 1 applies."
    graph = build_citation_graph("Privacy judgment", text, ["K.S. Puttaswamy v. Union of India"])
    assert len(graph["nodes"]) == 2
    assert graph["edges"][0]["evidence"]["start_char"] == 0


def test_graph_merges_citations_that_normalise_to_the_same_node():
    text = "See (2005) 2 SCALE 33 and 2005 (2) SCALE 33."
    graph = build_citation_graph("Judgment", text, ["(2005) 2 SCALE 33", "2005 (2) SCALE 33"])
    ids = [node["id"] for node in graph["nodes"]]
    assert len(ids) == len(set(ids)) == 2
    assert len(graph["edges"]) == 1


def test_local_query_returns_document_evidence_without_global_index():
    result = answer_from_text("Article 21 protects life and personal liberty.", "What protects liberty?", "Case")
    assert "Article 21" in result["Answer"]


def test_document_question_sends_only_ranked_passages_to_gemini(monkeypatch):
    class SentenceModel:
        def encode(self, values, convert_to_numpy=True):
            return np.asarray([[1.0, 0.0] if "liberty" in value.lower() else [0.0, 1.0] for value in values])

    class Registry:
        def get_sentence_model(self):
            return SentenceModel()

    prompts = []
    monkeypatch.setattr(legal_pipeline, "_gemini_text", lambda prompt: prompts.append(prompt) or "Article 21 protects liberty [Passage 1].")
    result = legal_pipeline.answer_document_question(
        "Article 21 protects life and personal liberty. " * 18, "What protects liberty?", "Privacy", Registry()
    )
    assert result["mode"] == "gemini"
    assert result["passages"]
    assert "Article 21" in prompts[0]
    assert "What protects liberty?" in prompts[0]


def test_detailed_analysis_merges_report_and_nli_signals(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(legal_pipeline, "_gemini_text", lambda prompt, json_response=False:
                        '{"summary":"Supported analysis", "claims":["Claim A [Chunk 0]", "Claim B [Chunk 0]"], "key_flows":["Flow"], "review_signals":[]}')
    monkeypatch.setattr(legal_pipeline, "_nli_review_signals", lambda claims: [{"type": "possible_conflict", "severity": "medium"}])
    result = legal_pipeline.detailed_internal_analysis("A document contains two candidate claims.", {"coherence_score": 0.9, "issues": []})
    assert result["analysis_mode"] == "gemini"
    assert result["claims"] == ["Claim A [Chunk 0]", "Claim B [Chunk 0]"]
    assert result["issues"][0]["type"] == "possible_conflict"


def test_database_only_extraction_ocr_s_blank_pages_without_citations(monkeypatch):
    class Pdf:
        pages = [SimpleNamespace(extract_text=lambda: "Article 21 provides rights."),
                 SimpleNamespace(extract_text=lambda: "")]

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    monkeypatch.setitem(sys.modules, "pdfplumber", SimpleNamespace(open=lambda _: Pdf()))
    monkeypatch.setattr(legal_pipeline, "_ocr_scanned_pdf", lambda path, page_numbers: [
        {"page": 2, "text": "Scanned evidence", "character_count": 16, "source": "tesseract"}
    ])
    result = legal_pipeline.extract_pdf(Path("example.pdf"), include_citations=False)
    assert result["citations"] == []
    assert result["articles"] == []
    assert result["pages"][1]["text"] == "Scanned evidence"
    assert "Scanned evidence" in result["full_text"]


def test_corpus_distance_is_numeric_and_results_are_deduplicated():
    from sqlalchemy import Float
    from app.models import CorpusChunk, CorpusDocument

    model = SimpleNamespace(encode=lambda texts, **kwargs: np.ones((len(texts), 384)))
    registry = SimpleNamespace(get_sentence_model=lambda: model, sentence_model_name=lambda: "test")
    document = SimpleNamespace(id="case-1", title="Privacy", full_text="privacy rights", keywords=[], metadata_json={})
    chunk = SimpleNamespace(chunk_text="privacy rights")

    class Session:
        def query(self, *columns):
            # A raw .op('<=>') retains VECTOR's decoder and crashes when the
            # database returns the scalar distance. Exercise the real expression.
            assert isinstance(columns[2].type, Float)
            return self

        def join(self, *args): return self
        def filter(self, *args): return self
        def order_by(self, *args): return self
        def limit(self, *args): return self
        def all(self): return [(chunk, document, 0.3), (chunk, document, 0.1)]

    result = legal_pipeline.retrieve_and_score("privacy rights", "Test", [], {"coherence_score": 0.8},
                                               registry, Session(), CorpusChunk, CorpusDocument, 5)
    assert len(result["retrieved_cases"]) == 1
    assert result["retrieved_cases"][0]["similarity_score"] == 0.9
