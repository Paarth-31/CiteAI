"""
step3_vectordb_search.py
─────────────────────────
STEP 3 — VectorDB Similarity Search

For every embedded chunk produced by Step 2, runs a cosine-similarity search
against the trusted VectorDB and collects all hits above the similarity
threshold.

Results are de-duplicated per (source_chunk, db_chunk) pair, sorted by
similarity descending, and attached to state.db_matches.

Public API
──────────
    run(state: PipelineState, db_path, top_k, threshold) -> PipelineState
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from models import PipelineState, VectorMatch
from utils  import VectorDB, confidence_label, SIM_THRESHOLD, TOP_K

logger = logging.getLogger(__name__)


# ── Public entry point ────────────────────────────────────────────────────────

def run(
    state:     PipelineState,
    db_path:   Path  = Path(os.getenv("VECTORDB_PATH", "./vectordb")),
    top_k:     int   = TOP_K,
    threshold: float = SIM_THRESHOLD,
) -> PipelineState:
    """
    Search the VectorDB for each embedded chunk.
    Populates state.db_matches with VectorMatch objects.
    """
    t0 = time.perf_counter()

    assert state.embed_result is not None, \
        "Step 3 requires embed_result — run Step 2 first."

    db     = VectorDB(db_path)
    chunks = state.embed_result.chunks
    vecs   = state.embed_result.vectors   # (N, D)

    if db.vectors is None:
        logger.warning(
            "[Step 3] VectorDB is empty — no matches possible. "
            "Run build_vectordb.py first."
        )
        state.timings["step3_vectordb_search"] = round(time.perf_counter() - t0, 3)
        return state

    seen:    set[tuple[int, str]] = set()    # (chunk_index, db_chunk_id) dedup key
    matches: list[VectorMatch]   = []

    for chunk, vec in zip(chunks, vecs):
        hits = db.search(vec, top_k=top_k, threshold=threshold)
        for hit in hits:
            dedup_key = (chunk.index, hit["chunk_id"])
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            matches.append(VectorMatch(
                chunk_index       = chunk.index,
                source_line_start = chunk.start_line,
                source_line_end   = chunk.end_line,
                source_text       = chunk.text[:350],
                db_document       = hit["document"],
                db_chunk_id       = hit["chunk_id"],
                db_text           = hit["text"][:350],
                similarity        = hit["similarity"],
                match_confidence  = confidence_label(hit["similarity"]),
            ))

    matches.sort(key=lambda m: m.similarity, reverse=True)
    state.db_matches = matches
    state.timings["step3_vectordb_search"] = round(time.perf_counter() - t0, 3)

    logger.info(
        "[Step 3] %d matches found across %d chunks  (%.2fs)",
        len(matches), len(chunks),
        state.timings["step3_vectordb_search"],
    )
    return state
