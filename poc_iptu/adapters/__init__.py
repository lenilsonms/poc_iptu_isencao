"""Adapters concretos das portas (PDF, OCR, e futuramente LLM)."""
from .pymupdf_reader import DocumentReadError, PyMuPdfDocumentReader

__all__ = ["PyMuPdfDocumentReader", "DocumentReadError"]
