"""Adapters de OCR."""
from .noop_ocr import NoOpOcr
from .paddle_ocr import OcrEngineUnavailableError, PaddleOcr

__all__ = ["NoOpOcr", "PaddleOcr", "OcrEngineUnavailableError"]
