"""OCR agent for legal PDF documents.

Pipeline per document:
  1. pdfplumber  — raw text extraction (page by page)
  2. regex       — structured pattern extraction:
                     citations  (A v. B, AIR XXXX SC N, 2019 (4) SCC)
                     articles   (Article 21, Section 34(2), Sec. 302 IPC)
                     title      (first "X v. Y" line or first ALL-CAPS line)
  3. TF-IDF      — keyword extraction:
                     top-N important legal terms from the document body,
                     used downstream by the inference agent for richer
                     context-fit scoring.

Why both regex AND TF-IDF?
  Regex finds STRUCTURED patterns with known formats (citation strings,
  article references). TF-IDF finds IMPORTANT VOCABULARY — legal concepts,
  named principles, recurring terms — that regex cannot detect because they
  have no fixed structure. They serve different roles and are complementary.
"""
from __future__ import annotations

import os
import re
import json
import logging
from typing import Any

import pdfplumber
from sklearn.feature_extraction.text import TfidfVectorizer

logger = logging.getLogger(__name__)

# ── TF-IDF keyword extractor (module-level singleton) ─────────────────────────
# Fitted per-document in extract_keywords(). A light single-document TF-IDF
# ranks terms by their frequency weight relative to common English stop words.
_TFIDF_STOP_WORDS = "english"
_KEYWORD_MAX_FEATURES = 1000   # vocabulary cap
_KEYWORD_TOP_N = 30            # keywords returned per document

# ── Regex patterns ────────────────────────────────────────────────────────────
_CITATION_PATTERNS = [
    # A v. B  /  A vs. B  /  A v B
    r"[A-Z][A-Za-z&\s,]{2,40}?v\.?[sS]?\.?\s+[A-Z][A-Za-z&\s,]{2,40}",
    # AIR 1992 SC 604
    r"AIR\s?\d{4}\s?[A-Z]{1,5}\s?\d+",
    # 2019 (4) SCC 1
    r"\d{4}\s?\(\d+\)\s?[A-Z]{2,5}",
    # (2017) 10 SCC 1
    r"\(\d{4}\)\s?\d+\s?[A-Z]{2,5}",
]

_ARTICLE_PATTERNS = [
    r"Article\s+\d+[A-Z]?",
    r"Section\s+\d+[A-Z]?(?:\(\d+\))?(?:\([a-z]\))?",
    r"Sec\.\s*\d+[A-Z]?",
    r"Clause\s+\(?[0-9a-z]+\)?",
]

# Legal stop-words that are common but not informative as keywords
_LEGAL_STOP_WORDS = {
    "court", "judge", "judgment", "petition", "petitioner", "respondent",
    "appellant", "said", "held", "case", "matter", "order", "bench",
    "hon", "honourable", "vs", "versus", "also", "thus", "therefore",
}


# ── Text extraction ───────────────────────────────────────────────────────────

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract all text from a PDF using pdfplumber, page by page."""
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                pages.append(page_text)
    return "\n".join(pages).strip()


# ── Regex extraction ──────────────────────────────────────────────────────────

def extract_title(text: str) -> str:
    """Extract the case title from the first 10 non-empty lines.

    Looks for:
      1. A line containing "v." / "vs." (most reliable)
      2. An ALL-CAPS line with 3+ words
      3. Falls back to the first non-empty line
    """
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    for line in lines[:10]:
        if re.search(r"\bv\.?\s+|vs\.", line, re.IGNORECASE):
            return line
        if line.isupper() and len(line.split()) > 2:
            return line
    return lines[0] if lines else "Untitled Document"


def extract_citations(text: str) -> list[str]:
    """Extract legal citation strings using regex patterns.

    Returns a deduplicated list of raw citation strings.
    Regex is the correct tool here — citations are structured patterns
    with known formats that TF-IDF cannot reliably detect.
    """
    found: dict[str, None] = {}
    for pattern in _CITATION_PATTERNS:
        for match in re.findall(pattern, text):
            cleaned = match.strip()
            if len(cleaned) > 5:          # filter noise
                found[cleaned] = None
    return list(found.keys())


def extract_articles(text: str) -> list[str]:
    """Extract Article / Section / Clause references using regex."""
    found: dict[str, None] = {}
    for pattern in _ARTICLE_PATTERNS:
        for match in re.findall(pattern, text, flags=re.IGNORECASE):
            found[match.strip()] = None
    return list(found.keys())


# ── TF-IDF keyword extraction ─────────────────────────────────────────────────

def extract_keywords(text: str, top_n: int = _KEYWORD_TOP_N) -> list[str]:
    """Extract the top-N important terms from a document using TF-IDF.

    Unlike regex, this captures legal concepts, named principles, and
    domain vocabulary that have no fixed pattern — e.g. "proportionality",
    "informational autonomy", "surveillance", "data protection".

    These keywords are stored in the OCR output and used downstream by the
    ExternalInferenceAgent to compute a richer context-fit (C) score in TRS.

    Args:
        text:  Full document text.
        top_n: Number of top keywords to return.

    Returns:
        Ordered list of keywords, highest weight first.
    """
    if not text or len(text.split()) < 20:
        return []

    try:
        # Single-document TF-IDF: term frequency weighted by inverse
        # document frequency learned from a background English vocabulary.
        # sublinear_tf dampens the effect of very high-frequency terms.
        vectorizer = TfidfVectorizer(
            max_features=_KEYWORD_MAX_FEATURES,
            stop_words=_TFIDF_STOP_WORDS,
            sublinear_tf=True,
            ngram_range=(1, 2),         # unigrams + bigrams for legal phrases
            min_df=1,
            token_pattern=r"(?u)\b[A-Za-z][A-Za-z]+\b",  # alpha only, len >= 2
        )
        tfidf_matrix = vectorizer.fit_transform([text])
        feature_names = vectorizer.get_feature_names_out()
        scores = tfidf_matrix.toarray()[0]

        # Pair (term, score), filter legal stop-words, sort descending
        term_scores = [
            (feature_names[i], scores[i])
            for i in range(len(feature_names))
            if scores[i] > 0 and feature_names[i].lower() not in _LEGAL_STOP_WORDS
        ]
        term_scores.sort(key=lambda x: x[1], reverse=True)

        return [term for term, _ in term_scores[:top_n]]

    except Exception as exc:
        logger.warning("TF-IDF keyword extraction failed: %s", exc)
        return []


# ── Main pipeline ─────────────────────────────────────────────────────────────

def process_pdf(
    pdf_path: str,
    output_dir: str | None = None,
) -> dict[str, Any]:
    """Run the full OCR + extraction pipeline for a single PDF.

    Args:
        pdf_path:   Path to the PDF file.
        output_dir: If provided, save the JSON result here.
                    Pass None (default) when called from Flask to skip
                    the disk write — the caller caches to the DB instead.

    Returns:
        {
          "file_name":  str,
          "title":      str,
          "full_text":  str,          ← key used by Flask OCR route
          "citations":  list[str],    ← regex-extracted citation strings
          "articles":   list[str],    ← regex-extracted article references
          "keywords":   list[str],    ← TF-IDF top-N legal terms
          "pages":      list[str],    ← per-page text (for metadata)
          "stats": {
            "num_pages":     int,
            "num_citations": int,
            "num_articles":  int,
            "num_keywords":  int,
          }
        }
    """
    # ── Step 1: pdfplumber text extraction ────────────────────────────────
    with pdfplumber.open(pdf_path) as pdf:
        page_texts = []
        for page in pdf.pages:
            pt = page.extract_text()
            if pt:
                page_texts.append(pt)

    full_text = "\n".join(page_texts).strip()

    # ── Step 2: regex — structured pattern extraction ─────────────────────
    title     = extract_title(full_text)
    citations = extract_citations(full_text)
    articles  = extract_articles(full_text)

    # ── Step 3: TF-IDF — important legal keyword extraction ───────────────
    keywords = extract_keywords(full_text)

    result: dict[str, Any] = {
        "file_name": os.path.basename(pdf_path),
        "title":     title,
        "full_text": full_text,         # used by Flask OCR route
        "raw_text":  full_text,         # kept for backward compatibility
        "citations": citations,
        "articles":  articles,
        "keywords":  keywords,
        "pages":     page_texts,
        "stats": {
            "num_pages":     len(page_texts),
            "num_citations": len(citations),
            "num_articles":  len(articles),
            "num_keywords":  len(keywords),
        },
    }

    # ── Optional disk save (skipped when called from Flask) ───────────────
    if output_dir is not None:
        os.makedirs(output_dir, exist_ok=True)
        base = os.path.splitext(os.path.basename(pdf_path))[0]
        out_path = os.path.join(output_dir, base + ".json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        logger.info("OCR result saved: %s", out_path)

    logger.info(
        "Processed %s — %d pages, %d citations, %d articles, %d keywords",
        os.path.basename(pdf_path),
        len(page_texts), len(citations), len(articles), len(keywords),
    )
    return result
