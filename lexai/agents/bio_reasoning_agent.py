"""
Bio-Reasoning Agent for generating structured multi-aspect biomedical analysis.

This agent receives a target article and retrieved reference articles and 
generates comprehensive biomedical reasoning reports including evidence tables, 
clinical uncertainty, and research recommendations.
"""

import json
import re
from typing import List, Dict, Any, Optional
import numpy as np
import torch
from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM

class BioReasoningAgent:
    """
    Agent for generating structured biomedical reasoning analysis.
    
    Can use:
    1. Local LLM (via transformers) for generative insights.
    2. Rule-based fallback (deterministic) for structured data analysis.
    """
    
    def __init__(
        self,
        model_name: Optional[str] = "gpt2",
        use_llm: bool = False,
        device: Optional[str] = None,
        max_length: int = 2048
    ):
        """
        Initialize the BioReasoningAgent.
        
        Args:
            model_name: Hugging Face model name. Defaults to "gpt2" for fallback.
            use_llm: Whether to use LLM or rule-based reasoning.
            device: Device to run model on ('cuda', 'cpu', or None for auto).
            max_length: Maximum token length for generation.
        """
        self.use_llm = use_llm
        self.max_length = max_length
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
        
        self.model = None
        self.tokenizer = None
        self.generator = None
        
        if use_llm:
            self._initialize_llm(model_name)
    
    def _initialize_llm(self, model_name: str):
        """Initialize the local LLM for reasoning generation."""
        print(f"Initializing Bio-Reasoning LLM: {model_name} on {self.device}...")
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModelForCausalLM.from_pretrained(
                model_name,
                torch_dtype=torch.float16 if self.device == 'cuda' else torch.float32,
                trust_remote_code=True
            ).to(self.device)
            
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            self.generator = pipeline(
                "text-generation",
                model=self.model,
                tokenizer=self.tokenizer,
                device=0 if self.device == 'cuda' else -1,
                max_new_tokens=512,
                temperature=0.7
            )
            print("LLM pipeline ready.")
        except Exception as e:
            print(f"Error loading LLM: {e}. Defaulting to rule-based logic.")
            self.use_llm = False

    def generate_reasoning(
        self,
        target_article: Dict[str, Any],
        retrieved_articles: List[Dict[str, Any]],
        external_coherence_score: float
    ) -> Dict[str, Any]:
        """Main entry point for generating the reasoning report."""
        if self.use_llm and self.generator:
            return self._generate_llm_reasoning(
                target_article, retrieved_articles, external_coherence_score
            )
        return self._generate_rule_based_reasoning(
            target_article, retrieved_articles, external_coherence_score
        )

    # --- LLM REASONING LOGIC ---

    def _generate_llm_reasoning(
        self,
        target: Dict[str, Any],
        references: List[Dict[str, Any]],
        score: float
    ) -> Dict[str, Any]:
        """Orchestrates LLM prompt building and result parsing."""
        prompt = self._build_reasoning_prompt(target, references)
        
        try:
            raw_output = self.generator(prompt)[0]['generated_text']
            # Split to get only the response portion
            response_text = raw_output.split("### RESPONSE:")[-1].strip()
            
            parsed = self._parse_llm_output(response_text)
            parsed["overall_coherence_score"] = float(score)
            parsed["reasoning_method"] = "llm_inference"
            
            # Ensure detailed evidence table exists even in LLM mode
            if "detailed_evidence_table" not in parsed:
                parsed["detailed_evidence_table"] = self._generate_evidence_table(references)
                
            return parsed
        except Exception as e:
            print(f"LLM Reasoning failed: {e}. Falling back...")
            return self._generate_rule_based_reasoning(target, references, score)

    def _build_reasoning_prompt(self, target: Dict[str, Any], references: List[Dict[str, Any]]) -> str:
        """Constructs a biomedical-specific instruction prompt."""
        ref_context = ""
        for i, ref in enumerate(references[:3]):
            ref_context += f"- Reference {i+1} (PMID: {ref.get('article_id')}): {ref.get('title')}. "
            ref_context += f"Findings: {ref.get('text', 'N/A')[:150]}...\n"

        return f"""### INSTRUCTION:
As a clinical research expert, analyze the Target Article against the provided References.
Identify consensus, contradictions, and clinical relevance. 

Output must be a valid JSON object with the following keys:
"summary_long", "aspect_analysis" (list of objects with "aspect" and "analysis"), 
"uncertainty_and_limits", and "recommended_next_steps" (list).

TARGET ARTICLE:
Title: {target.get('title')}
Abstract: {target.get('text', 'N/A')[:400]}

REFERENCES:
{ref_context}

### RESPONSE:
"""

    def _parse_llm_output(self, response: str) -> Dict[str, Any]:
        """Cleans and parses the LLM output into a dictionary."""
        try:
            json_str = re.search(r'\{.*\}', response, re.DOTALL).group()
            return json.loads(json_str)
        except:
            return {
                "summary_long": response[:500],
                "aspect_analysis": [{"aspect": "General", "analysis": "Parsing failed."}],
                "uncertainty_and_limits": "High parsing uncertainty.",
                "recommended_next_steps": ["Review raw LLM output."]
            }

    # --- RULE-BASED FALLBACK LOGIC ---

    def _generate_rule_based_reasoning(
        self,
        target: Dict[str, Any],
        references: List[Dict[str, Any]],
        score: float
    ) -> Dict[str, Any]:
        """Deterministic reasoning based on similarity and alignment."""
        
        confirming = [a for a in references if a.get('alignment_type') == 'confirms']
        contradicting = [a for a in references if a.get('alignment_type') == 'contradicts']
        neutral = [a for a in references if a.get('alignment_type') not in ['confirms', 'contradicts']]
        
        return {
            "summary_long": self._generate_summary_text(target, references, score, len(confirming), len(contradicting), len(neutral)),
            "aspect_analysis": self._generate_aspect_analysis_list(confirming, contradicting),
            "detailed_evidence_table": self._generate_evidence_table(references),
            "uncertainty_and_limits": self._generate_uncertainty_text(score),
            "recommended_next_steps": self._generate_recommendations(score, len(contradicting)),
            "reasoning_method": "rule_based_fallback",
            "overall_coherence_score": float(score)
        }

    def _generate_summary_text(self, target, refs, score, n_conf, n_cont, n_neut) -> str:
        verdict = "strongly supported" if score > 0.7 else "exploratory"
        journal = target.get('journal', 'N/A')
        
        summary = (f"The study '{target.get('title')}' (Journal: {journal}) is considered {verdict} "
                  f"within the current biomedical context. Analysis of {len(refs)} references "
                  f"suggests a coherence score of {score:.2f}. ")
        
        summary += f"Results indicate {n_conf} confirming studies, {n_cont} contradicting studies, and {n_neut} neutral matches."
        return summary

    def _generate_aspect_analysis_list(self, confirming, contradicting) -> List[Dict[str, str]]:
        return [
            {
                "aspect": "Evidence Consensus",
                "analysis": f"Detected {len(confirming)} supporting articles. " + 
                            (f"Key support found in '{confirming[0].get('title')[:50]}...'" if confirming else ""),
                "strength": "high" if len(confirming) >= 3 else "moderate"
            },
            {
                "aspect": "Conflict Density",
                "analysis": f"Identified {len(contradicting)} contradictory findings in retrieved literature.",
                "strength": "low" if len(contradicting) == 0 else "significant"
            }
        ]

    def _generate_evidence_table(self, articles) -> List[Dict[str, Any]]:
        return [{
            "pmid": a.get('article_id', 'N/A'),
            "title": a.get('title', 'N/A')[:70],
            "similarity": round(a.get('similarity_score', 0), 4),
            "alignment": a.get('alignment_type', 'neutral')
        } for a in articles[:5]]

    def _generate_uncertainty_text(self, score) -> str:
        if score < 0.5:
            return "Significant divergence from established literature suggests high uncertainty or high novelty."
        return "Standard biomedical alignment observed with low to moderate uncertainty."

    def _generate_recommendations(self, score, n_cont) -> List[str]:
        recs = ["Conduct further validation studies."]
        if n_cont > 0:
            recs.append("Investigate potential confounding variables causing divergence from prior literature.")
        if score > 0.8:
            recs.append("Consider translation into clinical guidelines or meta-analysis.")
        return recs

# --- DEMO / TEST ---

def demo_bio_reasoning_agent():
    # Mock data incorporating keys from both versions
    target = {
        "article_id": "12345",
        "title": "Impact of Metformin on COVID-19 Severity",
        "text": "Metformin shows promise in reducing inflammatory markers in acute respiratory cases...",
        "journal": "Nature Medicine"
    }
    
    refs = [
        {
            "article_id": "PMID1", 
            "title": "Diabetes and Viral Infections", 
            "similarity_score": 0.82, 
            "alignment_type": "confirms",
            "text": "Prior studies show metformin reduces cytokines."
        },
        {
            "article_id": "PMID2", 
            "title": "Retrospective study of metformin", 
            "similarity_score": 0.61, 
            "alignment_type": "contradicts",
            "text": "No significant difference was found in mortality rates."
        }
    ]
    
    # Testing Rule-Based Fallback
    agent = BioReasoningAgent(use_llm=False)
    report = agent.generate_reasoning(target, refs, 0.71)
    
    print("-" * 30)
    print("BIOMEDICAL REASONING REPORT (Rule-Based)")
    print("-" * 30)
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    demo_bio_reasoning_agent()
