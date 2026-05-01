"""
step4_coherence.py
───────────────────
STEP 4 — Intra-Document Coherence & Conflict Detection

Analyses the embedded chunks produced by Step 2 to find internal
contradictions, suspicious duplicates, and numerical mismatches within the
document itself (not against the DB — that is Step 3).

Three detectors run in sequence:

    1. SEMANTIC_CONTRADICTION
       Pairs of chunks that are *topically similar* (cos-sim ≥ TOPIC_SIM_FLOOR)
       but whose embeddings point in *opposing directions* after centering.
       Heuristic: high similarity in surface topic space + low similarity when
       we subtract the per-chunk mean, indicating a polarity flip.

    2. DUPLICATE
       Chunks with cosine similarity above DUP_THRESHOLD are flagged as
       potentially redundant / cut-paste errors.

    3. NUMERICAL_MISMATCH
       Chunks that share the same numeric anchor (dollar amount, date, dosage,
       percentage, etc.) but with different values are flagged.

Overall coherence score
───────────────────────
    score = 1 − (weighted_conflict_penalty / max_possible_penalty)

    Weights: HIGH=1.0  MEDIUM=0.5  LOW=0.2

Public API
──────────
    run(state: PipelineState) -> PipelineState
"""

from __future__ import annotations

import logging
import re
import time
from itertools import combinations

import numpy as np

from models import Chunk, Conflict, CoherenceResult, PipelineState

logger = logging.getLogger(__name__)

# ── Thresholds (all tunable) ──────────────────────────────────────────────────

TOPIC_SIM_FLOOR   = 0.55   # minimum similarity to consider a chunk-pair "on same topic"
CONTRA_SIM_CEIL   = 0.72   # pairs above this are probably duplicates, not contradictions
DUP_THRESHOLD     = 0.92   # cosine similarity → likely duplicate
MAX_PAIRS         = 2_000  # cap pairwise comparisons for large docs
CONFLICT_WEIGHTS  = {"HIGH": 1.0, "MEDIUM": 0.5, "LOW": 0.2}


# ── Severity helper ───────────────────────────────────────────────────────────

def _severity(score: float) -> str:
    if score >= 0.80:
        return "HIGH"
    if score >= 0.55:
        return "MEDIUM"
    return "LOW"


# ── Detector 1 — Semantic contradiction ──────────────────────────────────────

def _detect_contradictions(
    chunks:  list[Chunk],
    vecs:    np.ndarray,          # (N, D) normalised
) -> list[Conflict]:
    """
    Flag chunk-pairs that are on the same topic but semantically divergent.

    Method
    ──────
    After L2-normalising all vectors:
      • topic_sim  = vᵢ · vⱼ                   high → same topic area
      • contra_sim = (vᵢ − μ) · (vⱼ − μ)       low  → opposing sentiment/polarity

    Contradiction signal = topic_sim − contra_sim   (high = contradiction)
    """
    conflicts: list[Conflict] = []
    N = len(vecs)

    # L2-normalise
    norms  = np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-9
    normed = vecs / norms
    mu     = normed.mean(axis=0)
    centered = normed - mu

    pairs = list(combinations(range(N), 2))
    if len(pairs) > MAX_PAIRS:
        # Sample evenly to stay within budget
        step  = len(pairs) // MAX_PAIRS
        pairs = pairs[::step][:MAX_PAIRS]

    for i, j in pairs:
        topic_sim  = float(normed[i] @ normed[j])
        contra_sim = float(centered[i] @ centered[j])

        if topic_sim < TOPIC_SIM_FLOOR or topic_sim >= CONTRA_SIM_CEIL:
            continue

        signal = topic_sim - contra_sim   # ∈ [−1, 2] in practice ≈ [0, 1]
        score  = min(max(signal, 0.0), 1.0)

        if score < 0.40:
            continue

        conflicts.append(Conflict(
            chunk_a_index = chunks[i].index,
            chunk_b_index = chunks[j].index,
            line_a_start  = chunks[i].start_line,
            line_a_end    = chunks[i].end_line,
            line_b_start  = chunks[j].start_line,
            line_b_end    = chunks[j].end_line,
            text_a        = chunks[i].text[:200],
            text_b        = chunks[j].text[:200],
            conflict_type = "SEMANTIC_CONTRADICTION",
            severity      = _severity(score),
            score         = round(score, 4),
            explanation   = (
                f"Chunks share the same topic area (similarity={topic_sim:.2f}) "
                f"but diverge semantically after centering (centered_sim={contra_sim:.2f}), "
                f"suggesting contradictory claims."
            ),
        ))

    return conflicts


# ── Detector 2 — Duplicate detection ─────────────────────────────────────────

def _detect_duplicates(
    chunks: list[Chunk],
    vecs:   np.ndarray,
) -> list[Conflict]:
    """Flag near-identical chunk pairs (likely copy-paste errors)."""
    conflicts: list[Conflict] = []
    N = len(vecs)

    norms  = np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-9
    normed = vecs / norms

    for i in range(N):
        for j in range(i + 1, N):
            sim = float(normed[i] @ normed[j])
            if sim < DUP_THRESHOLD:
                continue
            score = sim
            conflicts.append(Conflict(
                chunk_a_index = chunks[i].index,
                chunk_b_index = chunks[j].index,
                line_a_start  = chunks[i].start_line,
                line_a_end    = chunks[i].end_line,
                line_b_start  = chunks[j].start_line,
                line_b_end    = chunks[j].end_line,
                text_a        = chunks[i].text[:200],
                text_b        = chunks[j].text[:200],
                conflict_type = "DUPLICATE",
                severity      = _severity(score),
                score         = round(score, 4),
                explanation   = (
                    f"Chunks are near-identical (similarity={sim:.3f}). "
                    f"This may indicate redundant content or an unintended copy."
                ),
            ))

    return conflicts


# ── Detector 3 — Numerical mismatch ──────────────────────────────────────────

# Patterns that capture "anchor + value" pairs
# e.g. "$1,200"  "3.5 mg"  "15%"  "2024-03-01"  "Section 4"
_NUM_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("currency",    re.compile(r"\$[\d,]+(?:\.\d+)?")),
    ("percentage",  re.compile(r"\b\d+(?:\.\d+)?\s*%")),
    ("dosage",      re.compile(r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|ml|mmol|iu)\b", re.I)),
    ("date",        re.compile(r"\b(?:\d{4}[-/]\d{2}[-/]\d{2}|\d{1,2}/\d{1,2}/\d{2,4})\b")),
    ("section_ref", re.compile(r"\b(?:section|clause|article|paragraph)\s+\d+(?:\.\d+)*\b", re.I)),
]

def _extract_anchors(text: str) -> dict[str, list[str]]:
    """Return {pattern_name: [matched_strings]} for a chunk of text."""
    return {name: pat.findall(text) for name, pat in _NUM_PATTERNS}


def _detect_numerical_mismatches(chunks: list[Chunk]) -> list[Conflict]:
    """
    Find pairs of chunks that reference the same *type* of numerical anchor
    but with different values — e.g. "$500" in one chunk and "$750" in another.
    """
    conflicts: list[Conflict] = []

    # Build per-chunk anchor index
    anchors = [_extract_anchors(c.text) for c in chunks]

    for i in range(len(chunks)):
        for j in range(i + 1, len(chunks)):
            for pattern_name in [p[0] for p in _NUM_PATTERNS]:
                vals_i = set(anchors[i][pattern_name])
                vals_j = set(anchors[j][pattern_name])

                if not vals_i or not vals_j:
                    continue
                if vals_i == vals_j:
                    continue   # same values — no mismatch

                # Overlap in *type* but not in value = mismatch
                mismatch_score = 0.75   # fixed heuristic severity
                conflicts.append(Conflict(
                    chunk_a_index = chunks[i].index,
                    chunk_b_index = chunks[j].index,
                    line_a_start  = chunks[i].start_line,
                    line_a_end    = chunks[i].end_line,
                    line_b_start  = chunks[j].start_line,
                    line_b_end    = chunks[j].end_line,
                    text_a        = chunks[i].text[:200],
                    text_b        = chunks[j].text[:200],
                    conflict_type = "NUMERICAL_MISMATCH",
                    severity      = _severity(mismatch_score),
                    score         = mismatch_score,
                    explanation   = (
                        f"Both chunks contain {pattern_name} values but they differ. "
                        f"Chunk A has {sorted(vals_i)}, Chunk B has {sorted(vals_j)}."
                    ),
                ))

    return conflicts


# ── Overall coherence scoring ─────────────────────────────────────────────────

def _compute_coherence(conflicts: list[Conflict], n_chunks: int) -> tuple[float, str]:
    """
    Returns (score ∈ [0,1], label).

    Penalty is normalised against the theoretical maximum (all chunks conflict
    at HIGH severity) so the score is comparable across document sizes.
    """
    if n_chunks < 2:
        return 1.0, "COHERENT"

    max_pairs = n_chunks * (n_chunks - 1) / 2
    max_penalty = max_pairs * CONFLICT_WEIGHTS["HIGH"]

    penalty = sum(CONFLICT_WEIGHTS.get(c.severity, 0.2) for c in conflicts)
    score   = max(0.0, 1.0 - (penalty / max_penalty))
    score   = round(score, 4)

    if score >= 0.85:
        label = "COHERENT"
    elif score >= 0.60:
        label = "MINOR_ISSUES"
    else:
        label = "CONFLICTED"

    return score, label


# ── Public entry point ────────────────────────────────────────────────────────

def run(state: PipelineState) -> PipelineState:
    """
    Run all three conflict detectors and compute an overall coherence score.
    Attaches a CoherenceResult to *state*.
    """
    t0 = time.perf_counter()

    assert state.embed_result is not None, \
        "Step 4 requires embed_result — run Step 2 first."

    chunks = state.embed_result.chunks
    vecs   = state.embed_result.vectors

    logger.info(
        "[Step 4] Running coherence checks on %d chunks …", len(chunks)
    )

    all_conflicts: list[Conflict] = []

    # ── Detector 1 ───────────────────────────────────────────────────────────
    contra = _detect_contradictions(chunks, vecs)
    logger.info("[Step 4] Semantic contradictions: %d", len(contra))
    all_conflicts.extend(contra)

    # ── Detector 2 ───────────────────────────────────────────────────────────
    dups = _detect_duplicates(chunks, vecs)
    logger.info("[Step 4] Duplicates: %d", len(dups))
    all_conflicts.extend(dups)

    # ── Detector 3 ───────────────────────────────────────────────────────────
    num_mis = _detect_numerical_mismatches(chunks)
    logger.info("[Step 4] Numerical mismatches: %d", len(num_mis))
    all_conflicts.extend(num_mis)

    # Sort: severity HIGH first, then by score desc
    severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    all_conflicts.sort(key=lambda c: (severity_order[c.severity], -c.score))

    score, label = _compute_coherence(all_conflicts, len(chunks))

    state.coherence_result = CoherenceResult(
        overall_coherence_score = score,
        coherence_label         = label,
        total_chunks_examined   = len(chunks),
        conflicts               = all_conflicts,
    )
    state.timings["step4_coherence"] = round(time.perf_counter() - t0, 3)

    logger.info(
        "[Step 4] Coherence: %s (score=%.3f)  |  total conflicts: %d  (%.2fs)",
        label, score, len(all_conflicts), state.timings["step4_coherence"],
    )
    return state
