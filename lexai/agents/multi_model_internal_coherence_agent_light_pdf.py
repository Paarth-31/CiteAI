# import re
# import json
# from typing import List, Dict, Any

# from langchain_text_splitters import RecursiveCharacterTextSplitter
# from langchain_community.vectorstores import FAISS
# from langchain_community.embeddings import HuggingFaceEmbeddings
# from transformers import pipeline
# from langchain_community.llms import HuggingFacePipeline

# from .ocr_agent import process_pdf  # Import OCR agent


# # ===========================================
# # 1. Model Setup (Lightweight Versions)
# # ===========================================
# from transformers import pipeline
# from langchain_community.embeddings import HuggingFaceEmbeddings
# from langchain_community.llms import HuggingFacePipeline
# from langchain_community.tools import DuckDuckGoSearchRun

# # -----------------------------
# # 1. Lightweight Classification & NLI
# # -----------------------------
# # Use a smaller and faster NLI model for zero-shot tasks
# #extractor = pipeline(
# #    "zero-shot-classification",
# #    model="facebook/bart-large-mnli",     # moderate accuracy, faster than distilbart-mnli
# #    device=-1                            # ensure CPU
# #)

# # Or for extreme speed (sacrifices a bit of accuracy):
# extractor = pipeline("zero-shot-classification", model="typeform/distilbert-base-uncased-mnli", device=-1)

# # -----------------------------
# # 2. Tiny Embedding Model
# # -----------------------------
# embedding_model = HuggingFaceEmbeddings(
#     model_name="sentence-transformers/all-MiniLM-L6-v2"  # small, fast, robust on CPU
# )

# # -----------------------------
# # 3. Logic Reasoning Model (Small)
# # -----------------------------
# logic_pipe = pipeline(
#     "text2text-generation",
#     model="google/flan-t5-base",          # decent reasoning, still fast on CPU
#     max_new_tokens=200,
#     device=-1
# )
# logic_llm = HuggingFacePipeline(pipeline=logic_pipe)

# # -----------------------------
# # 4. NLI (Contradiction Detection)
# # -----------------------------
# nli = pipeline(
#     "text-classification",
#     model="typeform/distilbert-base-uncased-mnli",  # very small, optimized
#     device=-1
# )

# # -----------------------------
# # 5. Final Summarization / Report Model
# # -----------------------------
# final_pipe = pipeline(
#     "text-generation",
#     model="microsoft/Phi-1.5",            # lighter than Phi-2, still coherent
#     max_new_tokens=300,
#     temperature=0.3,
#     device=-1
# )
# final_llm = HuggingFacePipeline(pipeline=final_pipe)
# # Lazy load search if needed (not currently used in analysis)
# search = None


# # ===========================================
# # 2. Regex Citation Extractor
# # ===========================================
# def extract_citations_regex(text: str) -> List[str]:
#     patterns = [
#         r"Article\s\d+[A-Z]?(?:\(\d+\))?",
#         r"(?:Section|Sec\.?)\s\d+[A-Z]?(?:\(\d+\))?",
#         r"[A-Z][A-Za-z&\s]+(?:vs\.?|v\.?)\s[A-Z][A-Za-z&\s]+",
#         r"[A-Z][a-zA-Z\s]+Act(?:,\s*\d{4})?",
#         r"\bAIR\s\d{4}\s[A-Z]{2,}\s\d+\b",
#         r"\b\d{4}\s*\(\d+\)\s*SCC\s*\d+\b",
#     ]
#     found = []
#     for p in patterns:
#         found += re.findall(p, text, flags=re.IGNORECASE)
#     return list(set([f.strip() for f in found]))


# # ===========================================
# # 3. Claim Extraction
# # ===========================================
# def extract_claims(text: str) -> List[str]:
#     # Limit text length to avoid processing too much data
#     text = text[:50000]  # Limit to first 50k characters
    
#     sentences = re.split(r'(?<=[\.\n])\s+', text)
#     claims = []
    
#     LIMIT=1000  
#     for s in sentences[:LIMIT]:
#         if not s.strip():
#             continue
#         res = extractor(s, candidate_labels=["legal argument", "evidence", "factual statement"], multi_label=False)
#         if res["labels"][0] in ["legal argument", "evidence"] and res["scores"][0] > 0.5:
#             claims.append(s.strip())
        
#         # Stop if we have enough claims
#         if len(claims) >= 20:
#             break
    
#     return claims


# # ===========================================
# # 4. FAISS Index Builder
# # ===========================================
# def build_faiss_index(text: str):
#     splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)
#     chunks = splitter.split_text(text)
#     vectordb = FAISS.from_texts(chunks, embedding=embedding_model)
#     return vectordb


# # ===========================================
# # 5. Logical Flow Analyzer
# # ===========================================
# def analyze_logical_flows(claims: List[str]) -> str:
#     # Limit claims to avoid CUDA OOM - take first 10 claims or truncate text
#     limited_claims = claims[:10] if len(claims) > 10 else claims
#     joined_claims = "\n".join([f"- {c[:200]}" for c in limited_claims])  # Truncate each claim to 200 chars
    
#     # Ensure total prompt is under 400 tokens (roughly 1600 chars)
#     if len(joined_claims) > 1400:
#         joined_claims = joined_claims[:1400] + "..."
    
#     prompt = f"Summarize the logical flow among these legal claims:\n{joined_claims}"
#     return logic_llm.invoke(prompt)


# # ===========================================
# # 6. Contradiction Detector
# # ===========================================
# def detect_contradictions(claims: List[str]) -> List[str]:
#     contradictions = []
#     for i in range(len(claims)):
#         for j in range(i + 1, len(claims)):
#             pair = f"{claims[i]} </s> {claims[j]}"
#             result = nli(pair)
#             label = result[0]["label"].lower()
#             if "contradiction" in label:
#                 contradictions.append(f"Contradiction between: '{claims[i]}' AND '{claims[j]}'")
#     return contradictions


# # ===========================================
# # 7. Context Retrieval
# # ===========================================
# def retrieve_context(vectordb, claims: List[str]) -> Dict[str, List[str]]:
#     context = {}
#     for c in claims:
#         try:
#             docs = vectordb.similarity_search(c, k=2)
#             snippets = [d.page_content for d in docs]
#         except Exception:
#             snippets = []
#         context[c] = snippets
#     return context


# # ===========================================
# # 8. Coherence Scoring (Safe JSON Handling)
# # ===========================================
# def generate_coherence_report(document: str, flows: str, contradictions: List[str], context: Dict[str, Any]) -> Dict[str, Any]:
#     sample_context = "\n".join([f"{k}: {v[:2]}" for k, v in context.items()])
#     prompt = f"""
# You are a legal reasoning coherence analyzer.

# Document excerpt:
# {document[:1000]}

# Argument Flows:
# {flows}

# Contradictions:
# {contradictions}

# Context:
# {sample_context[:700]}

# Return JSON with exactly these keys:
# - Key Argument Flows (list of strings)
# - Detected Contradictions (list of strings)
# - Logical Gaps (list of strings)
# - Coherence Score (float between 0 and 1)
# - Brief Commentary (string)
# """
#     output = final_llm.invoke(prompt)

#     try:
#         cleaned = output.replace("\n", "").replace(",}", "}")
#         return json.loads(cleaned)
#     except Exception:
#         # fallback safe structure
#         return {
#             "Key Argument Flows": flows.split("\n") if flows else [],
#             "Detected Contradictions": contradictions,
#             "Logical Gaps": [],
#             "Coherence Score": 0.0,
#             "Brief Commentary": output
#         }


# # ===========================================
# # 9. Master Orchestrator (PDF Input)
# # ===========================================
# def run_internal_coherence_agent(pdf_path: str) -> Dict[str, Any]:
#     ocr_result = process_pdf(pdf_path)
#     document_text = ocr_result["raw_text"]

#     citations = extract_citations_regex(document_text)
#     claims = extract_claims(document_text)
#     vectordb = build_faiss_index(document_text)
#     flows = analyze_logical_flows(claims)
#     contradictions = detect_contradictions(claims)
#     context = retrieve_context(vectordb, claims[:5])
#     report = generate_coherence_report(document_text, flows, contradictions, context)

#     return {
#         "File Name": ocr_result["file_name"],
#         "Title": ocr_result["title"],
#         "Citations": citations,
#         "Claims": claims,
#         "Contradictions": contradictions,
#         "Final Report": report
#     }


# # ===========================================
# # Example Run
# # ===========================================
# if __name__ == "__main__":
#     pdf_path = "CiteAI/corpus/legal_pdfs/example.pdf"
#     result = run_internal_coherence_agent(pdf_path)
#     print(json.dumps(result, indent=2))






"""
multi_model_internal_coherence_agent_light_pdf.py

Internal coherence analysis for legal documents.

Extraction  : distilbert zero-shot classification (local, fast, unchanged)
Embeddings  : sentence-transformers/all-MiniLM-L6-v2 (local, unchanged)
Reasoning   : Google Gemini gemini-1.5-flash  (replaces flan-t5 + phi-1.5)

Why changed:
  - 'text2text-generation' pipeline task was removed in the installed
    version of transformers — causes KeyError at module import time,
    crashing the entire agent before any analysis runs.
  - microsoft/Phi-1.5 (final_llm) is a 1.3B model run on CPU — extremely
    slow for a report-generation call.
  - Gemini is near-instant, needs no local GPU/RAM, and produces
    significantly better structured JSON output.
"""

import os
import re
import json
from typing import List, Dict, Any

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from transformers import pipeline

from .ocr_agent import process_pdf


# =============================================================================
# 1. Model setup — only models that work with the installed transformers
# =============================================================================

# Zero-shot classifier: kept local (small, works fine)
extractor = pipeline(
    "zero-shot-classification",
    model="typeform/distilbert-base-uncased-mnli",
    device=-1,
)

# Embedding model: kept local (fast on CPU)
embedding_model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

# NLI for contradiction detection: kept local
nli = pipeline(
    "text-classification",
    model="typeform/distilbert-base-uncased-mnli",
    device=-1,
)

# Gemini client — lazy initialised on first use
_gemini_model = None


def _get_gemini():
    """Return a cached Gemini model, initialising it on first call."""
    global _gemini_model
    if _gemini_model is not None:
        return _gemini_model

    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise EnvironmentError(
            "GEMINI_API_KEY not set in backend/.env. "
            "Add it and restart Flask."
        )

    import google.generativeai as genai
    genai.configure(api_key=api_key)
    _gemini_model = genai.GenerativeModel("gemini-flash-latest")
    return _gemini_model


def _gemini(prompt: str) -> str:
    """Call Gemini and return the text response."""
    model    = _get_gemini()
    response = model.generate_content(prompt)
    return response.text.strip()


# =============================================================================
# 2. Regex citation extractor (unchanged)
# =============================================================================
def extract_citations_regex(text: str) -> List[str]:
    patterns = [
        r"Article\s\d+[A-Z]?(?:\(\d+\))?",
        r"(?:Section|Sec\.?)\s\d+[A-Z]?(?:\(\d+\))?",
        r"[A-Z][A-Za-z&\s]+(?:vs\.?|v\.?)\s[A-Z][A-Za-z&\s]+",
        r"[A-Z][a-zA-Z\s]+Act(?:,\s*\d{4})?",
        r"\bAIR\s\d{4}\s[A-Z]{2,}\s\d+\b",
        r"\b\d{4}\s*\(\d+\)\s*SCC\s*\d+\b",
    ]
    found = []
    for p in patterns:
        found += re.findall(p, text, flags=re.IGNORECASE)
    return list(set([f.strip() for f in found]))


# =============================================================================
# 3. Claim extractor (unchanged — uses local distilbert)
# =============================================================================
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


# =============================================================================
# 4. FAISS index builder (unchanged)
# =============================================================================
def build_faiss_index(text: str) -> FAISS:
    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)
    chunks   = splitter.split_text(text)
    return FAISS.from_texts(chunks, embedding=embedding_model)


# =============================================================================
# 5. Logical flow analyser — NOW USES GEMINI instead of flan-t5
# =============================================================================
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
    except Exception as exc:
        # Fallback: plain concatenation if Gemini fails
        return f"Key claims identified: {'; '.join(limited[:3])}"


# =============================================================================
# 6. Contradiction detector (unchanged — uses local NLI)
# =============================================================================
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


# =============================================================================
# 7. Context retrieval (unchanged)
# =============================================================================
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


# =============================================================================
# 8. Coherence report — NOW USES GEMINI instead of phi-1.5
# =============================================================================
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
        # Strip any markdown fences Gemini might add
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


# =============================================================================
# 9. Master orchestrator
# =============================================================================
def run_internal_coherence_agent(pdf_path: str) -> Dict[str, Any]:
    ocr_result    = process_pdf(pdf_path)
    document_text = ocr_result["raw_text"]

    citations     = extract_citations_regex(document_text)
    claims        = extract_claims(document_text)
    vectordb      = build_faiss_index(document_text)
    flows         = analyze_logical_flows(claims)
    contradictions = detect_contradictions(claims)
    context       = retrieve_context(vectordb, claims[:5])
    report        = generate_coherence_report(document_text, flows, contradictions, context)

    return {
        "File Name":     ocr_result.get("file_name", "Unknown"),
        "Title":         ocr_result.get("title", "Untitled"),
        "Citations":     citations,
        "Claims":        claims,
        "Contradictions": contradictions,
        "Final Report":  report,
    }


# =============================================================================
# CLI smoke test
# =============================================================================
if __name__ == "__main__":
    pdf_path = "lexai/data/raw/1-266Right_to_Privacy__Puttaswamy_Judgment-Chandrachud.pdf"
    result   = run_internal_coherence_agent(pdf_path)
    print(json.dumps(result, indent=2))