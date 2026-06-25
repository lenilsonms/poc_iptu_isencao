"""Portas (interfaces) do caso de uso. Adapters concretos as implementam."""
from .document_classification import DocumentClassificationPort
from .document_reader import DocumentReaderPort
from .field_extraction import FieldExtractionPort
from .ocr import OcrPort

__all__ = [
    "DocumentReaderPort",
    "OcrPort",
    "DocumentClassificationPort",
    "FieldExtractionPort",
]
