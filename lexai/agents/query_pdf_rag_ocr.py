"""RAG-based document query agent.

Retrieval  : FAISS + sentence-transformers
Generation : Google Gemini

OCR is not re-run when Flask already has cached text — use query_rag_from_text.
"""

import os
import json
import hashlib
from pathlib import Path
from typing import Dict

from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .ocr_agent import process_pdf

BASE_DIR = Path(__file__).resolve().parent.parent
INDEX_PATH = str(BASE_DIR / "faiss_index")
HASH_PATH = str(BASE_DIR / "faiss_index" / "doc_hash.txt")

_gemini_model = None


def _get_gemini_model():
    """Return a cached Gemini model instance, initialising it on first call."""
    global _gemini_model
    if _gemini_model is not None:
        return _gemini_model

    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise EnvironmentError(
            "GEMINI_API_KEY is not set. "
            "Add it to backend/.env and restart Flask."
        )

    import google.generativeai as genai
    genai.configure(api_key=api_key)
    _gemini_model = genai.GenerativeModel("gemini-flash-latest")
    return _gemini_model


def build_faiss_index(text: str) -> FAISS:
    embedding_model = HuggingFaceEmbeddings(
        model_name="sentence-transformers/paraphrase-MiniLM-L6-v2"
    )
    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)
    chunks = splitter.split_text(text)
    if not chunks:
        raise ValueError("No text chunks available for indexing")
    return FAISS.from_texts(chunks, embedding=embedding_model)


def query_rag(vectordb: FAISS, query: str, k: int = 4) -> str:
    """Retrieve top-k passages with FAISS, then ask Gemini to synthesise an answer."""
    docs = vectordb.similarity_search(query, k=k)
    context = "\n\n".join(
        [f"[Passage {i+1}]\n{d.page_content}" for i, d in enumerate(docs)]
    )

    prompt = f"""You are a legal assistant specialising in Indian law.
Answer the user's question using ONLY the passages provided below.
If the answer is not in the passages, say so honestly.

---
{context}
---

Question: {query}

Give a clear, concise answer in 2–4 sentences. Cite the passage number (e.g. [Passage 1]) where relevant."""

    model = _get_gemini_model()
    response = model.generate_content(prompt)
    return response.text.strip()


def _load_or_build_index(document_text: str) -> FAISS:
    current_hash = hashlib.md5(document_text.encode()).hexdigest()
    index_ready = os.path.exists(INDEX_PATH) and os.path.exists(HASH_PATH)
    if index_ready:
        with open(HASH_PATH) as f:
            index_ready = f.read().strip() == current_hash

    if index_ready:
        embedding_model = HuggingFaceEmbeddings(
            model_name="sentence-transformers/paraphrase-MiniLM-L6-v2"
        )
        return FAISS.load_local(
            INDEX_PATH,
            embedding_model,
            allow_dangerous_deserialization=True,
        )

    vectordb = build_faiss_index(document_text)
    os.makedirs(INDEX_PATH, exist_ok=True)
    vectordb.save_local(INDEX_PATH)
    with open(HASH_PATH, "w") as f:
        f.write(current_hash)
    return vectordb


def query_pdf_with_ocr(pdf_path: str, query: str) -> Dict[str, str]:
    ocr_result = process_pdf(pdf_path)
    document_text = (ocr_result.get("full_text") or ocr_result.get("raw_text") or "").strip()

    if not document_text:
        return {
            "File Name": ocr_result.get("file_name", "Unknown"),
            "Title": ocr_result.get("title", "Untitled"),
            "Query": query,
            "Answer": "No textual content could be extracted from this document.",
        }

    try:
        vectordb = _load_or_build_index(document_text)
        answer = query_rag(vectordb, query)
    except (ValueError, EnvironmentError) as exc:
        answer = f"Query failed: {exc}"

    return {
        "File Name": ocr_result.get("file_name", "Unknown"),
        "Title": ocr_result.get("title", "Untitled"),
        "Query": query,
        "Answer": answer,
    }


def query_rag_from_text(
    document_text: str,
    query: str,
    title: str = "Document",
) -> Dict[str, str]:
    """Query using pre-extracted OCR text stored in the database."""
    if not document_text or not document_text.strip():
        return {
            "Title": title,
            "Query": query,
            "Answer": "No textual content available for this document.",
        }

    try:
        vectordb = _load_or_build_index(document_text)
        answer = query_rag(vectordb, query)
    except (ValueError, EnvironmentError) as exc:
        answer = f"Query failed: {exc}"

    return {
        "Title": title,
        "Query": query,
        "Answer": answer,
    }


if __name__ == "__main__":
    sample_pdf = "lexai/data/raw/1-266Right_to_Privacy__Puttaswamy_Judgment-Chandrachud.pdf"
    sample_query = "What does the judgment say about Article 19(1)(a)?"
    result = query_pdf_with_ocr(sample_pdf, sample_query)
    print(json.dumps(result, indent=2))
