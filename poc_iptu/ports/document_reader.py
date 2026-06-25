"""Porta de leitura de documento.

Contrato para transformar a fonte (bytes ou caminho do PDF) em um `ExtractedDocument`
consolidado por página. A implementação concreta (PyMuPDF) decide quando acionar OCR.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ..domain.pipeline_models import ExtractedDocument


class DocumentReaderPort(ABC):
    """Lê um PDF e devolve suas páginas com texto e origem (PDF_TEXT/OCR)."""

    @abstractmethod
    def read(self, source: bytes | str | Path, file_name: str | None = None) -> ExtractedDocument:
        """Lê o documento da fonte informada.

        Args:
            source: bytes do PDF ou caminho para o arquivo.
            file_name: nome lógico do arquivo (para rastreabilidade); inferido do caminho se ausente.
        """
        raise NotImplementedError
