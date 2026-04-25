"""
step2_embed_biobert.py
───────────────────────
STEP 2 (medical path) — Embedding with BioBERT

Invoked by main.py when step1_classifier sets embedder_key = "biobert".

Model: dmis-lab/biobert-base-cased-v1.2
  • Domain-specific BERT pre-trained on PubMed abstracts + PMC full-text.
  • Mean-pools the last hidden state of each chunk → fixed-size vector.

Public API
──────────
    run(state: PipelineState) -> PipelineState
"""

from __future__ import annotations

import logging
import time

import numpy as np

from models import Chunk, EmbedResult, PipelineState
from utils  import chunk_text

logger = logging.getLogger(__name__)

MODEL_NAME   = "dmis-lab/biobert-base-cased-v1.2"
CHUNK_SIZE   = 200   # words per chunk
CHUNK_OVERLAP = 40   # word overlap between consecutive chunks
MAX_TOKENS   = 512   # BioBERT context window


# ── Model loader (module-level singleton) ────────────────────────────────────

_tokenizer = None
_model     = None

def _load_model():
    global _tokenizer, _model
    if _tokenizer is None:
        from transformers import AutoTokenizer, AutoModel
        logger.info("[Step 2 / BioBERT] Loading model: %s", MODEL_NAME)
        _tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        _model     = AutoModel.from_pretrained(MODEL_NAME)
        _model.eval()
        logger.info("[Step 2 / BioBERT] Model loaded.")


# ── Embedding function ────────────────────────────────────────────────────────

def _embed_texts(texts: list[str]) -> np.ndarray:
    """
    Embed a list of text strings.
    Returns float32 ndarray of shape (len(texts), hidden_size).
    """
    import torch
    _load_model()

    vecs = []
    for text in texts:
        inputs = _tokenizer(
            text,
            return_tensors = "pt",
            truncation     = True,
            max_length     = MAX_TOKENS,
            padding        = True,
        )
        with torch.no_grad():
            out = _model(**inputs)
        # Mean-pool last hidden state over token dimension
        vec = out.last_hidden_state.mean(dim=1).squeeze(0).numpy()
        vecs.append(vec)

    return np.array(vecs, dtype=np.float32)


# ── Public entry point ────────────────────────────────────────────────────────

def run(state: PipelineState) -> PipelineState:
    """
    Chunk the document text and embed every chunk with BioBERT.
    Attaches an EmbedResult to *state*.
    """
    t0 = time.perf_counter()

    raw_chunks = chunk_text(
        state.raw_text,
        chunk_size = CHUNK_SIZE,
        overlap    = CHUNK_OVERLAP,
    )

    chunks = [
        Chunk(index=i, start_line=sl, end_line=el, text=ct)
        for i, (sl, el, ct) in enumerate(raw_chunks)
    ]

    logger.info(
        "[Step 2 / BioBERT] Embedding %d chunks with %s …",
        len(chunks), MODEL_NAME,
    )

    vectors = _embed_texts([c.text for c in chunks])

    state.embed_result = EmbedResult(
        embedder_model = MODEL_NAME,
        chunks         = chunks,
        vectors        = vectors,
    )
    state.timings["step2_embed_biobert"] = round(time.perf_counter() - t0, 3)

    logger.info(
        "[Step 2 / BioBERT] Done — %d vectors, dim=%d  (%.2fs)",
        len(chunks), vectors.shape[1], state.timings["step2_embed_biobert"],
    )
    return state
