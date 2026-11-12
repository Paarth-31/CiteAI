/# ExternalInferenceAgent Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                      ExternalInferenceAgent                          │
│                                                                       │
│  ┌───────────────────────────────────────────────────────────┐     │
│  │ Initialization Phase                                       │     │
│  │  • Load sentence-transformer model                         │     │
│  │  • Configure device (CPU/GPU)                              │     │
│  └───────────────────────────────────────────────────────────┘     │
│                             ↓                                         │
│  ┌───────────────────────────────────────────────────────────┐     │
│  │ Index Building Phase (build_index)                         │     │
│  │                                                             │     │
│  │  1. Validate Candidates                                    │     │
│  │     └─ Check for required fields                           │     │
│  │     └─ Validate data types                                 │     │
│  │                                                             │     │
│  │  2. Create Embeddings                                      │     │
│  │     └─ Extract text from candidates                        │     │
│  │     └─ model.encode(texts) → embeddings                   │     │
│  │                                                             │     │
│  │  3. Normalize Embeddings                                   │     │
│  │     └─ L2 normalization: emb / ||emb||                    │     │
│  │     └─ For cosine similarity via inner product             │     │
│  │                                                             │     │
│  │  4. Build FAISS Index                                      │     │
│  │     └─ IndexFlatIP (inner product index)                  │     │
│  │     └─ Add normalized embeddings                          │     │
│  │                                                             │     │
│  │  5. Store Metadata                                         │     │
│  │     └─ candidates list                                     │     │
│  │     └─ embeddings array                                    │     │
│  └───────────────────────────────────────────────────────────┘     │
│                             ↓                                         │
│  ┌───────────────────────────────────────────────────────────┐     │
│  │ Inference Phase (infer)                                    │     │
│  │                                                             │     │
│  │  1. Encode Query                                           │     │
│  │     └─ model.encode(query) → query_embedding              │     │
│  │     └─ L2 normalize query embedding                        │     │
│  │                                                             │     │
│  │  2. Retrieve Candidates (_retrieve_candidates)            │     │
│  │     └─ FAISS search: index.search(query_emb, top_k)       │     │
│  │     └─ Returns: [(idx, score), ...]                       │     │
│  │                                                             │     │
│  │  3. Compute Similarity (_compute_similarity)              │     │
│  │     └─ Enrich candidates with similarity scores            │     │
│  │     └─ Preserve all original metadata                      │     │
│  │     └─ Returns: [{...candidate, similarity_score}, ...]   │     │
│  └───────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────┘
```

## Data Flow

```
Input Documents                 Embeddings                    FAISS Index
─────────────                  ──────────                    ───────────

┌──────────────┐              ┌──────────┐                  ┌─────────┐
│ Candidate 1  │              │ [0.2,... │                  │ Index   │
│ text: "..."  │──encode──>   │  0.8,... │──normalize──>    │ Flat IP │
└──────────────┘              │  0.3]    │     add          └─────────┘
                               └──────────┘                       │
┌──────────────┐              ┌──────────┐                       │
│ Candidate 2  │              │ [0.5,... │                       │
│ text: "..."  │──encode──>   │  0.1,... │──normalize──>────────┤
└──────────────┘              │  0.9]    │                       │
                               └──────────┘                       │
┌──────────────┐              ┌──────────┐                       │
│ Candidate N  │              │ [0.7,... │                       │
│ text: "..."  │──encode──>   │  0.4,... │──normalize──>────────┘
└──────────────┘              │  0.2]    │
                               └──────────┘

                                                                  
Query Flow
──────────

┌──────────────┐              ┌──────────┐              ┌────────────────┐
│ Query:       │              │ [0.3,... │              │ Top-K Results  │
│ "privacy     │──encode──>   │  0.6,... │──search──>   │ with scores    │
│  rights"     │              │  0.8]    │              └────────────────┘
└──────────────┘              └──────────┘                      │
                                   │                            │
                                   └──normalize                 ↓
                                                        ┌────────────────┐
                                                        │ [{text: "...", │
                                                        │   similarity:  │
                                                        │   0.89}, ...]  │
                                                        └────────────────┘
```

## Component Interactions

```
┌────────────────────────┐
│  Sentence Transformers │  ← Pre-trained language model
│  (all-MiniLM-L6-v2)    │     - Converts text to dense vectors
└───────────┬────────────┘     - 384-dimensional embeddings
            │
            ↓
┌────────────────────────┐
│  NumPy                 │  ← Array operations
│  (Normalization)       │     - L2 normalization
└───────────┬────────────┘     - Vector operations
            │
            ↓
┌────────────────────────┐
│  FAISS                 │  ← Similarity search
│  (IndexFlatIP)         │     - Inner product index
└───────────┬────────────┘     - Exact nearest neighbor
            │
            ↓
┌────────────────────────┐
│  Results               │  ← Enriched candidates
│  (similarity_score)    │     - Original metadata + scores
└────────────────────────┘     - Sorted by relevance
```

## Method Call Sequence

### Building Index
```
build_index(candidates)
    │
    ├─→ Validate inputs
    │   └─→ Check empty list
    │   └─→ Check required fields
    │   └─→ Check field types
    │
    ├─→ Initialize model (if needed)
    │   └─→ SentenceTransformer(model_name, device)
    │
    ├─→ Create embeddings
    │   └─→ model.encode(texts)
    │
    ├─→ Normalize
    │   └─→ embeddings / ||embeddings||
    │
    ├─→ Build index
    │   └─→ faiss.IndexFlatIP(dimension)
    │   └─→ index.add(normalized_embeddings)
    │
    └─→ Store state
        └─→ self.candidates = candidates
        └─→ self.candidate_embeddings = embeddings
```

### Inference
```
infer(query, top_k)
    │
    ├─→ Validate index exists
    │
    ├─→ _retrieve_candidates(query, top_k)
    │   │
    │   ├─→ Initialize model (if needed)
    │   │
    │   ├─→ Encode query
    │   │   └─→ model.encode([query])
    │   │
    │   ├─→ Normalize query
    │   │   └─→ query_emb / ||query_emb||
    │   │
    │   └─→ FAISS search
    │       └─→ index.search(query_emb, top_k)
    │       └─→ Returns: [(idx, score), ...]
    │
    └─→ _compute_similarity(query, retrieved)
        │
        └─→ For each (idx, score):
            └─→ Copy candidate[idx]
            └─→ Add similarity_score
            └─→ Append to results
```

## Key Design Decisions

### 1. Normalization Strategy
- **L2 Normalization**: Enables cosine similarity via inner product
- **Formula**: `normalized = vector / ||vector||`
- **Benefit**: Faster computation than explicit cosine calculation

### 2. FAISS Index Type
- **IndexFlatIP**: Inner Product index
- **Why**: With normalized vectors, IP ≡ cosine similarity
- **Trade-off**: Exact search (slower) vs approximate (faster but less accurate)

### 3. Lazy Loading
- Model loaded only when needed
- Reduces initialization overhead
- Allows index building without model if reusing

### 4. Metadata Preservation
- Store full candidate dictionaries
- Results include all original fields
- Enables filtering/post-processing

### 5. Error Handling
- Early validation of inputs
- Clear error messages with context
- Graceful handling of edge cases

## Performance Characteristics

| Operation | Time Complexity | Space Complexity |
|-----------|----------------|------------------|
| build_index | O(n × d) | O(n × d) |
| infer | O(n × d) | O(k) |
| _retrieve_candidates | O(n × d) | O(k) |
| _compute_similarity | O(k) | O(k) |

Where:
- n = number of candidates
- d = embedding dimension
- k = top_k results

## Scalability Considerations

### Small Scale (< 10K documents)
- ✅ IndexFlatIP (exact search)
- ✅ CPU encoding acceptable
- ✅ In-memory storage

### Medium Scale (10K - 1M documents)
- ⚡ Consider IndexIVFFlat (approximate)
- ⚡ GPU encoding recommended
- ⚡ Batch processing

### Large Scale (> 1M documents)
- 🚀 Required: IndexIVFFlat or IndexHNSW
- 🚀 Required: GPU acceleration
- 🚀 Consider: Distributed FAISS
- 🚀 Consider: Incremental updates
