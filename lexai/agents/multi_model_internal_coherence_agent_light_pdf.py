import os
import re
import json
from typing import List, Dict, Any

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from transformers import pipeline

from .ocr_agent import extract_citations, extract_articles, process_pdf

# Zero-shot classifier for extracting legal claims
extractor = pipeline(
    "zero-shot-classification",
    model="typeform/distilbert-base-uncased-mnli",
    device=-1,
)

# Text embedding model for FAISS vector indexing
embedding_model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

# Natural Language Inference model for contradiction detection
nli = pipeline(
    "text-classification",
    model="typeform/distilbert-base-uncased-mnli",
    device=-1,
)

_gemini_model = None

# Initialize cached Gemini generative model
def _get_gemini():
    global _gemini_model
    if _gemini_model is not None:
        return _gemini_model

    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise EnvironmentError(
            "GEMINI_API_KEY not set in backend/.env. Add it and restart Flask."
        )

    import google.generativeai as genai
    genai.configure(api_key=api_key)
    _gemini_model = genai.GenerativeModel("gemini-flash-latest")
    return _gemini_model

# Execute Gemini completion prompt
def _gemini(prompt: str) -> str:
    model = _get_gemini()
    response = model.generate_content(prompt)
    return response.text.strip()

def extract_citations_regex(text: str) -> List[str]:
    """Reuse the OCR agent's structured extractors instead of a third regex copy."""
    found = extract_citations(text) + extract_articles(text)
    seen: dict[str, None] = {}
    for item in found:
        cleaned = item.strip()
        if cleaned:
            seen[cleaned] = None
    return list(seen.keys())

# Extract high-confidence legal arguments and factual claims
def extract_claims(text: str) -> List[str]:
    text      = text[:50000]
    sentences = re.split(r"(?<=[.\n])\s+", text)
    claims    = []

    for s in sentences[:1000]:
        if not s.strip():
            continue
        res = extractor(
            s,
            candidate_labels=["legal argument", "evidence", "factual statement"],
            multi_label=False,
        )
        if res["labels"][0] in ["legal argument", "evidence"] and res["scores"][0] > 0.5:
            claims.append(s.strip())
        if len(claims) >= 20:
            break

    return claims

# Build FAISS vector store over chunked document text
def build_faiss_index(text: str) -> FAISS:
    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)
    chunks   = splitter.split_text(text)
    return FAISS.from_texts(chunks, embedding=embedding_model)

# Summarize logical progression across extracted claims using LLM
def analyze_logical_flows(claims: List[str]) -> str:
    limited = claims[:10]
    joined  = "\n".join([f"- {c[:200]}" for c in limited])

    prompt = f"""You are a legal reasoning expert.
Summarise the logical argument flow among these legal claims from a court document.
Write 2-3 sentences maximum.

Claims:
{joined}

Logical flow summary:"""

    try:
        return _gemini(prompt)
    except Exception:
        return f"Key claims identified: {'; '.join(limited[:3])}"

# Identify pairwise contradictions among claims using NLI
def detect_contradictions(claims: List[str]) -> List[str]:
    contradictions = []
    for i in range(len(claims)):
        for j in range(i + 1, len(claims)):
            pair   = f"{claims[i]} </s> {claims[j]}"
            result = nli(pair)
            label  = result[0]["label"].lower()
            if "contradiction" in label:
                contradictions.append(
                    f"Contradiction between: '{claims[i]}' AND '{claims[j]}'"
                )
    return contradictions

# Retrieve contextual snippets for claims from vector index
def retrieve_context(vectordb: FAISS, claims: List[str]) -> Dict[str, List[str]]:
    context = {}
    for c in claims:
        try:
            docs     = vectordb.similarity_search(c, k=2)
            snippets = [d.page_content for d in docs]
        except Exception:
            snippets = []
        context[c] = snippets
    return context

# Synthesize full internal coherence assessment report
def generate_coherence_report(
    document: str,
    flows: str,
    contradictions: List[str],
    context: Dict[str, Any],
) -> Dict[str, Any]:
    sample_context = "\n".join([f"{k[:100]}: {str(v)[:150]}" for k, v in list(context.items())[:3]])

    prompt = f"""You are a legal coherence analyser. Analyse the following legal document excerpt and return ONLY a valid JSON object.

Document excerpt:
{document[:1500]}

Argument flows identified:
{flows}

Contradictions found:
{json.dumps(contradictions[:5])}

Context snippets:
{sample_context[:600]}

Return ONLY a JSON object with exactly these keys (no markdown, no extra text):
{{
  "Key Argument Flows": ["string", "string"],
  "Detected Contradictions": ["string"],
  "Logical Gaps": ["string"],
  "Coherence Score": 0.75,
  "Brief Commentary": "string"
}}"""

    try:
        raw = _gemini(prompt)
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = "\n".join(cleaned.split("\n")[1:])
        if cleaned.endswith("```"):
            cleaned = "\n".join(cleaned.split("\n")[:-1])
        return json.loads(cleaned.strip())
    except Exception:
        return {
            "Key Argument Flows":       flows.split("\n") if flows else [],
            "Detected Contradictions":  contradictions,
            "Logical Gaps":             [],
            "Coherence Score":          0.0,
            "Brief Commentary":         flows or "Analysis could not be completed.",
        }

def run_internal_coherence_from_text(
    document_text: str,
    title: str = "Untitled",
    file_name: str = "Unknown",
) -> Dict[str, Any]:
    """Run internal coherence on already-extracted text. Does not re-OCR."""
    citations = extract_citations_regex(document_text)
    claims = extract_claims(document_text)
    vectordb = build_faiss_index(document_text) if document_text.strip() else None
    flows = analyze_logical_flows(claims)
    contradictions = detect_contradictions(claims)
    context = retrieve_context(vectordb, claims[:5]) if vectordb is not None else {}
    report = generate_coherence_report(document_text, flows, contradictions, context)

    return {
        "File Name": file_name,
        "Title": title,
        "Citations": citations,
        "Claims": claims,
        "Contradictions": contradictions,
        "Final Report": report,
    }


def run_internal_coherence_agent(pdf_path: str) -> Dict[str, Any]:
    """PDF entry point — OCR once, then reuse the text pipeline."""
    ocr_result = process_pdf(pdf_path)
    document_text = ocr_result.get("full_text") or ocr_result.get("raw_text") or ""
    return run_internal_coherence_from_text(
        document_text,
        title=ocr_result.get("title", "Untitled"),
        file_name=ocr_result.get("file_name", "Unknown"),
    )

if __name__ == "__main__":
    pdf_path = "lexai/data/raw/1-266Right_to_Privacy__Puttaswamy_Judgment-Chandrachud.pdf"
    result   = run_internal_coherence_agent(pdf_path)
    print(json.dumps(result, indent=2))