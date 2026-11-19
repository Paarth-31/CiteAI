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


def test_document_question_includes_cited_case_context_and_history(monkeypatch):
    text = ("The judgment cites Madhav Hayawadanrao Hoskot v. State of Maharashtra "
            "when discussing access to an appeal and legal assistance. ") * 3
    graph = build_citation_graph("Current judgment", text, ["Madhav Hayawadanrao Hoskot v. State of Maharashtra"])
    model = SimpleNamespace(encode=lambda values, **kwargs: np.ones((len(values), 2)))
    registry = SimpleNamespace(get_sentence_model=lambda: model)
    prompts = []
    monkeypatch.setattr(legal_pipeline, "_gemini_text", lambda prompt: prompts.append(prompt) or "The document discusses legal assistance [Citation 1].")
    monkeypatch.setattr(legal_pipeline, "retrieve_cited_case_passages", lambda *args: [])

    result = legal_pipeline.answer_document_question(
        text, "What about that case?", "Current judgment", registry,
        citation_graph=graph, history=[{"role": "user", "content": "Which case discusses an appeal?"}],
    )

    assert result["citation_count"] == 1
    assert result["citation_context"][0]["title"] == "Madhav Hayawadanrao Hoskot v. State of Maharashtra"
    assert "access to an appeal" in result["citation_context"][0]["excerpt"]
    assert "Recent conversation" in prompts[0] and "Which case discusses an appeal?" in prompts[0]
    assert "[Citation 1]" in prompts[0]
    assert "only labeled Cited Case Passages come from a full cited" in prompts[0]


def test_cited_case_passages_require_matching_case_and_use_full_text(monkeypatch):
    assert legal_pipeline._same_case_title(
        "Madhav Hayawadanrao Hoskot v. State of Maharashtra",
        "Madhav Hayawadanrao Hoskot vs State Of Maharashtra on 17 August, 1978",
    )
    assert not legal_pipeline._same_case_title(
        "Madhav Hayawadanrao Hoskot v. State of Maharashtra",
        "Madhav Hayawadanrao Hoskot vs State Of Orissa on 17 August, 1978",
    )
    monkeypatch.setenv("INDIAN_KANOON_API_TOKEN", "test-token")
    monkeypatch.setattr(legal_pipeline, "_load_cited_case", lambda *args: {
        "title": "Madhav Hayawadanrao Hoskot vs State Of Maharashtra",
        "text": "The cited judgment discusses access to an appeal and legal assistance.",
        "pdf_url": "https://indiankanoon.org/doc/513169/?type=pdf",
    })
    model = SimpleNamespace(encode=lambda values, **kwargs: np.ones((len(values), 2)))
    registry = SimpleNamespace(get_sentence_model=lambda: model)
    passages = legal_pipeline.retrieve_cited_case_passages(
        [{"title": "Madhav Hayawadanrao Hoskot v. State of Maharashtra", "excerpt": ""}],
        "What did Madhav Hoskot say about an appeal?", registry,
    )
    assert len(passages) == 1
    assert "legal assistance" in passages[0]["text"]
    assert passages[0]["pdf_url"].endswith("/?type=pdf")


def test_workspace_evidence_prefers_article_passage_and_falls_back_to_upload(monkeypatch):
    title = "Madhav Hayawadanrao Hoskot v. State of Maharashtra"
    text = f"The court cited {title} when discussing Article 21 and legal assistance."
    graph = build_citation_graph("Uploaded judgment", text, [title])
    node = graph["nodes"][1]
    monkeypatch.setenv("INDIAN_KANOON_API_TOKEN", "test-token")
    monkeypatch.setattr(legal_pipeline, "_load_cited_case", lambda *args: {
        "title": title, "text": "Full cited judgment text", "pdf_url": "https://indiankanoon.org/doc/513169/?type=pdf"
    })
    monkeypatch.setattr(legal_pipeline, "retrieve_document_passages", lambda *args, **kwargs: [
        {"text": "General discussion of legal assistance.", "score": 0.9},
        {"text": "Article 21 protects access to legal assistance.", "score": 0.8},
    ])
    result = legal_pipeline.build_citation_evidence("Uploaded judgment", text, graph, node, registry=None)
    assert result["source"] == "cited_judgment"
    assert result["excerpt"] == "Article 21 protects access to legal assistance."
    assert result["article_refs"] == ["Article 21"]
    assert result["pdf_url"].endswith("/?type=pdf")
    assert title in result["citation_excerpt"]

    monkeypatch.setattr(legal_pipeline, "_load_cited_case", lambda *args: None)
    fallback = legal_pipeline.build_citation_evidence("Uploaded judgment", text, graph, node, registry=None)
    assert fallback["source"] == "uploaded_document"
    assert title in fallback["excerpt"]
    assert fallback["pdf_url"] is None


def test_internal_score_does_not_compare_unrelated_chunk_numbers():
    chunks = [
        {"text": "The court heard appeal 120 in 2018 and discussed jurisdiction at length."},
        {"text": "The court heard appeal 245 in 2021 and discussed evidence at length."},
    ]
    result = legal_pipeline.internal_score(chunks, registry=None)
    assert result["issues"] == []
    assert result["coherence_score"] == 1.0
    assert result["analysis_version"] == legal_pipeline.INTERNAL_ANALYSIS_VERSION


def test_internal_score_flags_only_matching_numeric_statements_once():
    chunks = [
        {"text": "The amount payable under the agreement is 100 rupees after the hearing."},
        {"text": "The amount payable under the agreement is 200 rupees after the hearing."},
        {"text": "The amount payable under the agreement is 300 rupees after the hearing."},
    ]
    result = legal_pipeline.internal_score(chunks, registry=None)
    assert len(result["issues"]) == 1
    assert result["issues"][0]["type"] == "review_numeric_claim"
    assert result["issues"][0]["chunk_indices"] == [0, 1]
    assert result["coherence_score"] > 0.9


def test_detailed_analysis_merges_report_and_nli_signals(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(legal_pipeline, "_gemini_text", lambda prompt, json_response=False:
                        '{"summary":"Supported analysis", "claims":["Claim A [Chunk 0]", "Claim B [Chunk 0]"], "key_flows":["Flow"], "review_signals":[]}')
    monkeypatch.setattr(legal_pipeline, "_nli_review_signals", lambda claims: [{"type": "possible_conflict", "severity": "medium"}])
    result = legal_pipeline.detailed_internal_analysis("A document contains two candidate claims.", {"coherence_score": 0.9, "issues": []})
    assert result["analysis_mode"] == "gemini"
    assert result["claims"] == ["Claim A [Chunk 0]", "Claim B [Chunk 0]"]
    assert result["issues"][0]["type"] == "possible_conflict"


def test_gemini_retries_truncated_chat_output_with_thinking_disabled(monkeypatch):
    from google import genai

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    requests = []

    class Models:
        def generate_content(self, *, model, contents, config):
            requests.append((model, config))
            if len(requests) == 1:
                return SimpleNamespace(candidates=[SimpleNamespace(finish_reason="MAX_TOKENS")], text="partial")
            return SimpleNamespace(candidates=[SimpleNamespace(finish_reason="STOP")], text="Brief summary [Passage 1].")

    monkeypatch.setattr(genai, "Client", lambda **kwargs: SimpleNamespace(models=Models(), close=lambda: None))
    answer = legal_pipeline._gemini_text("Summarize Minerva Mills briefly.")
    assert answer.startswith("Brief summary")
    assert [config["max_output_tokens"] for _, config in requests] == [4096, 8192]
    assert all(config["thinking_config"]["thinking_budget"] == 0 for _, config in requests)


def test_gemini_falls_back_after_transient_server_errors(monkeypatch):
    from google import genai
    import time

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash")
    monkeypatch.setenv("GEMINI_FALLBACK_MODEL", "gemini-2.5-flash-lite")
    monkeypatch.setattr(time, "sleep", lambda _: None)
    models_called = []

    class CapacityError(Exception):
        code = 503

    class Models:
        def generate_content(self, *, model, contents, config):
            models_called.append(model)
            if model == "gemini-2.5-flash":
                raise CapacityError("busy")
            return SimpleNamespace(candidates=[SimpleNamespace(finish_reason="STOP")], text='{"summary":"ok"}')

    monkeypatch.setattr(genai, "Client", lambda **kwargs: SimpleNamespace(models=Models(), close=lambda: None))
    result = legal_pipeline._gemini_text("Report", json_response=True)
    assert result == '{"summary":"ok"}'
    assert models_called == ["gemini-2.5-flash", "gemini-2.5-flash", "gemini-2.5-flash-lite"]


def test_detailed_analysis_explains_gemini_connection_failure(monkeypatch):
    from httpx import ConnectError

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def unavailable(*args, **kwargs):
        raise ConnectError("network unavailable")

    monkeypatch.setattr(legal_pipeline, "_gemini_text", unavailable)
    result = legal_pipeline.detailed_internal_analysis(
        "The amount payable under the agreement is 100 rupees.",
        {"coherence_score": 0.99, "issues": [{"type": "review_numeric_claim"}]},
    )
    assert result["analysis_mode"] == "deterministic"
    assert "check DNS/HTTPS access" in result["summary"]
    assert len(result["issues"]) == 1


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
