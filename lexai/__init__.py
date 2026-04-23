"""LexAI — Legal Document Intelligence System."""

__version__ = "0.2.0"
__author__  = "CiteAI Team"

from .agents.base_agent import BaseExternalAgent
from .agents.external_inference_agent import ExternalInferenceAgent
from .agents.inlegalbert_external_agent import InLegalBERTExternalAgent
from .agents.biobert_external_agent import BioBERTExternalAgent
from .agents.legal_reasoning_agent import LegalReasoningAgent

__all__ = [
    "BaseExternalAgent",
    "ExternalInferenceAgent",
    "InLegalBERTExternalAgent",
    "BioBERTExternalAgent",
    "LegalReasoningAgent",
]
