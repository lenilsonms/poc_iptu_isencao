"""Portas (interfaces) do caso de uso. Adapters concretos as implementam."""
from .document_classification import DocumentClassificationPort
from .document_reader import DocumentReaderPort
from .field_extraction import FieldExtractionPort
from .ocr import OcrPort
from .decision_drafting import DecisionDraftingPort

__all__ = [
    "DocumentReaderPort",
    "OcrPort",
    "DocumentClassificationPort",
    "FieldExtractionPort",
    "DecisionDraftingPort",
]
