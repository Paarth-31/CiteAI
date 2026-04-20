"""
BioBERT-based External Inference Agent for Biomedical AI.

This module implements an ExternalInferenceAgent specifically designed for biomedical
literature and clinical datasets using BioBERT embeddings and citation/co-occurrence
graph reasoning. It combines:
1. Citation / co-occurrence graph analysis (NetworkX)
2. Semantic similarity (BioBERT embeddings)
3. Hybrid retrieval (graph + semantic)
4. Biomedical reasoning generation

Compatible with PubMed-style dataset formats (PMID-based).
"""

import os
import json
import gzip
import csv
from typing import List, Dict, Any, Optional, Tuple, Set
import numpy as np
import pandas as pd
import networkx as nx
from collections import defaultdict

try:
    from transformers import AutoTokenizer, AutoModel
    import torch
    import torch.nn.functional as F
except ImportError:
    print("Warning: transformers or torch not installed. Install with: pip install transformers torch")
    raise


class BioBERTExternalAgent:
    """
    External Inference Agent using BioBERT and citation/co-occurrence graph reasoning.

    This agent performs hybrid retrieval combining:
    - Citation / co-occurrence graph traversal (cited/citing articles)
    - Semantic similarity using BioBERT embeddings
    - Citeomatic-style scoring for article ranking

    Designed for biomedical literature retrieval tasks such as:
    - Finding similar PubMed articles
    - Drug-disease relationship discovery
    - Clinical trial relevance ranking
    """

    def __init__(
        self,
        model_name: str = "dmis-lab/biobert-v1.1",
        device: Optional[str] = None,
        max_length: int = 512,
        use_citation_weight: float = 0.4,
        use_semantic_weight: float = 0.6, #NEED TO FINETUNE
    ):
        """
        Initialize the BioBERT External Agent.

        Args:
            model_name: HuggingFace model name (default: BioBERT v1.1)
            device: Device to run on ("cuda", "cpu", or None for auto-detect)
            max_length: Maximum token length for BERT encoding
            use_citation_weight: Weight for citation-based similarity [0, 1]
            use_semantic_weight: Weight for semantic similarity [0, 1]
        """
        self.model_name = model_name
        self.max_length = max_length
        self.citation_weight = use_citation_weight
        self.semantic_weight = use_semantic_weight

        # Auto-detect device
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        print(f"Initializing BioBERT External Agent on device: {self.device}")

        # Load BioBERT model and tokenizer
        print(f"Loading model: {model_name}")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name)
        self.model.to(self.device)
        self.model.eval()

        # Data storage
        self.articles = {}           # article_id -> article_data dict
        self.article_embeddings = {} # article_id -> embedding vector
        self.citation_graph = nx.DiGraph()  # Directed graph: source -> target (cites)
        self.article_id_to_idx = {}  # article_id -> node index
        self.idx_to_article_id = {}  # node index -> article_id

        # Metadata
        self.dataset_loaded = False
        self.embeddings_computed = False

        print("BioBERT External Agent initialized successfully")

    # ------------------------------------------------------------------
    # Dataset loading
    # ------------------------------------------------------------------

    def load_dataset(
        self,
        article_mapping_path: str,
        abstract_dir: Optional[str] = None,
        edge_list_path: Optional[str] = None,
        node_features_path: Optional[str] = None,
        max_articles: Optional[int] = None,
    ) -> int:
        """
        Load biomedical article dataset with metadata and optional citation graph.

        Expected CSV columns: pmid, title, journal  (additional columns tolerated)

        Args:
            article_mapping_path: Path to CSV mapping file (pmid, title, journal, ...)
            abstract_dir: Optional directory containing plain-text abstract files
                          named <pmid>.txt
            edge_list_path: Optional path to edge list file (source_pmid, target_pmid)
            node_features_path: Optional path to pre-computed node features / embeddings
            max_articles: Optional limit on number of articles to load

        Returns:
            Number of articles loaded
        """
        print(f"\nLoading biomedical dataset from: {article_mapping_path}")

        df = pd.read_csv(article_mapping_path)
        if max_articles:
            df = df.head(max_articles)

        print(f"Found {len(df)} articles in mapping file")

        for idx, row in df.iterrows():
            article_id = str(row["pmid"]).strip()
            title = str(row.get("title", "")).strip()
            journal = str(row.get("journal", "")).strip()
            pub_year = self._parse_year(row.get("year") or row.get("pub_date", ""))

            self.articles[article_id] = {
                "article_id": article_id,
                "title": title,
                "journal": journal,
                "year": pub_year,
                "text": None,   # Loaded below if abstract_dir provided
                "mesh_terms": row.get("mesh_terms", ""),
                "node_idx": idx,
            }

            self.article_id_to_idx[article_id] = idx
            self.idx_to_article_id[idx] = article_id

        print(f"Loaded {len(self.articles)} articles")

        # Load abstracts if directory provided
        if abstract_dir and os.path.exists(abstract_dir):
            print(f"Loading abstracts from: {abstract_dir}")
            loaded_texts = 0
            for article_id, article_data in self.articles.items():
                text_path = os.path.join(abstract_dir, f"{article_id}.txt")
                if os.path.exists(text_path):
                    try:
                        with open(text_path, "r", encoding="utf-8", errors="ignore") as f:
                            article_data["text"] = f.read()
                        loaded_texts += 1
                    except Exception as e:
                        print(f"Warning: Failed to load {article_id}.txt: {e}")

            print(f"Loaded abstracts for {loaded_texts}/{len(self.articles)} articles")

        # Load citation graph
        if edge_list_path and os.path.exists(edge_list_path):
            self._load_edge_list(edge_list_path)

        # Load pre-computed node features
        if node_features_path and os.path.exists(node_features_path):
            self._load_node_features(node_features_path)

        self.dataset_loaded = True
        print(
            f"Dataset loading complete: {len(self.articles)} articles, "
            f"{self.citation_graph.number_of_edges()} citation edges"
        )

        return len(self.articles)

    def _parse_year(self, raw: Any) -> Optional[int]:
        """Extract a 4-digit publication year from a string or number."""
        try:
            year = int(str(raw).strip()[:4])
            if 1800 <= year <= 2100:
                return year
        except Exception:
            pass
        return None

    def _load_edge_list(self, edge_list_path: str):
        """Load citation graph from edge list file (index-based or PMID-based)."""
        print(f"Loading citation graph from: {edge_list_path}")

        is_gzipped = edge_list_path.endswith(".gz")
        edges_loaded = 0

        def _process_row(row):
            nonlocal edges_loaded
            if len(row) < 2:
                return
            # Support both index-based and PMID-based edge lists
            raw_src, raw_tgt = row[0].strip(), row[1].strip()

            # Try index-based lookup first
            try:
                src_idx, tgt_idx = int(raw_src), int(raw_tgt)
                src_id = self.idx_to_article_id.get(src_idx)
                tgt_id = self.idx_to_article_id.get(tgt_idx)
            except ValueError:
                # Fall back to treating values directly as article IDs (PMIDs)
                src_id, tgt_id = raw_src, raw_tgt

            if src_id and tgt_id and src_id in self.articles and tgt_id in self.articles:
                self.citation_graph.add_edge(src_id, tgt_id)
                edges_loaded += 1

        try:
            opener = gzip.open(edge_list_path, "rt") if is_gzipped else open(edge_list_path, "r")
            with opener as f:
                reader = csv.reader(f)
                next(reader, None)  # Skip header if present
                for row in reader:
                    _process_row(row)

            print(f"Citation graph loaded: {edges_loaded} edges")
        except Exception as e:
            print(f"Warning: Failed to load edge list: {e}")

    def _load_node_features(self, node_features_path: str):
        """Load pre-computed node features / embeddings (optional)."""
        print(f"Loading node features from: {node_features_path}")
        # Extend here to load numpy .npy arrays or JSON-serialised embeddings
        pass

    # ------------------------------------------------------------------
    # Graph construction from raw case dicts
    # ------------------------------------------------------------------

    def build_graph(self, articles_data: Optional[List[Dict[str, Any]]] = None):
        """
        Build citation graph from loaded data or a provided article list.

        Args:
            articles_data: Optional list of article dicts with 'article_id' and
                           'citations' (list of cited PMIDs) fields.
        """
        if articles_data:
            print(f"Building graph from {len(articles_data)} provided articles")

            for article in articles_data:
                article_id = article["article_id"]

                if article_id not in self.articles:
                    self.articles[article_id] = article

                for cited_id in article.get("citations", []):
                    if cited_id in self.articles:
                        self.citation_graph.add_edge(article_id, cited_id)

        print(
            f"Citation graph: {self.citation_graph.number_of_nodes()} nodes, "
            f"{self.citation_graph.number_of_edges()} edges"
        )

    # ------------------------------------------------------------------
    # Embedding
    # ------------------------------------------------------------------

    def get_article_embedding(
        self,
        article_id: str,
        use_cache: bool = True,
    ) -> np.ndarray:
        """
        Get BioBERT embedding for an article.

        The agent prefers the abstract text; if unavailable, falls back to the
        title, and then to a placeholder string.

        Args:
            article_id: Article PMID / identifier
            use_cache: Whether to use a cached embedding

        Returns:
            Normalised 768-dimensional embedding vector
        """
        if use_cache and article_id in self.article_embeddings:
            return self.article_embeddings[article_id]

        if article_id not in self.articles:
            raise ValueError(f"Article {article_id} not found in dataset")

        article_data = self.articles[article_id]
        text = article_data.get("text") or article_data.get("title", "")

        if not text:
            print(f"Warning: No text for article {article_id}, using title")
            text = article_data.get("title", "Unknown article")

        embedding = self._encode_text(text)
        self.article_embeddings[article_id] = embedding

        return embedding

    def _encode_text(self, text: str) -> np.ndarray:
        """Encode text using BioBERT and return a normalised [CLS] embedding."""
        inputs = self.tokenizer(
            text,
            max_length=self.max_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )

        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.model(**inputs)
            # [CLS] token is at position 0 — captures sentence-level semantics
            embedding = outputs.last_hidden_state[:, 0, :].cpu().numpy()

        # L2 normalise for cosine similarity via dot product
        embedding = embedding / (np.linalg.norm(embedding) + 1e-9)

        return embedding.flatten()

    def compute_all_embeddings(self, batch_size: int = 8):
        """
        Pre-compute BioBERT embeddings for every article in the dataset.

        Args:
            batch_size: Number of articles to process per iteration
        """
        print(f"\nComputing BioBERT embeddings for {len(self.articles)} articles...")

        article_ids = list(self.articles.keys())
        total = len(article_ids)

        for i in range(0, total, batch_size):
            batch_ids = article_ids[i : i + batch_size]
            for article_id in batch_ids:
                self.get_article_embedding(article_id, use_cache=True)

            processed = min(i + batch_size, total)
            if processed % 100 == 0 or processed >= total:
                print(f"  Processed {processed}/{total} articles")

        self.embeddings_computed = True
        print("All embeddings computed successfully")

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def retrieve_similar_articles(
        self,
        query_article_id: str,
        top_k: int = 10,
        use_citations: bool = True,
        use_semantic: bool = True,
        max_citation_hops: int = 2,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve similar biomedical articles using hybrid graph + semantic retrieval.

        Args:
            query_article_id: Query article PMID / identifier
            top_k: Number of top articles to retrieve
            use_citations: Whether to incorporate citation graph scoring
            use_semantic: Whether to incorporate semantic (BioBERT) similarity
            max_citation_hops: Maximum citation hops for graph traversal

        Returns:
            List of retrieved articles with scores and biomedical reasoning
        """
        if query_article_id not in self.articles:
            raise ValueError(f"Query article {query_article_id} not found")

        print(f"\nRetrieving similar articles for: {query_article_id}")
        print(f"  Query: {self.articles[query_article_id]['title']}")

        query_embedding = self.get_article_embedding(query_article_id)

        candidates: Set[str] = set()
        citation_scores: Dict[str, float] = {}
        semantic_scores: Dict[str, float] = {}

        # --- 1. Citation-based retrieval ---
        if use_citations and self.citation_graph.number_of_edges() > 0:
            citation_candidates = self._get_citation_neighbors(
                query_article_id,
                max_hops=max_citation_hops,
            )
            candidates.update(citation_candidates.keys())
            citation_scores = citation_candidates
            print(f"  Found {len(citation_candidates)} citation-based candidates")

        # --- 2. Semantic retrieval ---
        if use_semantic or len(candidates) == 0:
            for article_id in self.articles.keys():
                if article_id == query_article_id:
                    continue
                article_embedding = self.get_article_embedding(article_id)
                similarity = float(np.dot(query_embedding, article_embedding))
                semantic_scores[article_id] = similarity
                candidates.add(article_id)

            print(f"  Computed semantic similarity for {len(semantic_scores)} articles")

        # --- 3. Hybrid scoring ---
        hybrid_scores: Dict[str, float] = {}
        for article_id in candidates:
            c_score = citation_scores.get(article_id, 0.0)
            s_score = semantic_scores.get(article_id, 0.0)

            if use_citations and use_semantic:
                hybrid_score = (
                    self.citation_weight * c_score + self.semantic_weight * s_score
                )
            elif use_citations:
                hybrid_score = c_score
            else:
                hybrid_score = s_score

            hybrid_scores[article_id] = hybrid_score

        # --- 4. Rank and select top-k ---
        ranked_articles = sorted(
            hybrid_scores.items(), key=lambda x: x[1], reverse=True
        )[:top_k]

        # --- 5. Build result with reasoning ---
        results = []
        for rank, (article_id, score) in enumerate(ranked_articles, 1):
            article_data = self.articles[article_id]

            result = {
                "rank": rank,
                "article_id": article_id,
                "title": article_data["title"],
                "journal": article_data.get("journal"),
                "year": article_data.get("year"),
                "mesh_terms": article_data.get("mesh_terms"),
                "similarity_score": float(score),
                "semantic_score": semantic_scores.get(article_id, 0.0),
                "citation_score": citation_scores.get(article_id, 0.0),
                "reasoning": self._generate_article_reasoning(
                    query_article_id,
                    article_id,
                    semantic_scores.get(article_id, 0.0),
                    citation_scores.get(article_id, 0.0),
                ),
            }
            results.append(result)

        print(f"  Retrieved {len(results)} similar articles")
        return results

    def _get_citation_neighbors(
        self,
        article_id: str,
        max_hops: int = 2,
    ) -> Dict[str, float]:
        """
        Get citation neighbours with distance-based scoring.

        Scoring scheme:
          1.0 — direct forward citation  (query cites candidate)
          0.9 — direct backward citation (candidate cites query)
          0.5 — 2-hop forward neighbour

        Args:
            article_id: Source article identifier
            max_hops: Maximum citation distance to traverse

        Returns:
            Dict mapping article_id -> citation score
        """
        if article_id not in self.citation_graph:
            return {}

        neighbors: Dict[str, float] = {}

        # Forward: articles cited by the query
        for target in self.citation_graph.successors(article_id):
            neighbors[target] = 1.0

        # Backward: articles that cite the query
        for source in self.citation_graph.predecessors(article_id):
            neighbors[source] = 0.9

        # 2-hop forward neighbours
        if max_hops >= 2:
            second_hop: Set[str] = set()
            for neighbor in list(neighbors.keys()):
                if neighbor in self.citation_graph:
                    for target in self.citation_graph.successors(neighbor):
                        if target != article_id and target not in neighbors:
                            second_hop.add(target)
            for target in second_hop:
                neighbors[target] = 0.5

        return neighbors

    # ------------------------------------------------------------------
    # Reasoning generation
    # ------------------------------------------------------------------

    def _generate_article_reasoning(
        self,
        query_id: str,
        candidate_id: str,
        semantic_score: float,
        citation_score: float,
    ) -> str:
        """Generate human-readable biomedical reasoning for article similarity."""
        query_article = self.articles[query_id]
        candidate_article = self.articles[candidate_id]

        reasoning_parts = []

        # Semantic reasoning
        if semantic_score > 0.8:
            reasoning_parts.append(
                f"High semantic similarity ({semantic_score:.2f}) indicates strong "
                "conceptual overlap in biomedical terminology, methodology, or findings."
            )
        elif semantic_score > 0.6:
            reasoning_parts.append(
                f"Moderate semantic similarity ({semantic_score:.2f}) suggests related "
                "biomedical concepts, disease areas, or experimental approaches."
            )
        elif semantic_score > 0.4:
            reasoning_parts.append(
                f"Some semantic similarity ({semantic_score:.2f}) indicates partial "
                "relevance within the broader biomedical domain."
            )

        # Citation reasoning
        if citation_score >= 1.0:
            reasoning_parts.append(
                "This article is directly cited by the query article, establishing "
                "an explicit scientific reference relationship."
            )
        elif citation_score >= 0.9:
            reasoning_parts.append(
                "This article cites the query article, demonstrating awareness and "
                "scientific engagement with its findings."
            )
        elif citation_score >= 0.5:
            reasoning_parts.append(
                "This article is connected through the citation network (2-hop), "
                "indicating indirect scientific influence."
            )

        # Temporal reasoning
        query_year = query_article.get("year")
        candidate_year = candidate_article.get("year")

        if query_year and candidate_year:
            year_diff = query_year - candidate_year
            if year_diff > 0:
                reasoning_parts.append(
                    f"This article ({candidate_year}) predates the query article "
                    f"({query_year}) by {year_diff} year(s), potentially serving as "
                    "foundational prior work."
                )
            elif year_diff < 0:
                reasoning_parts.append(
                    f"This article ({candidate_year}) is {abs(year_diff)} year(s) "
                    f"more recent than the query article ({query_year}), possibly "
                    "representing follow-up research."
                )

        if not reasoning_parts:
            reasoning_parts.append(
                "Related article identified via hybrid biomedical retrieval scoring."
            )

        return " ".join(reasoning_parts)

    # ------------------------------------------------------------------
    # Output generation
    # ------------------------------------------------------------------

    def generate_reasoning_output(
        self,
        query_article_id: str,
        retrieved_articles: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Generate structured output with biomedical reasoning summary.

        Args:
            query_article_id: Query article identifier (PMID)
            retrieved_articles: List of retrieved articles from retrieve_similar_articles()

        Returns:
            Structured output dict with reasoning summary and retrieval metadata
        """
        query_article = self.articles[query_article_id]

        if len(retrieved_articles) == 0:
            summary = "No similar articles found in the dataset."
        else:
            high_sim_count = sum(
                1 for a in retrieved_articles if a["similarity_score"] > 0.7
            )
            citation_count = sum(
                1 for a in retrieved_articles if a["citation_score"] > 0.5
            )
            avg_year = (
                np.mean(
                    [a["year"] for a in retrieved_articles if a["year"] is not None]
                )
                if any(a["year"] for a in retrieved_articles)
                else None
            )

            summary = (
                f"The query article '{query_article['title']}' shows strong biomedical "
                f"connections to {len(retrieved_articles)} related articles. "
            )
            if high_sim_count > 0:
                summary += (
                    f"{high_sim_count} article(s) exhibit high semantic similarity (>0.7), "
                    "indicating shared biological concepts and methodological approaches. "
                )
            if citation_count > 0:
                summary += (
                    f"{citation_count} article(s) are connected through the citation network, "
                    "establishing direct scientific reference relationships. "
                )
            if avg_year:
                summary += (
                    f"Retrieved articles span an average publication year of {int(avg_year)}, "
                    "providing temporal context for scientific progression. "
                )
            summary += (
                "These articles collectively form a robust external biomedical knowledge "
                "base for downstream analysis and evidence synthesis."
            )

        output = {
            "query_article": query_article_id,
            "query_title": query_article["title"],
            "query_year": query_article.get("year"),
            "query_journal": query_article.get("journal"),
            "top_references": [
                {
                    "article_id": article["article_id"],
                    "title": article["title"],
                    "journal": article.get("journal"),
                    "year": article["year"],
                    "mesh_terms": article.get("mesh_terms"),
                    "similarity_score": round(article["similarity_score"], 3),
                    "semantic_score": round(article["semantic_score"], 3),
                    "citation_score": round(article["citation_score"], 3),
                    "reasoning": article["reasoning"],
                }
                for article in retrieved_articles
            ],
            "overall_biomedical_context_summary": summary,
            "retrieval_metadata": {
                "total_retrieved": len(retrieved_articles),
                "citation_weight": self.citation_weight,
                "semantic_weight": self.semantic_weight,
                "model": self.model_name,
            },
        }

        return output

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_statistics(self) -> Dict[str, Any]:
        """Return a summary of the agent's current state."""
        stats = {
            "total_articles": len(self.articles),
            "embeddings_computed": len(self.article_embeddings),
            "citation_graph": {
                "nodes": self.citation_graph.number_of_nodes(),
                "edges": self.citation_graph.number_of_edges(),
                "density": (
                    nx.density(self.citation_graph)
                    if self.citation_graph.number_of_nodes() > 0
                    else 0
                ),
            },
            "model": self.model_name,
            "device": self.device,
            "weights": {
                "citation": self.citation_weight,
                "semantic": self.semantic_weight,
            },
        }

        years = [a.get("year") for a in self.articles.values() if a.get("year")]
        if years:
            stats["year_range"] = {
                "min": min(years),
                "max": max(years),
                "mean": int(np.mean(years)),
            }

        return stats


# ----------------------------------------------------------------------
# Demo / smoke-test
# ----------------------------------------------------------------------

def demo_biobert_agent():
    """Demonstrate BioBERT External Agent with a sample PubMed-style dataset."""
    print("\n" + "=" * 70)
    print("BIOBERT EXTERNAL AGENT DEMO")
    print("=" * 70)

    print("\n1. Initializing BioBERT External Agent...")
    agent = BioBERTExternalAgent(
        model_name="dmis-lab/biobert-v1.1",
        use_citation_weight=0.4,
        use_semantic_weight=0.6,
        device=None,  # Auto-detect
    )

    print("\n2. Loading dataset...")

    # -------------------------------------------------------------------
    # Replace this path with your actual PubMed CSV mapping file.
    # Expected columns: pmid, title, journal, year  (mesh_terms optional)
    # -------------------------------------------------------------------
    base_path = "/path/to/your/pubmed/dataset"
    article_mapping_path = os.path.join(base_path, "article_mapping.csv")

    num_articles = agent.load_dataset(
        article_mapping_path=article_mapping_path,
        max_articles=100,
    )

    print(f"\n3. Computing embeddings for {num_articles} articles...")
    agent.compute_all_embeddings(batch_size=4)

    print("\n4. Running retrieval on sample query article...")
    sample_ids = list(agent.articles.keys())[:10]
    query_article_id = sample_ids[0]

    print(f"   Query Article: {query_article_id}")
    print(f"   Title: {agent.articles[query_article_id]['title']}")

    retrieved = agent.retrieve_similar_articles(
        query_article_id=query_article_id,
        top_k=5,
        use_citations=False,  # No edge list loaded in demo
        use_semantic=True,
    )

    print("\n5. Generating structured reasoning output...")
    output = agent.generate_reasoning_output(
        query_article_id=query_article_id,
        retrieved_articles=retrieved,
    )

    print("\n" + "=" * 70)
    print("STRUCTURED OUTPUT")
    print("=" * 70)
    print(json.dumps(output, indent=2))

    print("\n" + "=" * 70)
    print("AGENT STATISTICS")
    print("=" * 70)
    stats = agent.get_statistics()
    print(json.dumps(stats, indent=2))

    print("\n" + "=" * 70)
    print("DEMO COMPLETED SUCCESSFULLY")
    print("=" * 70)

    return output, agent


if __name__ == "__main__":
    import sys

    if "--test" in sys.argv:
        print("Running BioBERT External Agent demo...")
        output, agent = demo_biobert_agent()

        print("\n" + "=" * 70)
        print("VALIDATION")
        print("=" * 70)

        required_keys = ["query_article", "top_references", "overall_biomedical_context_summary"]
        for key in required_keys:
            assert key in output, f"Missing key: {key}"
            print(f"✓ {key} present")

        assert len(output["top_references"]) > 0, "No references retrieved"
        print(f"✓ Retrieved {len(output['top_references'])} references")

        for ref in output["top_references"]:
            assert "similarity_score" in ref, "Missing similarity_score"
            assert "reasoning" in ref, "Missing reasoning"
            assert 0 <= ref["similarity_score"] <= 1, "Invalid similarity score"

        print("✓ All references have valid scores and reasoning")

        print("\n" + "=" * 70)
        print("ALL VALIDATIONS PASSED ✓")
        print("=" * 70)
    else:
        demo_biobert_agent()
