#!/usr/bin/env python3
"""
build_vectordb.py
==================
Scans a directory of known-good (trusted) documents, classifies each one,
embeds it with the appropriate domain model, and persists the results to the
flat-file VectorDB consumed by step3_vectordb_search.

This script is run once (or on a schedule) before using main.py.

Usage
-----:
  python build_vectordb.py --source ./known_good_docs --db ./vectordb
  python build_vectordb.py --source ./docs --db ./vectordb --reset
  python build_vectordb.py --source ./docs --chunk-size 150
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np

from step1_classifier import _score_domain, CLASSIFIER_WORDS,EMBEDDER_MAP
from utils import VectorDB, chunk_text

# Embedder modules (imported lazily per domain to avoid loading both models)
import step2_embed_biobert
import step2_embed_inlegalbert

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)-8s]  %(name)s -- %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("build_vectordb")

SUPPORTED_EXT = {".txt", ".md", ".pdf", ".rst"}

EMBEDDER_MODULES = {
    "biobert":     step2_embed_biobert,
    "inlegalbert": step2_embed_inlegalbert,
}


# ---------------------------------------------------------------------------
# Text extractor
# ---------------------------------------------------------------------------
def _extract_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        try:
            import pdfplumber
            with pdfplumber.open(path) as pdf:
                return "\n".join(p.extract_text() or "" for p in pdf.pages)
        except ImportError:
            logger.warning("pdfplumber missing; skipping PDF: %s", path)
            return ""
    return path.read_text(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------
def build(
    source_dir:  Path,
    db_path:     Path,
    reset:       bool = False,
    chunk_size:  int  = 200,
    chunk_overlap: int = 40,
) -> None:
    source_dir = Path(source_dir)
    if not source_dir.exists():
        logger.error("Source directory not found: %s", source_dir)
        sys.exit(1)

    db = VectorDB(db_path)
    if reset:
        db.metadata = []
        db.vectors  = None
        logger.info("VectorDB reset -- starting from scratch.")

    files = [
        p for p in source_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXT
    ]
    if not files:
        logger.error("No supported files found in: %s", source_dir)
        sys.exit(1)

    logger.info("Found %d document(s) in %s", len(files), source_dir)

    # -- Classify all files first, group by domain ----------------------------
    domain_groups: dict[str, list[tuple[Path, str]]] = {}   # domain -> [(path, text)]

    for fpath in files:
        text = _extract_text(fpath)
        if not text.strip():
            logger.warning("Empty file, skipping: %s", fpath)
            continue
        sample = " ".join(text.split()[:CLASSIFIER_WORDS])
        domain, score = _score_domain(sample)
        domain_groups.setdefault(domain, []).append((fpath, text))
        logger.info("  [%-8s %.0f%%]  %s", domain, score * 100, fpath.name)

    # -- Embed domain by domain (load each model only once) -------------------
    total_chunks = 0

    for domain, path_text_pairs in domain_groups.items():
        # Determine embedder key from the same map step1 uses
        from step1_classifier import EMBEDDER_MAP
        embedder_key, embedder_model = EMBEDDER_MAP[domain]
        embed_module = EMBEDDER_MODULES[embedder_key]

        # Load model once by embedding a dummy text
        logger.info(
            "\n-- Embedding %d %s document(s) with %s --",
            len(path_text_pairs), domain, embedder_model,
        )
        embed_module._load_model()
        embed_fn = embed_module._embed_texts

        for fpath, text in path_text_pairs:
            t0         = time.perf_counter()
            raw_chunks = chunk_text(text, chunk_size=chunk_size, overlap=chunk_overlap)

            chunk_meta:  list[dict] = []
            chunk_texts: list[str]  = []

            for idx, (sl, el, ct) in enumerate(raw_chunks):
                cid = f"{fpath.stem}__c{idx:04d}"
                chunk_meta.append({
                    "document":   fpath.name,
                    "chunk_id":   cid,
                    "start_line": sl,
                    "end_line":   el,
                    "text":       ct,
                    "domain":     domain,
                })
                chunk_texts.append(ct)

            logger.info(
                "  Embedding %d chunks from '%s' ...", len(raw_chunks), fpath.name
            )
            vecs = embed_fn(chunk_texts)
            db.add(chunk_meta, vecs)
            total_chunks += len(raw_chunks)

            logger.info(
                "  Done in %.1fs  (%d chunks)", time.perf_counter() - t0, len(raw_chunks)
            )

    db.save()
    logger.info("\nVectorDB built: %d total chunks -> %s", total_chunks, db_path)

    # Write human-readable manifest
    manifest = {
        "built_at":     time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_dir":   str(source_dir.resolve()),
        "total_chunks": total_chunks,
        "documents": [
            {"file": m["document"], "domain": m["domain"]}
            for m in {m["document"]: m for m in db.metadata}.values()
        ],
    }
    manifest_path = Path(db_path) / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    logger.info("Manifest -> %s", manifest_path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Build the DocVerify VectorDB from trusted reference documents.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--source",       default="./doc-store")
    parser.add_argument("--db",           default="./vectordb")
    parser.add_argument("--reset",        action="store_true")
    parser.add_argument("--chunk-size",   type=int, default=200)
    parser.add_argument("--chunk-overlap",type=int, default=40)
    args = parser.parse_args()

    build(
        source_dir    = Path(args.source),
        db_path       = Path(args.db),
        reset         = args.reset,
        chunk_size    = args.chunk_size,
        chunk_overlap = args.chunk_overlap,
    )
