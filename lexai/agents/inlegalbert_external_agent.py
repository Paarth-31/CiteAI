"""InLegalBERT-based External Inference Agent.

Uses law-ai/InLegalBERT for legal document embeddings with hybrid
retrieval (semantic + citation graph).

Changes from previous version:
  - Inherits from BaseExternalAgent (shared interface with BioBERT agent)
  - Accepts pre-loaded tokenizer/model from ModelRegistry via _load_model()
  - load_dataset_from_dicts() inherited from base — Flask route uses this
  - compute_all_embeddings() inherited from base
  - encode_text() / encode_batch() inherited from base
  - Hardcoded LecAI demo paths removed from this file
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np
import networkx as nx

from .base_agent import BaseExternalAgent

logger = logging.getLogger(__name__)


class InLegalBERTExternalAgent(BaseExternalAgent):
    """Hybrid retrieval agent using InLegalBERT embeddings + citation graph."""

    MODEL_DOMAIN = "legal"

    def __init__(
        self,
        model_name: str = "law-ai/InLegalBERT",
        device: str | None = None,
        max_length: int = 512,
        use_citation_weight: float = 0.4,
        use_semantic_weight: float = 0.6,
        # Pre-loaded model objects from ModelRegistry (optional)
        tokenizer=None,
        model=None,
    ) -> None:
        super().__init__(
            model_name=model_name,
            device=device,
            max_length=max_length,
            use_citation_weight=use_citation_weight,
            use_semantic_weight=use_semantic_weight,
        )
        self._load_model(tokenizer=tokenizer, model=model)

    # ── Model loading ─────────────────────────────────────────────────────────

    def _load_model(self, tokenizer=None, model=None) -> None:
        """Load InLegalBERT, or reuse pre-loaded objects from ModelRegistry."""
        if tokenizer is not None and model is not None:
            self.tokenizer = tokenizer
            self.model = model
            logger.info("InLegalBERTExternalAgent: using pre-loaded model from registry")
            return

        from transformers import AutoTokenizer, AutoModel
        logger.info("Loading InLegalBERT: %s on %s", self.model_name, self.device)
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model = AutoModel.from_pretrained(self.model_name)
        self.model.to(self.device)
        self.model.eval()

    # ── Dataset loading (CSV path — for standalone / CLI use) ─────────────────

    def load_dataset(
        self,
        case_mapping_path: str,
        case_text_dir: str | None = None,
        edge_list_path: str | None = None,
        max_cases: int | None = None,
    ) -> int:
        """Load from a LecAI-format CSV file.

        For Flask usage, prefer load_dataset_from_dicts() (inherited from base)
        which avoids file I/O.
        """
        import pandas as pd

        df = pd.read_csv(case_mapping_path)
        if max_cases:
            df = df.head(max_cases)

        self.cases = {}
        for _, row in df.iterrows():
            case_id   = str(row.get("Case_id", row.get("case_id", ""))).strip()
            case_name = str(row.get("Case_name", row.get("case_name", case_id))).strip()
            if not case_id:
                continue

            text = case_name  # fallback text is the name
            if case_text_dir:
                import os
                txt_path = os.path.join(case_text_dir, f"{case_id}.txt")
                if os.path.exists(txt_path):
                    with open(txt_path, encoding="utf-8") as f:
                        text = f.read()

            self.cases[case_id] = {
                "case_id":   case_id,
                "case_name": case_name,
                "text":      text,
                "year":      self._extract_year_from_id(case_id),
            }

        if edge_list_path:
            self._load_edge_list(edge_list_path)

        self._build_index_maps()
        self.dataset_loaded = True
        logger.info("InLegalBERT dataset loaded: %d cases", len(self.cases))
        return len(self.cases)

    def _extract_year_from_id(self, case_id: str) -> int | None:
        import re
        match = re.search(r"(19|20)\d{2}", case_id)
        return int(match.group(0)) if match else None

    def _load_edge_list(self, path: str) -> None:
        import csv
        with open(path, encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 2:
                    src, tgt = row[0].strip(), row[1].strip()
                    if src in self.cases and tgt in self.cases:
                        self.citation_graph.add_edge(src, tgt)
        logger.info("Citation graph: %d edges loaded", self.citation_graph.number_of_edges())

    # ── Retrieval ─────────────────────────────────────────────────────────────

    def retrieve_similar_cases(
        self,
        query_text: str | None = None,
        query_case_id: str | None = None,
        top_k: int = 10,
        use_citations: bool = True,
        use_semantic: bool = True,
    ) -> list[dict[str, Any]]:
        """Hybrid retrieval: semantic similarity + citation graph score."""
        if not self.embeddings_computed:
            raise ValueError("Call compute_all_embeddings() first.")

        # Resolve query embedding
        if query_case_id and query_case_id in self.case_embeddings:
            query_emb = self.case_embeddings[query_case_id]
        elif query_text:
            query_emb = self.encode_text(query_text)
        else:
            raise ValueError("Provide query_text or a valid query_case_id.")

        # Semantic scores
        sem_scores: dict[str, float] = {}
        if use_semantic:
            for cid, emb in self.case_embeddings.items():
                if cid == query_case_id:
                    continue
                sem_scores[cid] = float(np.dot(query_emb, emb))

        # Citation graph scores
        cite_scores: dict[str, float] = {}
        if use_citations and query_case_id and self.citation_graph.number_of_edges() > 0:
            cite_scores = self._get_citation_neighbors(query_case_id)

        # Hybrid score
        all_ids = set(sem_scores) | set(cite_scores)
        results = []
        for cid in all_ids:
            s = sem_scores.get(cid, 0.0)
            c = cite_scores.get(cid, 0.0)
            hybrid = self.semantic_weight * s + self.citation_weight * c
            case = self.cases.get(cid, {})
            results.append({
                "case_id":         cid,
                "case_name":       case.get("case_name", cid),
                "year":            case.get("year"),
                "similarity_score": round(hybrid, 4),
                "semantic_score":  round(s, 4),
                "citation_score":  round(c, 4),
                "source_model":    "legalbert",
            })

        results.sort(key=lambda x: x["similarity_score"], reverse=True)
        return results[:top_k]

    def _get_citation_neighbors(self, case_id: str) -> dict[str, float]:
        """Return citation-based scores for all neighbors."""
        scores: dict[str, float] = {}
        if self.citation_graph is None:
            return scores
        # Direct citations (out-edges): strong signal
        for _, tgt in self.citation_graph.out_edges(case_id):
            scores[tgt] = scores.get(tgt, 0.0) + 1.0
        # Cited by (in-edges): weaker signal
        for src, _ in self.citation_graph.in_edges(case_id):
            scores[src] = scores.get(src, 0.0) + 0.5
        # Normalise to [0, 1]
        if scores:
            max_score = max(scores.values())
            if max_score > 0:
                scores = {k: v / max_score for k, v in scores.items()}
        return scores

    # ── Output ────────────────────────────────────────────────────────────────

    def generate_reasoning_output(
        self,
        query_case_id: str,
        retrieved_cases: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Generate structured reasoning output."""
        query = self.cases.get(query_case_id, {})
        return {
            "query_case":      query_case_id,
            "query_case_name": query.get("case_name", query_case_id),
            "query_year":      query.get("year"),
            "source_model":    "legalbert",
            "model_name":      self.model_name,
            "top_references":  retrieved_cases,
            "overall_legal_context_summary": (
                f"InLegalBERT retrieved {len(retrieved_cases)} precedent(s) "
                f"for '{query.get('case_name', query_case_id)}'."
            ),
            "retrieval_metadata": {
                "total_retrieved":  len(retrieved_cases),
                "citation_weight":  self.citation_weight,
                "semantic_weight":  self.semantic_weight,
            },
        }
