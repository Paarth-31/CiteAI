"""Agents module for CiteAI / LexAI system."""

from .base_agent import BaseExternalAgent
from .external_inference_agent import ExternalInferenceAgent
from .inlegalbert_external_agent import InLegalBERTExternalAgent
from .biobert_external_agent import BioBERTExternalAgent
from .legal_reasoning_agent import LegalReasoningAgent

__all__ = [
    "BaseExternalAgent",
    "ExternalInferenceAgent",
    "InLegalBERTExternalAgent",
    "BioBERTExternalAgent",
    "LegalReasoningAgent",
]
