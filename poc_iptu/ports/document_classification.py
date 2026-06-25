"""Porta de classificação documental (LLM)."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..domain.pipeline_models import ClassifiedDocument, ExtractedDocument


class DocumentClassificationPort(ABC):
    """Classifica os documentos contidos no PDF, com evidência ancorada."""

    @abstractmethod
    def classify(self, document: ExtractedDocument) -> list[ClassifiedDocument]:
        raise NotImplementedError
