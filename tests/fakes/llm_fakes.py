"""Fakes de LLM para teste do caso de uso.

Reutilizam os adapters de demonstração offline (fonte única dos dados do caso-ouro),
evitando duplicação.
"""
from __future__ import annotations

from poc_iptu.adapters.llm import OfflineDemoClassification, OfflineDemoExtraction


class FakeGoldenCaseClassification(OfflineDemoClassification):
    """Alias semântico para uso nos testes."""


class FakeGoldenCaseExtraction(OfflineDemoExtraction):
    """Alias semântico para uso nos testes."""
