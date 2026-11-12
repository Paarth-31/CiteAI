"""Domain agent integration example for InLegalBERT."""
from __future__ import annotations

import os
from pathlib import Path

from lexai.agents import InLegalBERTExternalAgent

BASE_DIR = Path(__file__).resolve().parent.parent

# -- Standalone demo helpers ---------------------------------------------------

def _sample_cases() -> list[dict]:
    """Minimal sample dataset - no CSV required."""
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


# -- InLegalBERT standalone example -------------------------------------------

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
            print(f"  -> {r['case_name'][:50]}  (score: {r['similarity_score']:.3f})")

    print("\nDone.")


# -- How Flask ModelRegistry wires this in -------------------------------------

def show_flask_usage() -> None:
    """Explain how the backend uses the InLegalBERT agent (no models loaded here)."""
    print("""
Flask ModelRegistry (extensions.py) wires the agent:

    from app.extensions import model_registry

    # InLegalBERT (always available)
    legalbert = model_registry.get_legalbert_agent()

The inference route (routes/inference.py) accepts ?model=legalbert
and delegates to the agent via ModelRegistry.

Models are loaded once on first request and reused for all subsequent calls.
""")


# -- Entry point ---------------------------------------------------------------

if __name__ == "__main__":
    lecai_base  = os.getenv("LECAI_BASE", "")
    dataset_csv = os.path.join(lecai_base, "file_Case_id_and_name.csv") if lecai_base else None

    run_legalbert_example(dataset_path=dataset_csv)
    show_flask_usage()