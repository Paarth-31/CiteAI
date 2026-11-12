"""
utils.py — Shared utilities used by multiple pipeline steps.

  • chunk_text()  — word-level sliding-window chunker with line tracking
  • VectorDB      — flat-file cosine-similarity vector store
  • confidence_label() — maps similarity → HIGH / MEDIUM / LOW
"""

from __future__ import annotations
import json
import logging
import os
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

VECTORDB_PATH  = Path(os.getenv("VECTORDB_PATH", "./vectordb"))
SIM_THRESHOLD  = float(os.getenv("SIM_THRESHOLD", "0.50"))
TOP_K          = int(os.getenv("TOP_K", "5"))


# ── Chunker ───────────────────────────────────────────────────────────────────

def chunk_text(
    text: str,
    chunk_size: int = 200,
    overlap:    int = 40,
) -> list[tuple[int, int, str]]:
    """
    Split *text* into overlapping word-windows.

    Returns a list of (start_line, end_line, chunk_text) tuples.
    Line numbers are 1-based.
    """
    lines      = text.splitlines()
    words:      list[str] = []
    word_lines: list[int] = []

    for ln, line in enumerate(lines, start=1):
        for w in line.split():
            words.append(w)
            word_lines.append(ln)

    chunks = []
    i = 0
    while i < len(words):
        end         = min(i + chunk_size, len(words))
        chunk_words = words[i:end]
        start_line  = word_lines[i]
        end_line    = word_lines[end - 1]
        chunks.append((start_line, end_line, " ".join(chunk_words)))
        i += chunk_size - overlap

    return chunks


# ── Confidence helper ─────────────────────────────────────────────────────────

def confidence_label(sim: float) -> str:
    if sim >= 0.82:
        return "HIGH"
    if sim >= 0.65:
        return "MEDIUM"
    return "LOW"


# ── VectorDB ──────────────────────────────────────────────────────────────────

class VectorDB:
    """
    Disk-backed flat-file vector store.

    Layout on disk
    ──────────────
    <db_path>/
        index.json      – list of chunk-metadata dicts
        vectors.npy     – float32 array  shape (N, D)
        manifest.json   – human-readable build info (optional)
    """

    def __init__(self, db_path: Path = VECTORDB_PATH):
        self.db_path    = Path(db_path)
        self.index_file = self.db_path / "index.json"
        self.vec_file   = self.db_path / "vectors.npy"
        self.metadata:  list[dict]           = []
        self.vectors:   Optional[np.ndarray] = None
        self._load()

    # ── persistence ──────────────────────────────────────────────────────────

    def _load(self) -> None:
        if self.index_file.exists() and self.vec_file.exists():
            with open(self.index_file) as fh:
                self.metadata = json.load(fh)
                #fix: allowing serialized loading
            self.vectors = np.load(self.vec_file,allow_pickle = True)
            logger.info(
                "VectorDB loaded: %d chunks from %s",
                len(self.metadata), self.db_path,
            )
        else:
            logger.info(
                "VectorDB not found at %s — run build_vectordb.py first.",
                self.db_path,
            )

    def save(self) -> None:
        self.db_path.mkdir(parents=True, exist_ok=True)
        with open(self.index_file, "w") as fh:
            json.dump(self.metadata, fh, indent=2)
        np.save(self.vec_file, self.vectors)
        logger.info("VectorDB saved: %d chunks → %s", len(self.metadata), self.db_path)

    def add(self, chunks: list[dict], vectors: np.ndarray) -> None:
        """Append *chunks* metadata and their corresponding *vectors*."""
        if self.vectors is None:
            self.vectors = vectors
        else:
            self.vectors = np.vstack([self.vectors, vectors])
        self.metadata.extend(chunks)

    # ── search ────────────────────────────────────────────────────────────────

    def search(
        self,
        query_vec:  np.ndarray,
        top_k:      int   = TOP_K,
        threshold:  float = SIM_THRESHOLD,
    ) -> list[dict]:
        """
        Return up to *top_k* metadata dicts with an added ``similarity`` key,
        filtered to those whose cosine similarity is ≥ *threshold*.
        """
        if self.vectors is None or not self.metadata:
            return []

        q      = query_vec / (np.linalg.norm(query_vec) + 1e-9)
        norms  = np.linalg.norm(self.vectors, axis=1, keepdims=True) + 1e-9
        sims   = (self.vectors / norms) @ q          # (N,)

        top_idx = np.argsort(sims)[::-1][:top_k]
        results = []
        for i in top_idx:
            score = float(sims[i])
            if score >= threshold:
                results.append({**self.metadata[i], "similarity": round(score, 4)})
        return results
