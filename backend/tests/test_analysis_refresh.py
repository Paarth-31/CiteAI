"""Legacy saved reports must be replaced when the analysis algorithm changes."""
from types import SimpleNamespace

from flask import Flask

from app.routes import ocr
from app.services.legal_pipeline import INTERNAL_ANALYSIS_VERSION


def test_legacy_analysis_recomputes_before_it_is_served(monkeypatch):
    document = SimpleNamespace(ocr_text="Document text", internal_analysis={
        "coherence_score": 0.25, "issues": [{"type": "review_numeric_claim"}] * 111712,
    })
    query = SimpleNamespace(filter_by=lambda **kwargs: SimpleNamespace(one_or_none=lambda: document))
    monkeypatch.setattr(ocr, "Document", SimpleNamespace(query=query))
    monkeypatch.setattr(ocr, "current_user", SimpleNamespace(id="user-1"))
    refreshed = {"analysis_version": INTERNAL_ANALYSIS_VERSION, "coherence_score": 0.96, "issues": []}
    calls = []
    monkeypatch.setattr(ocr, "run_internal_analysis_from_text", lambda doc: calls.append(doc) or refreshed)

    app = Flask(__name__)
    with app.test_request_context("/api/ocr/internal-analysis/document-1"):
        response = ocr.get_internal_analysis.__wrapped__("document-1")
        assert response.json["analysis"] == refreshed
    assert calls == [document]

    document.internal_analysis = refreshed
    calls.clear()
    with app.test_request_context("/api/ocr/internal-analysis/document-1"):
        response = ocr.get_internal_analysis.__wrapped__("document-1")
        assert response.json["analysis"] == refreshed
    assert calls == []
