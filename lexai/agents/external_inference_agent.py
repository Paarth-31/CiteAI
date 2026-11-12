"""External Inference Agent for legal document similarity and retrieval.

Key optimisations over previous version:
  1. TF-IDF vectorizer is fitted ONCE on the candidate corpus during
     build_index() and reused for every call to _estimate_context_fit()
     and _extract_support_spans(). Previously a new vectorizer was
     instantiated on every single call — major bottleneck removed.

  2. Accepts a pre-loaded SentenceTransformer from ModelRegistry via the
     `sentence_model` parameter, so models are not reloaded per request.

  3. OCR keywords (from ocr_agent TF-IDF extraction) are used to boost
     the context-fit score when available, giving a richer C score in TRS.

  4. infer() correctly handles both plain string and dict targets throughout,
     including the final result dict construction.

  5. Demo / test functions moved to external_inference_agent_demo.py to
     keep this file focused on the agent class.

Usage:
    from app.extensions import model_registry
    sentence_model = model_registry.get_sentence_model()

    agent = ExternalInferenceAgent(sentence_model=sentence_model)
    agent.build_index(candidates_list)
    result = agent.infer(target_case, top_k=5)
"""
from __future__ import annotations

import re
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


class ExternalInferenceAgent:
    """Similarity-based inference agent for legal documents.

    Uses sentence-transformer embeddings + FAISS for retrieval, then
    re-ranks results using the Trust Relevance Score (TRS):

        TRS = w_S·S + w_C·C + w_J·J + w_I·I - w_U·U

    where:
        S  — semantic similarity (FAISS inner product on normalised vectors)
        C  — context fit (TF-IDF cosine similarity, vectorizer fitted once)
        J  — jurisdiction + temporal alignment
        I  — internal confidence (optional, from coherence agent)
        U  — uncertainty (variance between S and C)
    """

    def __init__(
        self,
        embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        trs_weights: Optional[Dict[str, float]] = None,
        retriever: Optional[Callable] = None,
        device: Optional[str] = None,
        sentence_model: Optional[SentenceTransformer] = None,
    ) -> None:
        """
        Args:
            embedding_model_name: HuggingFace model name. Ignored if
                                  sentence_model is provided directly.
            trs_weights:          Override default TRS factor weights.
            retriever:            Optional custom retriever function.
            device:               'cuda', 'cpu', or None (auto).
            sentence_model:       Pre-loaded SentenceTransformer from
                                  ModelRegistry. Pass this to avoid
                                  reloading the model per request.
        """
        self.model_name = embedding_model_name
        self.device = device

        # Accept pre-loaded model from ModelRegistry (avoids reload)
        self.model: Optional[SentenceTransformer] = sentence_model

        self.index: Optional[faiss.IndexFlatIP] = None
        self.candidates: List[Dict[str, Any]] = []
        self.candidate_embeddings: Optional[np.ndarray] = None
        self.custom_retriever = retriever

        # TF-IDF vectorizer — fitted once in build_index(), reused everywhere
        self._tfidf_vectorizer: Optional[TfidfVectorizer] = None
        self._tfidf_matrix = None   # shape: (n_candidates, n_features)

        self.trs_weights: Dict[str, float] = trs_weights or {
            "w_S": 0.50,   # semantic similarity
            "w_C": 0.20,   # context fit
            "w_J": 0.10,   # jurisdiction score
            "w_I": 0.15,   # internal confidence
            "w_U": 0.05,   # uncertainty (subtracted)
        }

    # ── Index building ────────────────────────────────────────────────────────

    def build_index(
        self,
        candidates: List[Dict[str, Any]],
        text_field: str = "text",
    ) -> None:
        """Build FAISS index and fit TF-IDF vectorizer from candidates.

        Both are fitted here once. All subsequent scoring calls reuse them.

        Args:
            candidates: List of dicts, each must contain `text_field`.
            text_field: Key in each dict that holds the text to embed.

        Raises:
            ValueError: candidates empty or missing text field / wrong type.
        """
        if not candidates:
            raise ValueError("Candidates list cannot be empty")

        for idx, cand in enumerate(candidates):
            if text_field not in cand:
                raise ValueError(
                    f"Candidate at index {idx} is missing required field '{text_field}'"
                )
            if not isinstance(cand[text_field], str):
                raise ValueError(
                    f"Candidate at index {idx} has non-string value for '{text_field}'"
                )

        texts = [c[text_field] for c in candidates]

        # ── Load sentence-transformer if not pre-supplied ─────────────────
        if self.model is None:
            logger.info("Loading sentence-transformer: %s", self.model_name)
            self.model = SentenceTransformer(self.model_name, device=self.device)

        # ── Sentence embeddings + FAISS ───────────────────────────────────
        embeddings = self.model.encode(
            texts,
            convert_to_numpy=True,
            show_progress_bar=len(texts) > 50,
            normalize_embeddings=False,
        )
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        normed = embeddings / (norms + 1e-10)

        dimension = normed.shape[1]
        self.index = faiss.IndexFlatIP(dimension)
        self.index.add(normed.astype("float32"))

        # ── TF-IDF corpus vectorizer (fitted once here) ───────────────────
        # Enriched with OCR keywords when available:
        # if a candidate has a "keywords" list from ocr_agent, append those
        # terms to its text so they get higher weight in TF-IDF space.
        enriched_texts = []
        for cand, raw_text in zip(candidates, texts):
            kw = cand.get("keywords", [])
            enriched = raw_text + (" " + " ".join(kw) * 3 if kw else "")
            enriched_texts.append(enriched)

        self._tfidf_vectorizer = TfidfVectorizer(
            max_features=2000,
            stop_words="english",
            sublinear_tf=True,
            ngram_range=(1, 2),
        )
        self._tfidf_matrix = self._tfidf_vectorizer.fit_transform(enriched_texts)

        self.candidates = candidates
        self.candidate_embeddings = normed

        logger.info(
            "Index built — %d candidates, dim=%d, TF-IDF vocab=%d",
            len(candidates), dimension,
            len(self._tfidf_vectorizer.vocabulary_),
        )

    # ── Inference ─────────────────────────────────────────────────────────────

    def infer(
        self,
        target: str | Dict[str, Any],
        top_k: int = 5,
        internal_confidence: Optional[float] = None,
        return_factors: bool = False,
    ) -> Dict[str, Any]:
        """Find the most relevant candidate cases for a target.

        Args:
            target:              Plain string OR dict with at least "text".
                                 Dict may also carry "year", "jurisdiction",
                                 "case_id", "title", "keywords".
            top_k:               Number of results.
            internal_confidence: Optional coherence-agent confidence [0,1].
            return_factors:      Include per-factor breakdown in each result.

        Returns:
            {
              "target":                        {...},
              "retrieved_cases":               [...],
              "overall_external_coherence_score": float,
              "short_summary":                 str,
            }
        """
        if self.index is None or not self.candidates:
            raise ValueError("Index has not been built. Call build_index() first.")

        # ── Normalise target ──────────────────────────────────────────────
        if isinstance(target, str):
            target_text         = target
            target_year         = None
            target_jurisdiction = "Unknown"
            target_id           = "query"
            target_title        = target[:60]
            target_keywords: list[str] = []
        else:
            if "text" not in target:
                raise ValueError("Target dict is missing required field 'text'")
            target_text         = target["text"]
            target_year         = target.get("year")
            target_jurisdiction = target.get("jurisdiction", "Unknown")
            target_id           = target.get("case_id", target.get("id", "query"))
            target_title        = target.get("title", target_text[:60])
            target_keywords     = target.get("keywords", [])

        # ── Retrieve via FAISS or custom retriever ────────────────────────
        if self.custom_retriever is not None:
            raw_retrieved = self.custom_retriever(target_text, top_k)
        else:
            raw_retrieved = self._retrieve_candidates(target_text, top_k)

        # ── Encode target for TF-IDF context fit ─────────────────────────
        if self._tfidf_vectorizer is None:
            raise ValueError("TF-IDF vectorizer not fitted. Call build_index() first.")

        enriched_target = target_text + (
            " " + " ".join(target_keywords) * 3 if target_keywords else ""
        )
        target_tfidf = self._tfidf_vectorizer.transform([enriched_target])

        # ── Score each candidate ──────────────────────────────────────────
        retrieved_cases = []
        for candidate_idx, similarity_score in raw_retrieved:
            cand       = self.candidates[candidate_idx].copy()
            cand_text  = cand.get("text", "")
            cand_year  = cand.get("year")
            cand_jur   = cand.get("jurisdiction", "Unknown")

            S = float(similarity_score)
            C = self._estimate_context_fit(target_tfidf, candidate_idx)
            J = self._compute_jurisdiction_score(
                target_jurisdiction, cand_jur, target_year, cand_year
            )
            I = internal_confidence if internal_confidence is not None else 0.0
            U = self._estimate_uncertainty(S, C)

            trs = self._compute_trs(S, C, J, I, U, return_factors=return_factors)

            alignment     = self._determine_alignment(target_text, cand_text, S)
            target_span, cand_span = self._extract_support_spans(
                target_text, target_tfidf, cand_text, candidate_idx
            )
            justification = self._generate_justification(
                S, C, J, alignment, cand_year, cand_jur
            )

            retrieved_cases.append({
                "case_id":           cand.get("case_id", cand.get("id", f"cand_{candidate_idx}")),
                "title":             cand.get("title", cand_text[:60]),
                "year":              cand_year if cand_year is not None else "N/A",
                "jurisdiction":      cand_jur,
                "similarity_score":  float(np.clip(S, 0, 1)),
                "context_fit":       float(np.clip(C, 0, 1)),
                "jurisdiction_score": float(np.clip(J, 0, 1)),
                "internal_confidence": float(np.clip(I, 0, 1)),
                "uncertainty":       float(np.clip(U, 0, 1)),
                "trs":               float(trs) if not return_factors else trs,
                "alignment_type":    alignment,
                "justification":     justification,
                "spans": {
                    "target_span":    target_span,
                    "candidate_span": cand_span,
                },
            })

        # ── Sort by TRS ───────────────────────────────────────────────────
        retrieved_cases.sort(
            key=lambda x: x["trs"] if isinstance(x["trs"], float) else x["trs"]["score"],
            reverse=True,
        )

        trs_scores = [
            c["trs"] if isinstance(c["trs"], float) else c["trs"]["score"]
            for c in retrieved_cases
        ]
        overall_score = float(np.mean(trs_scores)) if trs_scores else 0.0

        return {
            "target": {
                "case_id":     target_id,
                "title":       target_title,
                "year":        target_year if target_year is not None else "N/A",
                "jurisdiction": target_jurisdiction,
            },
            "retrieved_cases": retrieved_cases,
            "overall_external_coherence_score": float(np.clip(overall_score, 0, 1)),
            "short_summary": self._generate_summary(
                target_title, retrieved_cases, overall_score
            ),
        }

    # ── Internal retrieval ────────────────────────────────────────────────────

    def _retrieve_candidates(
        self, query: str, top_k: int
    ) -> List[Tuple[int, float]]:
        """Encode query and search FAISS index."""
        if self.model is None:
            self.model = SentenceTransformer(self.model_name, device=self.device)

        q_emb = self.model.encode(
            [query], convert_to_numpy=True, normalize_embeddings=False
        )
        q_norm = np.linalg.norm(q_emb, axis=1, keepdims=True)
        q_normed = q_emb / (q_norm + 1e-10)

        distances, indices = self.index.search(
            q_normed.astype("float32"),
            min(top_k, len(self.candidates)),
        )
        return [
            (int(indices[0][i]), float(distances[0][i]))
            for i in range(len(indices[0]))
        ]

    # ── Scoring ───────────────────────────────────────────────────────────────

    def _estimate_context_fit(self, target_tfidf, candidate_idx: int) -> float:
        """Compute context fit using the pre-fitted TF-IDF vectorizer.

        Reuses self._tfidf_matrix (fitted in build_index) — no new
        vectorizer instantiated per call.
        """
        try:
            cand_vector = self._tfidf_matrix[candidate_idx]
            sim = cosine_similarity(target_tfidf, cand_vector)[0][0]
            return float(np.clip(sim, 0, 1))
        except Exception as exc:
            logger.debug("Context fit fallback for candidate %d: %s", candidate_idx, exc)
            # Word-overlap fallback
            target_words = set(
                self._tfidf_vectorizer.inverse_transform(target_tfidf)[0]
            ) if self._tfidf_vectorizer else set()
            cand_text = self.candidates[candidate_idx].get("text", "")
            cand_words = set(cand_text.lower().split())
            if not target_words or not cand_words:
                return 0.0
            return len(target_words & cand_words) / len(target_words | cand_words)

    def _compute_jurisdiction_score(
        self,
        target_jur: str,
        cand_jur: str,
        target_year: Optional[int],
        cand_year: Optional[int],
    ) -> float:
        jur_score = 1.0 if target_jur.lower() == cand_jur.lower() else 0.5
        if target_year is not None and cand_year is not None:
            temporal = float(np.exp(-abs(target_year - cand_year) / 20.0))
            return float(np.clip(0.7 * jur_score + 0.3 * temporal, 0, 1))
        return float(np.clip(jur_score * 0.7, 0, 1))

    def _estimate_uncertainty(self, S: float, C: float) -> float:
        return float(min((S - C) ** 2, 1.0))

    def _compute_trs(
        self,
        S: float, C: float, J: float, I: float, U: float,
        return_factors: bool = False,
    ):
        w = self.trs_weights
        trs = (
            w.get("w_S", 0.5) * S
            + w.get("w_C", 0.2) * C
            + w.get("w_J", 0.1) * J
            + w.get("w_I", 0.15) * I
            - w.get("w_U", 0.05) * U
        )
        trs = float(np.clip(trs, 0, 1))
        if not return_factors:
            return trs
        return {
            "score":   trs,
            "factors": {"similarity": S, "context_fit": C,
                         "jurisdiction_score": J, "internal_confidence": I,
                         "uncertainty": U},
            "weights": self.trs_weights,
        }

    def _determine_alignment(
        self, target_text: str, candidate_text: str, similarity: float
    ) -> str:
        if similarity < 0.4:
            return "neutral"
        contradiction_kw = {
            "however", "overruled", "reversed", "contrary", "distinguished",
            "dissent", "but", "notwithstanding",
        }
        if any(kw in candidate_text.lower() for kw in contradiction_kw):
            return "contradicts"
        return "supports" if similarity >= 0.5 else "neutral"

    def _extract_support_spans(
        self,
        target_text: str,
        target_tfidf,
        candidate_text: str,
        candidate_idx: int,
    ) -> Tuple[str, str]:
        """Extract the best matching sentence pair (≤40 words each).

        Uses the pre-fitted TF-IDF vectorizer — no new instance created.
        """
        t_sents = [s.strip() for s in re.split(r"[.!?]+", target_text) if s.strip()]
        c_sents = [s.strip() for s in re.split(r"[.!?]+", candidate_text) if s.strip()]

        if not t_sents or not c_sents:
            return "N/A", "N/A"

        try:
            all_sents = t_sents + c_sents
            vecs = self._tfidf_vectorizer.transform(all_sents)
            t_vecs = vecs[: len(t_sents)]
            c_vecs = vecs[len(t_sents):]
            sims = cosine_similarity(t_vecs, c_vecs)
            best = np.unravel_index(sims.argmax(), sims.shape)
            t_span = " ".join(t_sents[best[0]].split()[:40])
            c_span = " ".join(c_sents[best[1]].split()[:40])
            return t_span, c_span
        except Exception:
            return (
                " ".join(t_sents[0].split()[:40]),
                " ".join(c_sents[0].split()[:40]),
            )

    def _generate_justification(
        self,
        S: float, C: float, J: float,
        alignment: str,
        year: Optional[int],
        jurisdiction: str,
    ) -> str:
        parts = []
        if S >= 0.7:
            parts.append(f"High semantic similarity ({S:.2f}) indicates strong relevance.")
        elif S >= 0.5:
            parts.append(f"Moderate similarity ({S:.2f}) suggests potential relevance.")
        else:
            parts.append(f"Lower similarity ({S:.2f}) indicates limited semantic overlap.")
        if J >= 0.8:
            parts.append(f"Strong jurisdictional alignment ({jurisdiction}, {year}).")
        elif not year or jurisdiction == "Unknown":
            parts.append("Limited metadata for jurisdictional assessment.")
        parts.append(f"This case {alignment} the target case's reasoning.")
        return " ".join(parts)

    def _generate_summary(
        self,
        target_title: str,
        retrieved_cases: List[Dict[str, Any]],
        overall_score: float,
    ) -> str:
        n = len(retrieved_cases)
        supporting   = sum(1 for c in retrieved_cases if c["alignment_type"] == "supports")
        contradicting = sum(1 for c in retrieved_cases if c["alignment_type"] == "contradicts")
        s = f"Analysis of '{target_title}' retrieved {n} relevant case(s) "
        s += f"with an overall external coherence score of {overall_score:.2f}. "
        if supporting:
            s += f"{supporting} case(s) support the target reasoning. "
        if contradicting:
            s += f"{contradicting} case(s) present contradicting perspectives. "
        if overall_score >= 0.7:
            s += "The external corpus strongly validates the legal reasoning."
        elif overall_score >= 0.5:
            s += "The external corpus provides moderate support."
        else:
            s += "The external corpus shows limited alignment."
        return s

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _compute_similarity(self, query: str, retrieved: list) -> list:
        """Return candidates annotated with similarity scores.
        Used by test suite."""
        results = []
        for idx, score in retrieved:
            result = self.candidates[idx].copy()
            result["similarity_score"] = score
            results.append(result)
        return results

    def get_index_stats(self) -> Dict[str, Any]:
        if self.index is None:
            return {"is_built": False, "num_candidates": 0, "embedding_dimension": None}
        return {
            "is_built":           True,
            "num_candidates":     len(self.candidates),
            "embedding_dimension": self.index.d,
            "model_name":         self.model_name,
            "tfidf_vocab_size":   len(self._tfidf_vectorizer.vocabulary_)
                                  if self._tfidf_vectorizer else 0,
        }

    def clear_index(self) -> None:
        self.index                = None
        self.candidates           = []
        self.candidate_embeddings = None
        self._tfidf_vectorizer    = None
        self._tfidf_matrix        = None
