"""
step1_classifier.py
────────────────────
STEP 1 — Legal Domain Verification & Embedder Selection

Reads the first CLASSIFIER_WORDS words of the document, scores keyword
overlap against the legal lexicon, then verifies the document is legal
and selects InLegalBERT as the embedder.

    domain   →  "legal"
    embedder →  InLegalBERT

The embedder key is attached to ClassifierResult so that main.py
can dispatch to the correct Step 2 module.

Public API
──────────
    run(state: PipelineState) -> PipelineState
"""

from __future__ import annotations

import logging
import re
import time

from models import ClassifierResult, PipelineState

logger = logging.getLogger(__name__)

# ── Tunable ───────────────────────────────────────────────────────────────────

CLASSIFIER_WORDS = 1_000   # words examined for classification

# ── Domain lexicon ────────────────────────────────────────────────────────────

LEGAL_KEYWORDS: frozenset[str] = frozenset({
    "plaintiff", "defendant", "jurisdiction", "statute", "liability",
    "indemnify", "tort", "contract", "clause", "arbitration", "subpoena",
    "deposition", "counsel", "affidavit", "injunction", "litigation",
    "precedent", "verdict", "appeal", "amendment", "legislation",
    "regulatory", "compliance", "covenant", "breach", "damages", "remedy",
    "fiduciary", "intellectual property", "patent", "trademark", "copyright",
    "mortgage", "lien", "probate", "testimony", "witness", "exhibit",
    "motion", "ruling", "ordinance", "code", "provision", "party", "parties",
    "indictment", "acquittal", "sentence", "parole", "felony", "misdemeanor",
    "statute of limitations", "due process", "hearsay", "discovery",
})

# ── Embedder registry ─────────────────────────────────────────────────────────
# Maps domain  →  (embedder_key, hf_model_name)

EMBEDDER_MAP: dict[str, tuple[str, str]] = {
    "legal": ("inlegalbert", "law-ai/InLegalBERT"),
}


# ── Core logic ────────────────────────────────────────────────────────────────

def _score_domain(text: str) -> tuple[str, float]:
    """
    Keyword-overlap scoring on *text* against the legal lexicon.
    Returns ("legal", confidence_score ∈ [0,1]).
    """
    lower = text.lower()
    tokens: set[str] = set(re.findall(r"[a-z]+", lower))
    bigrams: set[str] = set(
        a + " " + b
        for a, b in zip(lower.split(), lower.split()[1:])
    )
    word_set = tokens | bigrams

    legal_hits = len(word_set & LEGAL_KEYWORDS)
    total_words = len(word_set)

    logger.debug("Keyword hits — legal: %d", legal_hits)

    if total_words == 0 or legal_hits == 0:
        logger.warning(
            "No legal keywords detected in first %d words. "
            "Proceeding with 'legal' domain at low confidence.",
            CLASSIFIER_WORDS,
        )
        return "legal", 0.40

    confidence = round(min(legal_hits / max(total_words * 0.05, 1), 1.0), 3)
    return "legal", confidence


# ── Public entry point ────────────────────────────────────────────────────────

def run(state: PipelineState) -> PipelineState:
    """
    Verify the document is a legal document and attach a ClassifierResult
    to *state* with InLegalBERT as the embedder.
    """
    t0 = time.perf_counter()

    # Take only the first CLASSIFIER_WORDS words
    words      = state.raw_text.split()
    sample     = " ".join(words[:CLASSIFIER_WORDS])
    words_used = min(len(words), CLASSIFIER_WORDS)

    domain, confidence = _score_domain(sample)

    embedder_key, embedder_model = EMBEDDER_MAP[domain]

    result = ClassifierResult(
        domain         = domain,
        confidence     = confidence,
        embedder_key   = embedder_key,
        embedder_model = embedder_model,
        word_sample    = words_used,
    )

    state.classifier_result = result
    state.timings["step1_classifier"] = round(time.perf_counter() - t0, 3)

    logger.info(
        "[Step 1] Domain: %s  (confidence=%.1f%%)  →  embedder: %s",
        domain.upper(), confidence * 100, embedder_key,
    )
    return state
