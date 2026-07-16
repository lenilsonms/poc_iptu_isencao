"""Porta de geração de minuta de decisão.

Contrato para transformar um ProcessAnalysisResult em uma DecisionDraft revisável.
Implementações: DecisionDraftService (determinística) e LlmDecisionDraftService (LLM
com guardrails e fallback determinístico).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..domain.pipeline_models import DecisionDraft, ProcessAnalysisResult


class DecisionDraftingPort(ABC):
    """Gera a minuta de decisão administrativa de 1ª instância (sempre revisável)."""

    @abstractmethod
    def generate(self, result: ProcessAnalysisResult) -> DecisionDraft:
        raise NotImplementedError