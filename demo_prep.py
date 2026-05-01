"""
CiteAI Demo Preparation Script
================================
Run this ONCE before the evaluator demo to pre-process all 4 sample cases.
It builds the citation graph, runs OCR, and saves results so the demo
responds instantly without any waiting.

Usage (from CiteAI root, with venv active):
    python demo_prep.py

What it does:
    1. Builds citation graph from lexai/data/lecai_baseline/*.txt
    2. Saves graph to lexai/data/graphs/lecai_citation_graph.json
    3. Runs the full OCR + keyword extraction on each .txt case
    4. Saves per-case OCR JSON to lexai/data/processed/
    5. Prints a summary so you know everything is ready

After running this, the demo flow is:
    Upload PDF → backend finds cached OCR → instant citation graph → inference
"""

import json
import sys
from pathlib import Path

# Ensure project root is importable
_ROOT = Path(__file__).parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "lexai"))      # ← fixes lexai import
DATA_DIR      = Path("lexai/data/lecai_baseline")
GRAPH_OUT     = Path("lexai/data/graphs/lecai_citation_graph.json")
PROCESSED_DIR = Path("lexai/data/processed")

def step1_build_citation_graph():
    print("\n" + "="*60)
    print("STEP 1 — Building citation graph from sample cases")
    print("="*60)

    from citation_graph_builder import CitationGraphBuilder

    builder = CitationGraphBuilder()
    num_nodes, num_edges = builder.build_graph(DATA_DIR)
    GRAPH_OUT.parent.mkdir(parents=True, exist_ok=True)
    builder.save_json(GRAPH_OUT)

    print(f"  ✓ {num_nodes} nodes, {num_edges} edges")
    print(f"  ✓ Saved → {GRAPH_OUT}")
    return builder

def step2_ocr_all_cases():
    print("\n" + "="*60)
    print("STEP 2 — Running OCR + TF-IDF on all .txt cases")
    print("="*60)

    from lexai.agents.ocr_agent import extract_title, extract_citations, extract_articles, extract_keywords

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    case_files = sorted(DATA_DIR.glob("*.txt"))

    for case_file in case_files:
        text = case_file.read_text(encoding="utf-8")
        title     = extract_title(text)
        citations = extract_citations(text)
        articles  = extract_articles(text)
        keywords  = extract_keywords(text)

        result = {
            "file_name": case_file.name,
            "title":     title,
            "full_text": text,
            "citations": citations,
            "articles":  articles,
            "keywords":  keywords,
            "stats": {
                "num_citations": len(citations),
                "num_articles":  len(articles),
                "num_keywords":  len(keywords),
            }
        }

        out_path = PROCESSED_DIR / (case_file.stem + ".json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print(f"  ✓ {case_file.name}: {len(citations)} citations, {len(keywords)} keywords")
        print(f"    Title   : {title[:70]}")
        print(f"    Keywords: {', '.join(keywords[:8])}")
        print()

def step3_verify_inlegalbert():
    print("="*60)
    print("STEP 3 — Verifying InLegalBERT loads correctly")
    print("="*60)

    try:
        from lexai.agents.inlegalbert_external_agent import InLegalBERTExternalAgent
        agent = InLegalBERTExternalAgent(
            model_name="law-ai/InLegalBERT",
            device="cpu",
        )

        # Load all 4 sample cases
        cases = []
        for jf in sorted(PROCESSED_DIR.glob("*.json")):
            with open(jf, encoding="utf-8") as f:
                data = json.load(f)
            cases.append({
                "case_id": jf.stem,
                "title":   data["title"],
                "text":    data["full_text"],
            })

        n = agent.load_dataset_from_dicts(cases)
        print(f"  ✓ InLegalBERT loaded, {n} cases indexed")

        agent.compute_all_embeddings(batch_size=2)
        print(f"  ✓ Embeddings computed")

        # Quick retrieval test
        qid = cases[0]["case_id"]
        results = agent.retrieve_similar_cases(query_case_id=qid, top_k=2, use_citations=False)
        print(f"  ✓ Test retrieval for '{cases[0]['title'][:50]}':")
        for r in results:
            print(f"      → {r['case_name'][:50]}  (score: {r['similarity_score']:.3f})")

    except Exception as e:
        print(f"  ✗ InLegalBERT check failed: {e}")
        print("    Make sure you ran: python -c \"from transformers import AutoModel; AutoModel.from_pretrained('law-ai/InLegalBERT')\"")

def main():
    print("\n" + "="*60)
    print("CiteAI DEMO PREPARATION")
    print("="*60)
    print("Pre-processing 4 sample cases for evaluator demo...")

    step1_build_citation_graph()
    step2_ocr_all_cases()
    step3_verify_inlegalbert()

    print("\n" + "="*60)
    print("✅ DEMO PREP COMPLETE")
    print("="*60)
    print("\nAll 4 cases processed and ready.")
    print("\nTo run the full project:")
    print("  Terminal 1:  cd backend && python init_db.py && flask run --port=8000")
    print("  Terminal 2:  cd website && bun dev")
    print("  Browser:     http://localhost:3000")
    print()

if __name__ == "__main__":
    main()
