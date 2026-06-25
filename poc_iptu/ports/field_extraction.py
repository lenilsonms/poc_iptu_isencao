"""Porta de extração de campos (LLM)."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..domain.pipeline_models import (
    ClassifiedDocument,
    ExtractedDocument,
    ExtractedFields,
)


class FieldExtractionPort(ABC):
    """Extrai os campos estruturados do processo a partir das páginas e da classificação."""

    @abstractmethod
    def extract(
        self,
        document: ExtractedDocument,
        classified_documents: list[ClassifiedDocument],
    ) -> ExtractedFields:
        raise NotImplementedError
