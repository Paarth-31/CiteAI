"""Base class for domain-specific BERT inference agents.

Both InLegalBERTExternalAgent and BioBERTExternalAgent inherit from this
class. It defines the shared interface so the Flask inference route can
call either interchangeably — same method names, same return shapes.

When the team adds more domain models (e.g. a finance BERT), they inherit
from this class and the rest of the system works without changes.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

import numpy as np
import torch

logger = logging.getLogger(__name__)


class BaseExternalAgent(ABC):
    """Abstract base for domain BERT inference agents.

    Subclasses must implement:
        encode_text()
        retrieve_similar_cases()
        generate_reasoning_output()

    Everything else (device resolution, mean pooling, batch encoding,
    citation graph management) is provided here.
    """

    MODEL_DOMAIN: str = "base"  # override in subclass: "legal" | "bio"

    def __init__(
        self,
        model_name: str,
        device: str | None = None,
        max_length: int = 512,
        use_citation_weight: float = 0.4,
        use_semantic_weight: float = 0.6,
    ) -> None:
        self.model_name = model_name
        self.max_length = max_length
        self.citation_weight = use_citation_weight
        self.semantic_weight = use_semantic_weight
        self.device = self._resolve_device(device)

        # Populated by subclass __init__ after calling super().__init__()
        self.tokenizer = None
        self.model = None

        # Populated by load_dataset() / load_dataset_from_dicts()
        self.cases: dict[str, dict[str, Any]] = {}
        self.case_embeddings: dict[str, np.ndarray] = {}
        self.dataset_loaded = False
        self.embeddings_computed = False

        # Citation graph — populated if edge data is available
        try:
            import networkx as nx
            self.citation_graph = nx.DiGraph()
        except ImportError:
            self.citation_graph = None

        self.case_id_to_idx: dict[str, int] = {}
        self.idx_to_case_id: dict[int, str] = {}

    # ── Interface (subclasses implement) ─────────────────────────────────────

    @abstractmethod
    def retrieve_similar_cases(
        self,
        query_text: str | None = None,
        query_case_id: str | None = None,
        top_k: int = 10,
        use_citations: bool = True,
        use_semantic: bool = True,
    ) -> list[dict[str, Any]]:
        """Return top-k similar cases ranked by hybrid score."""
        ...

    @abstractmethod
    def generate_reasoning_output(
        self,
        query_case_id: str,
        retrieved_cases: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Return structured reasoning output for the query case."""
        ...

    # ── Shared helpers ────────────────────────────────────────────────────────

    def _resolve_device(self, device: str | None) -> str:
        if device and device != "auto":
            return device
        try:
            return "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            return "cpu"

    def _mean_pool(self, token_embeddings: torch.Tensor, attention_mask: torch.Tensor) -> np.ndarray:
        """Mean-pool token embeddings weighted by attention mask."""
        mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        summed = torch.sum(token_embeddings * mask_expanded, dim=1)
        counts = mask_expanded.sum(dim=1).clamp(min=1e-9)
        pooled = (summed / counts).detach().cpu().numpy()
        # L2 normalise
        norms = np.linalg.norm(pooled, axis=1, keepdims=True)
        return pooled / (norms + 1e-10)

    def encode_text(self, text: str) -> np.ndarray:
        """Encode a single text string to a normalised embedding vector."""
        if self.tokenizer is None or self.model is None:
            raise RuntimeError("Model not loaded. Call _load_model() in subclass __init__.")
        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=self.max_length,
            padding=True,
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        with torch.no_grad():
            outputs = self.model(**inputs)
        return self._mean_pool(outputs.last_hidden_state, inputs["attention_mask"])[0]

    def encode_batch(self, texts: list[str], batch_size: int = 8) -> np.ndarray:
        """Encode a list of texts in batches. Returns (N, dim) array."""
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i: i + batch_size]
            inputs = self.tokenizer(
                batch,
                return_tensors="pt",
                truncation=True,
                max_length=self.max_length,
                padding=True,
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            with torch.no_grad():
                outputs = self.model(**inputs)
            batch_emb = self._mean_pool(outputs.last_hidden_state, inputs["attention_mask"])
            all_embeddings.append(batch_emb)
        return np.vstack(all_embeddings)

    def load_dataset_from_dicts(
        self,
        documents: list[dict[str, Any]],
        text_field: str = "text",
        id_field: str = "doc_id",
    ) -> int:
        """Load a list of dicts directly (no CSV required).

        This is the method called by the Flask inference route so it doesn't
        need a file path — it passes documents it already has in memory.
        """
        self.cases = {}
        for i, doc in enumerate(documents):
            doc_id = str(doc.get(id_field, doc.get("case_id", doc.get("id", f"doc_{i}"))))
            self.cases[doc_id] = {
                "case_id":   doc_id,
                "case_name": doc.get("title", doc.get("case_name", doc_id)),
                "text":      doc.get(text_field, doc.get("text", "")),
                "year":      doc.get("year"),
            }
        self._build_index_maps()
        self.dataset_loaded = True
        logger.info("%s: loaded %d cases from dicts", self.__class__.__name__, len(self.cases))
        return len(self.cases)

    def compute_all_embeddings(self, batch_size: int = 8) -> None:
        """Compute and cache embeddings for all loaded cases."""
        if not self.cases:
            raise ValueError("No cases loaded. Call load_dataset_from_dicts() first.")
        texts = [c["text"] for c in self.cases.values()]
        ids   = list(self.cases.keys())
        embeddings = self.encode_batch(texts, batch_size=batch_size)
        for case_id, emb in zip(ids, embeddings):
            self.case_embeddings[case_id] = emb
        self.embeddings_computed = True
        logger.info("%s: computed embeddings for %d cases", self.__class__.__name__, len(ids))

    def get_statistics(self) -> dict[str, Any]:
        return {
            "model_domain":       self.MODEL_DOMAIN,
            "model_name":         self.model_name,
            "device":             self.device,
            "cases_loaded":       len(self.cases),
            "embeddings_computed": self.embeddings_computed,
            "citation_edges":     (
                self.citation_graph.number_of_edges()
                if self.citation_graph else 0
            ),
        }

    def _build_index_maps(self) -> None:
        self.case_id_to_idx = {cid: i for i, cid in enumerate(self.cases)}
        self.idx_to_case_id = {i: cid for cid, i in self.case_id_to_idx.items()}
