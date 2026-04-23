"""BioBERT External Inference Agent.

Mirrors InLegalBERTExternalAgent exactly — same interface, same method
signatures, same return shapes — so the Flask inference route can call
either model interchangeably using a single code path.

BioBERT (dmis-lab/biobert-base-cased-v1.2) is a BERT model pre-trained
on PubMed abstracts and PubMed Central full-text articles. It captures
biomedical and clinical terminology that InLegalBERT misses.

In CiteAI this is useful for:
  - Medical evidence in legal judgments (drug approvals, clinical trials)
  - Health policy and pharmaceutical regulation cases
  - Cases citing WHO/ICMR guidelines or medical research

Integration status:
  This agent is wired into ModelRegistry (extensions.py) and the inference
  route (routes/inference.py). Set BIOBERT_ENABLED=1 in backend/.env to
  activate. The team's updated FAISS layer will replace _build_faiss_index()
  with a persistent index once that work is complete.
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np

from .base_agent import BaseExternalAgent

logger = logging.getLogger(__name__)


class BioBERTExternalAgent(BaseExternalAgent):
    """Hybrid retrieval agent using BioBERT embeddings + citation graph.

    Identical interface to InLegalBERTExternalAgent.
    """

    MODEL_DOMAIN = "bio"

    def __init__(
        self,
        model_name: str = "dmis-lab/biobert-base-cased-v1.2",
        device: str | None = None,
        max_length: int = 512,
        use_citation_weight: float = 0.3,   # lower default — bio citations less structured
        use_semantic_weight: float = 0.7,
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

        # FAISS index — built by _build_faiss_index() or loaded from disk
        # TODO: Once team's updated FAISS layer is ready, replace with
        #       persistent index loaded from FAISS_INDEX_DIR config key.
        self._faiss_index = None
        self._faiss_ids: list[str] = []  # maps FAISS index position → case_id

    # ── Model loading ─────────────────────────────────────────────────────────

    def _load_model(self, tokenizer=None, model=None) -> None:
        """Load BioBERT, or reuse pre-loaded objects from ModelRegistry."""
        if tokenizer is not None and model is not None:
            self.tokenizer = tokenizer
            self.model = model
            logger.info("BioBERTExternalAgent: using pre-loaded model from registry")
            return

        from transformers import AutoTokenizer, AutoModel
        logger.info("Loading BioBERT: %s on %s", self.model_name, self.device)
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model = AutoModel.from_pretrained(self.model_name)
        self.model.to(self.device)
        self.model.eval()

    # ── FAISS index ───────────────────────────────────────────────────────────

    def _build_faiss_index(self) -> None:
        """Build an in-memory FAISS index from computed embeddings.

        TODO: Replace this with a persistent index load/save using
        FAISS_INDEX_DIR once the team's updated FAISS layer is integrated.
        """
        try:
            import faiss
        except ImportError:
            logger.warning("faiss not installed — falling back to brute-force search")
            return

        if not self.case_embeddings:
            raise ValueError("No embeddings computed. Call compute_all_embeddings() first.")

        ids   = list(self.case_embeddings.keys())
        vecs  = np.stack([self.case_embeddings[i] for i in ids]).astype("float32")
        dim   = vecs.shape[1]

        index = faiss.IndexFlatIP(dim)
        index.add(vecs)

        self._faiss_index = index
        self._faiss_ids   = ids
        logger.info("BioBERT FAISS index built — %d vectors, dim=%d", len(ids), dim)

    def compute_all_embeddings(self, batch_size: int = 8) -> None:
        """Compute embeddings and build FAISS index."""
        super().compute_all_embeddings(batch_size=batch_size)
        self._build_faiss_index()

    # ── Retrieval ─────────────────────────────────────────────────────────────

    def retrieve_similar_cases(
        self,
        query_text: str | None = None,
        query_case_id: str | None = None,
        top_k: int = 10,
        use_citations: bool = False,   # bio domain has fewer citation links
        use_semantic: bool = True,
    ) -> list[dict[str, Any]]:
        """Retrieve similar cases using BioBERT semantic embeddings."""
        if not self.embeddings_computed:
            raise ValueError("Call compute_all_embeddings() first.")

        # Resolve query embedding
        if query_case_id and query_case_id in self.case_embeddings:
            query_emb = self.case_embeddings[query_case_id]
        elif query_text:
            query_emb = self.encode_text(query_text)
        else:
            raise ValueError("Provide query_text or a valid query_case_id.")

        # FAISS search
        sem_scores: dict[str, float] = {}
        if self._faiss_index is not None:
            try:
                import faiss
                q = query_emb.reshape(1, -1).astype("float32")
                k = min(top_k + 1, len(self._faiss_ids))
                distances, indices = self._faiss_index.search(q, k)
                for dist, idx in zip(distances[0], indices[0]):
                    cid = self._faiss_ids[idx]
                    if cid != query_case_id:
                        sem_scores[cid] = float(dist)
            except Exception as exc:
                logger.warning("FAISS search failed, falling back to brute-force: %s", exc)
                sem_scores = self._brute_force_scores(query_emb, query_case_id)
        else:
            sem_scores = self._brute_force_scores(query_emb, query_case_id)

        # Citation scores (optional)
        cite_scores: dict[str, float] = {}
        if use_citations and query_case_id and self.citation_graph and \
                self.citation_graph.number_of_edges() > 0:
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
                "case_id":          cid,
                "case_name":        case.get("case_name", cid),
                "year":             case.get("year"),
                "similarity_score": round(hybrid, 4),
                "semantic_score":   round(s, 4),
                "citation_score":   round(c, 4),
                "source_model":     "biobert",
            })

        results.sort(key=lambda x: x["similarity_score"], reverse=True)
        return results[:top_k]

    def _brute_force_scores(
        self, query_emb: np.ndarray, exclude_id: str | None
    ) -> dict[str, float]:
        scores = {}
        for cid, emb in self.case_embeddings.items():
            if cid == exclude_id:
                continue
            scores[cid] = float(np.dot(query_emb, emb))
        return scores

    def _get_citation_neighbors(self, case_id: str) -> dict[str, float]:
        scores: dict[str, float] = {}
        if self.citation_graph is None:
            return scores
        for _, tgt in self.citation_graph.out_edges(case_id):
            scores[tgt] = scores.get(tgt, 0.0) + 1.0
        for src, _ in self.citation_graph.in_edges(case_id):
            scores[src] = scores.get(src, 0.0) + 0.5
        if scores:
            max_s = max(scores.values())
            if max_s > 0:
                scores = {k: v / max_s for k, v in scores.items()}
        return scores

    # ── Output ────────────────────────────────────────────────────────────────

    def generate_reasoning_output(
        self,
        query_case_id: str,
        retrieved_cases: list[dict[str, Any]],
    ) -> dict[str, Any]:
        query = self.cases.get(query_case_id, {})
        return {
            "query_case":      query_case_id,
            "query_case_name": query.get("case_name", query_case_id),
            "query_year":      query.get("year"),
            "source_model":    "biobert",
            "model_name":      self.model_name,
            "top_references":  retrieved_cases,
            "overall_legal_context_summary": (
                f"BioBERT retrieved {len(retrieved_cases)} biomedically relevant "
                f"precedent(s) for '{query.get('case_name', query_case_id)}'."
            ),
            "retrieval_metadata": {
                "total_retrieved":  len(retrieved_cases),
                "citation_weight":  self.citation_weight,
                "semantic_weight":  self.semantic_weight,
            },
        }
