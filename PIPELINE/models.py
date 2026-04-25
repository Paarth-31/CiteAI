"""
models.py — Shared dataclasses that flow between pipeline steps.

Data travels as plain Python objects in-process.
Every step receives the PipelineState and mutates/returns it.

Flow:
    PipelineState
        .classifier_result  → populated by step1_classifier
        .embed_result       → populated by step2_embed_*
        .db_matches         → populated by step3_vectordb_search
        .coherence_result   → populated by step4_coherence
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional
import numpy as np


# ── Step 1 output ─────────────────────────────────────────────────────────────

@dataclass
class ClassifierResult:
    domain:       str    # "legal" | "medical"
    confidence:   float  # 0–1 keyword-overlap score
    embedder_key: str    # "biobert" | "inlegalbert"
    embedder_model: str  # full HuggingFace model name
    word_sample:  int    # how many words were examined


# ── Step 2 output ─────────────────────────────────────────────────────────────

@dataclass
class Chunk:
    index:      int
    start_line: int
    end_line:   int
    text:       str


@dataclass
class EmbedResult:
    embedder_model: str
    chunks:         list[Chunk]
    vectors:        np.ndarray   # shape (N, D), float32


# ── Step 3 output ─────────────────────────────────────────────────────────────

@dataclass
class VectorMatch:
    chunk_index:      int    # which input chunk this came from
    source_line_start: int
    source_line_end:   int
    source_text:      str
    db_document:      str
    db_chunk_id:      str
    db_text:          str
    similarity:       float
    match_confidence: str    # "HIGH" | "MEDIUM" | "LOW"


# ── Step 4 output ─────────────────────────────────────────────────────────────

@dataclass
class Conflict:
    chunk_a_index: int
    chunk_b_index: int
    line_a_start:  int
    line_a_end:    int
    line_b_start:  int
    line_b_end:    int
    text_a:        str
    text_b:        str
    conflict_type: str    # "SEMANTIC_CONTRADICTION" | "DUPLICATE" | "NUMERICAL_MISMATCH"
    severity:      str    # "HIGH" | "MEDIUM" | "LOW"
    score:         float  # how strong the contradiction signal is (0–1)
    explanation:   str


@dataclass
class CoherenceResult:
    overall_coherence_score: float   # 0–1  (1 = perfectly coherent)
    coherence_label:         str     # "COHERENT" | "MINOR_ISSUES" | "CONFLICTED"
    total_chunks_examined:   int
    conflicts:               list[Conflict] = field(default_factory=list)


# ── Envelope that flows through all steps ────────────────────────────────────

@dataclass
class PipelineState:
    input_file:   str
    raw_text:     str
    total_lines:  int

    # Populated progressively
    classifier_result:  Optional[ClassifierResult]  = None
    embed_result:       Optional[EmbedResult]        = None
    db_matches:         list[VectorMatch]            = field(default_factory=list)
    coherence_result:   Optional[CoherenceResult]    = None

    # Timing (step name → seconds)
    timings: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialise to plain dict (numpy arrays → lists)."""
        d = asdict(self)
        # numpy arrays are not JSON-serialisable
        if "embed_result" in d and d["embed_result"]:
            d["embed_result"]["vectors"] = "omitted (numpy array)"
        return d
