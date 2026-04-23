"""Legal Citation Graph Builder with BERT node embeddings.

Builds a NetworkX citation graph and optionally enriches each node with
BERT embeddings (InLegalBERT, BioBERT, or sentence-transformer).

Changes from previous version:
  - Accepts any BaseExternalAgent (InLegalBERT or BioBERT) via embed_agent.
  - Accepts a pre-loaded SentenceTransformer from ModelRegistry.
  - Hardcoded demo path (/home/anand/...) removed.
  - Demo function replaced with a path-agnostic example.
  - get_graph_as_dict() helper for Flask route to consume.
"""
from __future__ import annotations

import json
import logging
import os
from collections import defaultdict
from typing import Any, Optional

import numpy as np
import networkx as nx

logger = logging.getLogger(__name__)


class GraphBuilder:
    """Build and enrich legal citation graphs.

    Typical flow:
        builder = GraphBuilder(embed_agent=model_registry.get_legalbert_agent())
        builder.load_documents(docs)
        builder.compute_embeddings()
        builder.build_faiss_index()
        builder.build_citation_graph()
        graph_dict = builder.get_graph_as_dict()
    """

    def __init__(
        self,
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
        classifier_model: str = "cross-encoder/nli-deberta-v3-small",
        device: Optional[str] = None,
        top_k: int = 5,
        # Pass a pre-loaded agent from ModelRegistry to avoid reloading models.
        # If provided, embedding_model and classifier_model args are ignored.
        embed_agent=None,   # BaseExternalAgent subclass
        sentence_model=None,  # SentenceTransformer
    ) -> None:
        # Auto-detect device
        try:
            import torch
            self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        except ImportError:
            self.device = "cpu"

        self.top_k = top_k
        self.documents: list[dict[str, Any]] = []
        self.embeddings: Optional[np.ndarray] = None
        self.faiss_index = None
        self.graph = nx.DiGraph()

        # Embedding source — priority: embed_agent > sentence_model > load fresh
        self._embed_agent = embed_agent
        self._sentence_model = sentence_model
        self._embedding_model_name = embedding_model
        self._classifier_model_name = classifier_model
        self._classifier = None
        self._embedding_dim: Optional[int] = None

        if embed_agent is not None:
            logger.info("GraphBuilder: using pre-loaded domain agent (%s)", type(embed_agent).__name__)
        elif sentence_model is not None:
            logger.info("GraphBuilder: using pre-loaded sentence-transformer")
        else:
            logger.info("GraphBuilder: will load %s on first use", embedding_model)

    # ── Document loading ──────────────────────────────────────────────────────

    def load_documents(
        self,
        documents: list[dict[str, Any]],
        text_field: str = "text",
        id_field: str = "doc_id",
    ) -> int:
        self.documents = []
        for i, doc in enumerate(documents):
            if text_field not in doc:
                logger.warning("Document %d missing '%s' field — skipped", i, text_field)
                continue
            if id_field not in doc:
                doc = {**doc, id_field: f"DOC_{i:04d}"}
            self.documents.append(doc)
        logger.info("Loaded %d documents", len(self.documents))
        return len(self.documents)

    # ── Embedding ─────────────────────────────────────────────────────────────

    def compute_embeddings(
        self,
        text_field: str = "text",
        batch_size: int = 16,
    ) -> None:
        if not self.documents:
            raise ValueError("No documents loaded.")

        texts = [doc[text_field] for doc in self.documents]

        if self._embed_agent is not None:
            # Use domain agent (InLegalBERT or BioBERT) — encode_batch inherited from base
            logger.info("Computing embeddings via %s", type(self._embed_agent).__name__)
            self.embeddings = self._embed_agent.encode_batch(texts, batch_size=batch_size)

        elif self._sentence_model is not None:
            logger.info("Computing embeddings via pre-loaded sentence-transformer")
            self.embeddings = self._sentence_model.encode(
                texts, batch_size=batch_size, convert_to_numpy=True, show_progress_bar=True
            )
            norms = np.linalg.norm(self.embeddings, axis=1, keepdims=True)
            self.embeddings = self.embeddings / (norms + 1e-10)

        else:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading sentence-transformer: %s", self._embedding_model_name)
            model = SentenceTransformer(self._embedding_model_name)
            self.embeddings = model.encode(
                texts, batch_size=batch_size, convert_to_numpy=True, show_progress_bar=True
            )
            norms = np.linalg.norm(self.embeddings, axis=1, keepdims=True)
            self.embeddings = self.embeddings / (norms + 1e-10)

        self._embedding_dim = self.embeddings.shape[1]
        logger.info("Embeddings: shape=%s", self.embeddings.shape)

    # ── FAISS index ───────────────────────────────────────────────────────────

    def build_faiss_index(self, use_gpu: bool = False) -> None:
        if self.embeddings is None:
            raise ValueError("Call compute_embeddings() first.")
        import faiss
        index = faiss.IndexFlatIP(self._embedding_dim)
        if use_gpu:
            try:
                res = faiss.StandardGpuResources()
                index = faiss.index_cpu_to_gpu(res, 0, index)
            except Exception:
                logger.warning("GPU FAISS unavailable — using CPU")
        index.add(self.embeddings.astype("float32"))
        self.faiss_index = index
        logger.info("FAISS index built: %d vectors", index.ntotal)

    def find_nearest_neighbors(
        self, doc_idx: int, k: Optional[int] = None
    ) -> tuple[np.ndarray, np.ndarray]:
        if self.faiss_index is None:
            raise ValueError("Call build_faiss_index() first.")
        k = k or self.top_k
        query = self.embeddings[doc_idx: doc_idx + 1].astype("float32")
        query = query / (np.linalg.norm(query) + 1e-10)
        distances, indices = self.faiss_index.search(query, k + 1)
        mask = indices[0] != doc_idx
        return distances[0][mask][:k], indices[0][mask][:k]

    # ── Citation graph ────────────────────────────────────────────────────────

    def _load_classifier(self) -> None:
        if self._classifier is not None:
            return
        from transformers import pipeline
        logger.info("Loading NLI classifier: %s", self._classifier_model_name)
        self._classifier = pipeline(
            "text-classification",
            model=self._classifier_model_name,
            device=0 if self.device == "cuda" else -1,
        )

    def classify_citation_type(
        self, source_text: str, target_text: str, max_length: int = 256
    ) -> str:
        self._load_classifier()
        pair = f"{source_text[:max_length]} [SEP] {target_text[:max_length]}"
        try:
            result = self._classifier(pair, truncation=True, max_length=512)
            label  = result[0]["label"].lower()
            score  = result[0]["score"]
            if "entail" in label:
                return "supports" if score > 0.6 else "refers"
            if "contra" in label:
                return "contradicts" if score > 0.6 else "neutral"
            return "neutral"
        except Exception as exc:
            logger.debug("Classifier failed: %s", exc)
            return "neutral"

    def build_citation_graph(
        self,
        text_field: str = "text",
        id_field: str = "doc_id",
        similarity_threshold: float = 0.3,
        max_edges_per_node: Optional[int] = None,
    ) -> None:
        if self.faiss_index is None:
            raise ValueError("Call build_faiss_index() first.")

        max_edges = max_edges_per_node or self.top_k
        self.graph = nx.DiGraph()

        for doc in self.documents:
            doc_id = doc[id_field]
            # Store embedding on node for downstream consumers
            idx = self.documents.index(doc)
            self.graph.add_node(
                doc_id,
                text=doc.get(text_field, "")[:200],
                embedding=self.embeddings[idx].tolist() if self.embeddings is not None else None,
                **{k: v for k, v in doc.items() if k != text_field},
            )

        edges_added = 0
        for idx, doc in enumerate(self.documents):
            source_id   = doc[id_field]
            source_text = doc[text_field]
            distances, neighbor_indices = self.find_nearest_neighbors(idx, k=max_edges)

            for dist, nb_idx in zip(distances, neighbor_indices):
                if float(dist) < similarity_threshold:
                    continue
                nb_doc    = self.documents[nb_idx]
                target_id = nb_doc[id_field]
                ctype     = self.classify_citation_type(source_text, nb_doc[text_field])
                self.graph.add_edge(
                    source_id, target_id,
                    citation_type=ctype,
                    similarity=float(dist),
                    weight=float(dist),
                )
                edges_added += 1

        logger.info(
            "Citation graph: %d nodes, %d edges",
            self.graph.number_of_nodes(), self.graph.number_of_edges(),
        )

    # ── Output ────────────────────────────────────────────────────────────────

    def get_graph_as_dict(self) -> dict[str, Any]:
        """Return graph as {nodes, edges} dict — consumed by Flask route."""
        nodes = [
            {
                "id":    node,
                "title": self.graph.nodes[node].get("case_name", node),
                "year":  self.graph.nodes[node].get("year"),
                "text":  self.graph.nodes[node].get("text", "")[:200],
                # embedding omitted for JSON response — too large
            }
            for node in self.graph.nodes()
        ]
        edges = [
            {
                "source":        u,
                "target":        v,
                "citation_type": self.graph.edges[u, v].get("citation_type", "neutral"),
                "similarity":    self.graph.edges[u, v].get("similarity", 0.0),
            }
            for u, v in self.graph.edges()
        ]
        return {"nodes": nodes, "edges": edges}

    def save_graph(self, output_path: str, fmt: str = "json") -> None:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        if fmt == "json":
            with open(output_path, "w") as f:
                json.dump(self.get_graph_as_dict(), f, indent=2)
        elif fmt == "gexf":
            nx.write_gexf(self.graph, output_path)
        elif fmt == "graphml":
            nx.write_graphml(self.graph, output_path)
        logger.info("Graph saved: %s", output_path)

    def get_statistics(self) -> dict[str, Any]:
        if self.graph.number_of_nodes() == 0:
            return {"error": "Graph is empty"}
        citation_types: dict[str, int] = defaultdict(int)
        for _, _, data in self.graph.edges(data=True):
            citation_types[data.get("citation_type", "unknown")] += 1
        in_degrees  = [self.graph.in_degree(n) for n in self.graph.nodes()]
        out_degrees = [self.graph.out_degree(n) for n in self.graph.nodes()]
        return {
            "num_nodes":      self.graph.number_of_nodes(),
            "num_edges":      self.graph.number_of_edges(),
            "density":        float(nx.density(self.graph)),
            "citation_types": dict(citation_types),
            "embedding_model": (
                type(self._embed_agent).__name__
                if self._embed_agent else self._embedding_model_name
            ),
            "degree_stats": {
                "in_degree":  {"mean": float(np.mean(in_degrees)),  "max": int(np.max(in_degrees))},
                "out_degree": {"mean": float(np.mean(out_degrees)), "max": int(np.max(out_degrees))},
            },
        }

    def visualize_degree_distribution(
        self, output_path: Optional[str] = None, title: str = "Citation Graph Degree Distribution"
    ) -> None:
        import matplotlib.pyplot as plt
        if self.graph.number_of_nodes() == 0:
            logger.warning("Graph is empty — nothing to visualise")
            return
        in_d  = [self.graph.in_degree(n) for n in self.graph.nodes()]
        out_d = [self.graph.out_degree(n) for n in self.graph.nodes()]
        total = [a + b for a, b in zip(in_d, out_d)]
        fig, axes = plt.subplots(1, 3, figsize=(15, 4))
        for ax, data, label, color in zip(
            axes,
            [in_d, out_d, total],
            ["In-Degree", "Out-Degree", "Total Degree"],
            ["blue", "green", "purple"],
        ):
            ax.hist(data, bins=20, edgecolor="black", alpha=0.7, color=color)
            ax.set_xlabel(label)
            ax.set_ylabel("Frequency")
            ax.set_title(f"{label} Distribution")
            ax.grid(alpha=0.3)
        plt.suptitle(title, fontsize=14, fontweight="bold")
        plt.tight_layout()
        if output_path:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            plt.savefig(output_path, dpi=300, bbox_inches="tight")
            logger.info("Degree distribution saved: %s", output_path)
        else:
            plt.show()
        plt.close()
