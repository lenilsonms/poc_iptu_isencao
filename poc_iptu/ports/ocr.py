"""Porta de OCR.

Contrato mínimo para reconhecer texto a partir da imagem de uma página (PNG em bytes).
Implementações: PaddleOCR (primária) e, como alternativa, Azure Document Intelligence.
Para páginas que já têm texto útil, o OCR não é acionado.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class OcrPort(ABC):
    """Reconhece texto a partir da imagem de uma página."""

    @property
    @abstractmethod
    def engine_name(self) -> str:
        """Identificador do motor de OCR, registrado nos metadados de auditoria."""
        raise NotImplementedError

    @abstractmethod
    def extract_text(self, page_image_png: bytes) -> str:
        """Extrai texto da imagem (PNG). Deve retornar string vazia quando nada for reconhecido."""
        raise NotImplementedError
