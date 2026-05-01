"""
step1_classifier.py
────────────────────
STEP 1 — Domain Classification & Embedder Selection

Reads the first CLASSIFIER_WORDS words of the document, scores keyword
overlap against legal and medical lexicons, then decides:

    domain   →  "legal"   | "medical"
    embedder →  InLegalBERT | BioBERT

The chosen embedder key is attached to ClassifierResult so that main.py
can dispatch to the correct Step 2 module without any conditional logic
living outside this file.

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

# ── Domain lexicons ───────────────────────────────────────────────────────────

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

MEDICAL_KEYWORDS: frozenset[str] = frozenset({
    "patient", "diagnosis", "symptom", "treatment", "medication", "dosage",
    "clinical", "prognosis", "pathology", "etiology", "therapeutic",
    "surgery", "biopsy", "protocol", "contraindication", "adverse",
    "pharmacology", "anesthesia", "radiology", "oncology", "cardiology",
    "neurology", "pediatrics", "geriatrics", "immunology", "epidemiology",
    "comorbidity", "prophylaxis", "physician", "nurse", "hospital",
    "prescription", "laboratory", "specimen", "histology", "ecg", "mri",
    "ct scan", "biomarker", "syndrome", "disorder", "chronic", "acute",
    "benign", "malignant", "remission", "aetiology", "haematology",
    "triage", "icu", "ventilator", "intubation", "sepsis", "intravenous",
})

# ── Embedder registry ─────────────────────────────────────────────────────────
# Maps domain  →  (embedder_key, hf_model_name)
# Adding a new domain = one line here.

EMBEDDER_MAP: dict[str, tuple[str, str]] = {
    "medical": ("biobert",      "dmis-lab/biobert-base-cased-v1.2"),
    "legal":   ("inlegalbert",  "law-ai/InLegalBERT"),
}


# ── Core logic ────────────────────────────────────────────────────────────────

def _score_domain(text: str) -> tuple[str, float]:
    """
    Keyword-overlap scoring on *text*.
    Returns (domain, confidence_score ∈ [0,1]).
    """
    # Extract unigrams and bigrams from lowercased text
    lower = text.lower()
    tokens: set[str] = set(re.findall(r"[a-z]+", lower))
    bigrams: set[str] = set(
        a + " " + b
        for a, b in zip(lower.split(), lower.split()[1:])
    )
    word_set = tokens | bigrams

    legal_hits   = len(word_set & LEGAL_KEYWORDS)
    medical_hits = len(word_set & MEDICAL_KEYWORDS)
    total        = legal_hits + medical_hits

    logger.debug("Keyword hits — legal: %d  medical: %d", legal_hits, medical_hits)

    if total == 0:
        logger.warning(
            "No domain keywords detected in first %d words. "
            "Defaulting to 'legal' with low confidence.",
            CLASSIFIER_WORDS,
        )
        return "legal", 0.40

    if legal_hits >= medical_hits:
        return "legal",   round(legal_hits   / total, 3)
    else:
        return "medical", round(medical_hits / total, 3)


# ── Public entry point ────────────────────────────────────────────────────────

def run(state: PipelineState) -> PipelineState:
    """
    Classify the document domain and attach a ClassifierResult to *state*.

    The result includes the embedder_key that main.py should dispatch to.
    """
    t0 = time.perf_counter()

    # Take only the first CLASSIFIER_WORDS words
    words        = state.raw_text.split()
    sample       = " ".join(words[:CLASSIFIER_WORDS])
    words_used   = min(len(words), CLASSIFIER_WORDS)

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
