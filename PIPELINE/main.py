#!/usr/bin/env python3
"""
main.py — DocVerify Pipeline Orchestrator
==========================================

Invokes each step module in order, threading a single PipelineState
object through the whole pipeline.

Execution order
---------------
  Read file
       |
  step1_classifier.run()       -> ClassifierResult (domain + embedder_key)
       |
       +-- embedder_key="biobert"    --> step2_embed_biobert.run()
       |
       +-- embedder_key="inlegalbert"--> step2_embed_inlegalbert.run()
       |
       (both return EmbedResult: chunks + vectors)
       |
  step3_vectordb_search.run()  -> db_matches (VectorMatch list)
       |
  step4_coherence.run()        -> CoherenceResult (conflicts + score)
       |
  step5_output.run()           -> terminal report + optional JSON

Usage
-----
  python main.py path/to/document.txt
  python main.py document.pdf --db ./vectordb --top-k 8 --threshold 0.60
  python main.py document.txt --json
  python main.py document.txt --out report.json
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from models import PipelineState

import step1_classifier
import step2_embed_biobert
import step2_embed_inlegalbert
import step3_vectordb_search
import step4_coherence
import step5_output

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)-8s]  %(name)s -- %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("main")

# ---------------------------------------------------------------------------
# Embedder dispatch table
# Maps embedder_key (set by step1_classifier) -> step2 module.
# To add a new domain: create step2_embed_<name>.py and add one entry here.
# ---------------------------------------------------------------------------
EMBEDDER_DISPATCH = {
    "biobert":     step2_embed_biobert,
    "inlegalbert": step2_embed_inlegalbert,
}


# ---------------------------------------------------------------------------
# File reader
# ---------------------------------------------------------------------------
def _read_file(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        try:
            import pdfplumber
            with pdfplumber.open(path) as pdf:
                return "\n".join(p.extract_text() or "" for p in pdf.pages)
        except ImportError:
            logger.error(
                "pdfplumber not installed. "
                "Install it with: pip install pdfplumber"
            )
            sys.exit(1)
    return path.read_text(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Pipeline orchestrator
# ---------------------------------------------------------------------------
def run_pipeline(
    input_path:  Path,
    db_path:     Path,
    top_k:       int,
    threshold:   float,
    out_path:    Path | None,
    json_stdout: bool,
) -> PipelineState:
    """Execute all five steps and return the completed PipelineState."""

    t_total = time.perf_counter()

    # -- Read input file ------------------------------------------------------
    logger.info("Reading: %s", input_path)
    raw_text = _read_file(input_path)
    if not raw_text.strip():
        logger.error("File is empty: %s", input_path)
        sys.exit(1)

    state = PipelineState(
        input_file  = str(input_path.resolve()),
        raw_text    = raw_text,
        total_lines = raw_text.count("\n") + 1,
    )

    # -- Step 1: Domain classification ----------------------------------------
    logger.info(">> Step 1 -- Domain classifier")
    state = step1_classifier.run(state)

    embedder_key = state.classifier_result.embedder_key
    logger.info(
        "   Domain=%s  confidence=%.0f%%  dispatching to: %s",
        state.classifier_result.domain.upper(),
        state.classifier_result.confidence * 100,
        embedder_key,
    )

    # -- Step 2: Domain-specific embedder (dispatched) ------------------------
    embedder_module = EMBEDDER_DISPATCH.get(embedder_key)
    if embedder_module is None:
        logger.error(
            "No embedder registered for key '%s'. "
            "Add it to EMBEDDER_DISPATCH in main.py.",
            embedder_key,
        )
        sys.exit(1)

    logger.info(">> Step 2 -- Embedding  [%s]", embedder_key)
    state = embedder_module.run(state)

    # -- Step 3: VectorDB search ----------------------------------------------
    logger.info(">> Step 3 -- VectorDB search")
    state = step3_vectordb_search.run(
        state,
        db_path   = db_path,
        top_k     = top_k,
        threshold = threshold,
    )

    # -- Step 4: Intra-document coherence -------------------------------------
    logger.info(">> Step 4 -- Coherence & conflict detection")
    state = step4_coherence.run(state)

    # -- Step 5: Output -------------------------------------------------------
    logger.info(">> Step 5 -- Rendering output")
    step5_output.run(state, out_path=out_path, json_stdout=json_stdout)

    total_time = round(time.perf_counter() - t_total, 2)
    logger.info("Pipeline complete in %.2fs", total_time)

    return state


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="main.py",
        description="DocVerify — Domain-aware agentic document verification pipeline.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "file",
        help="Path to the document to verify (.txt, .md, .pdf).",
    )
    p.add_argument(
        "--db", default="./vectordb",
        help="Path to the VectorDB directory.",
    )
    p.add_argument(
        "--top-k", type=int, default=5,
        help="Number of VectorDB hits to retrieve per document chunk.",
    )
    p.add_argument(
        "--threshold", type=float, default=0.50,
        help="Minimum cosine similarity to include a VectorDB match.",
    )
    p.add_argument(
        "--out", default=None,
        help="Write a full JSON report to this file path.",
    )
    p.add_argument(
        "--json", action="store_true",
        help="Print JSON report to stdout instead of the formatted terminal output.",
    )
    p.add_argument(
        "--debug", action="store_true",
        help="Enable DEBUG-level logging.",
    )
    return p


def main() -> None:
    parser = _build_parser()
    args   = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    input_path = Path(args.file)
    if not input_path.exists():
        logger.error("File not found: %s", input_path)
        sys.exit(1)

    run_pipeline(
        input_path  = input_path,
        db_path     = Path(args.db),
        top_k       = args.top_k,
        threshold   = args.threshold,
        out_path    = Path(args.out) if args.out else None,
        json_stdout = args.json,
    )


if __name__ == "__main__":
    main()
