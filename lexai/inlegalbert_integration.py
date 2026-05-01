"""Integration example: InLegalBERT and BioBERT with CiteAI.

Shows how to use both domain agents standalone (outside Flask), and how
the Flask ModelRegistry wires them in for the backend.

The hardcoded /home/anand/... path has been removed. Set the environment
variable LECAI_BASE to your dataset root, or pass paths explicitly.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from lexai.agents import InLegalBERTExternalAgent, BioBERTExternalAgent

BASE_DIR = Path(__file__).resolve().parent.parent

# ── Standalone demo helpers ───────────────────────────────────────────────────

def _sample_cases() -> list[dict]:
    """Minimal sample dataset — no CSV required."""
    return [
        {
            "case_id": "puttaswamy_2017",
            "title":   "K.S. Puttaswamy v. Union of India",
            "text":    "The right to privacy is a fundamental right under Article 21. "
                       "Privacy includes the preservation of personal intimacies, the sanctity "
                       "of family life, marriage, procreation, the home and sexual orientation.",
            "year": 2017,
        },
        {
            "case_id": "maneka_1978",
            "title":   "Maneka Gandhi v. Union of India",
            "text":    "Article 21 confers a fundamental right to life and personal liberty. "
                       "The right to life is not merely confined to physical existence but includes "
                       "the right to live with human dignity.",
            "year": 1978,
        },
        {
            "case_id": "gobind_1975",
            "title":   "Gobind v. State of Madhya Pradesh",
            "text":    "The right to privacy must be weighed against other important interests "
                       "such as public interest. Privacy rights must be developed case by case.",
            "year": 1975,
        },
    ]


# ── InLegalBERT standalone example ───────────────────────────────────────────

def run_legalbert_example(
    dataset_path: str | None = None,
    max_cases: int = 500,
) -> None:
    """Run InLegalBERT retrieval.

    Args:
        dataset_path: Path to LecAI CSV (file_Case_id_and_name.csv).
                      Falls back to built-in sample cases if None.
        max_cases:    Limit when loading from CSV.
    """
    print("=" * 60)
    print("InLegalBERT Integration Example")
    print("=" * 60)

    agent = InLegalBERTExternalAgent(
        model_name="law-ai/InLegalBERT",
        use_citation_weight=0.4,
        use_semantic_weight=0.6,
        device=None,  # auto
    )

    if dataset_path and Path(dataset_path).exists():
        print(f"\nLoading dataset from: {dataset_path}")
        n = agent.load_dataset(case_mapping_path=dataset_path, max_cases=max_cases)
        print(f"Loaded {n} cases")
    else:
        print("\nUsing built-in sample cases (set dataset_path for full dataset)")
        n = agent.load_dataset_from_dicts(_sample_cases())
        print(f"Loaded {n} sample cases")

    print("\nComputing InLegalBERT embeddings...")
    agent.compute_all_embeddings(batch_size=4)

    query_ids = list(agent.cases.keys())[:3]
    for qid in query_ids:
        name = agent.cases[qid]["case_name"]
        print(f"\nQuery: {name[:60]}")
        results = agent.retrieve_similar_cases(
            query_case_id=qid, top_k=2, use_citations=False
        )
        for r in results:
            print(f"  → {r['case_name'][:50]}  (score: {r['similarity_score']:.3f})")

    print("\nDone.")


# ── BioBERT standalone example ────────────────────────────────────────────────

def run_biobert_example(biobert_enabled: bool = False) -> None:
    """Run BioBERT retrieval on the same sample cases.

    BioBERT is disabled by default. Set BIOBERT_ENABLED=1 in .env to enable.
    """
    if not biobert_enabled:
        print("\nBioBERT skipped (set BIOBERT_ENABLED=1 in .env to enable)")
        return

    print("=" * 60)
    print("BioBERT Integration Example")
    print("=" * 60)

    agent = BioBERTExternalAgent(
        model_name="dmis-lab/biobert-base-cased-v1.2",
        use_citation_weight=0.3,
        use_semantic_weight=0.7,
        device=None,
    )

    n = agent.load_dataset_from_dicts(_sample_cases())
    print(f"Loaded {n} sample cases")

    print("Computing BioBERT embeddings...")
    agent.compute_all_embeddings(batch_size=4)

    qid = list(agent.cases.keys())[0]
    results = agent.retrieve_similar_cases(query_case_id=qid, top_k=2)
    print(f"\nQuery: {agent.cases[qid]['case_name'][:60]}")
    for r in results:
        print(f"  → {r['case_name'][:50]}  (score: {r['similarity_score']:.3f})")


# ── How Flask ModelRegistry wires this in ─────────────────────────────────────

def show_flask_usage() -> None:
    """Explain how the backend uses these agents (no models loaded here)."""
    print("""
Flask ModelRegistry (extensions.py) wires both agents:

    from app.extensions import model_registry

    # InLegalBERT (always available)
    legalbert = model_registry.get_legalbert_agent()

    # BioBERT (when BIOBERT_ENABLED=1 in .env)
    biobert = model_registry.get_biobert_agent()

The inference route (routes/inference.py) accepts ?model=legalbert|biobert|both
and delegates to the appropriate agent via ModelRegistry.

Models are loaded once on first request and reused for all subsequent calls.
""")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    lecai_base    = os.getenv("LECAI_BASE", "")
    dataset_csv   = os.path.join(lecai_base, "file_Case_id_and_name.csv") if lecai_base else None
    biobert_on    = os.getenv("BIOBERT_ENABLED", "0") == "1"

    run_legalbert_example(dataset_path=dataset_csv)
    run_biobert_example(biobert_enabled=biobert_on)
    show_flask_usage()
