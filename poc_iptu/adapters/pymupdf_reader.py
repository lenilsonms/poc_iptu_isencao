"""Adapter de leitura de PDF com PyMuPDF (fitz).

Estratégia (requisito: 'OCR apenas em páginas sem texto útil'):
  - extrai texto de cada página com PyMuPDF;
  - se o texto for útil (comprimento >= limiar), marca a página como PDF_TEXT;
  - caso contrário, rasteriza a página em PNG e delega ao OcrPort, marcando-a como OCR.

O adapter NÃO conhece o motor de OCR concreto — depende apenas do OcrPort (inversão de
dependência). Falhas de leitura viram DocumentReadError com contexto acionável.
"""

from __future__ import annotations

from pathlib import Path
import logging
import fitz  # PyMuPDF

from ..domain.errors import PocIptuError
from ..domain.pipeline_models import ExtractedDocument, ExtractedPage, PageSource
from ..ports.document_reader import DocumentReaderPort
from ..ports.ocr import OcrPort
import os
from pathlib import Path
# DPI de rasterização para OCR. 200 equilibra qualidade de reconhecimento e custo.
_OCR_RENDER_DPI = 200
logger = logging.getLogger(__name__)

class DocumentReadError(PocIptuError):
    """Falha ao abrir ou ler o PDF."""


class PyMuPdfDocumentReader(DocumentReaderPort):
    """Leitor de PDF baseado em PyMuPDF, com fallback de OCR por página."""

    def __init__(self, ocr: OcrPort, min_useful_text_length: int = 100) -> None:
        """
        Args:
            ocr: motor de OCR para páginas sem texto útil.
            min_useful_text_length: número mínimo de caracteres não-brancos para considerar
                o texto da página 'útil' e dispensar OCR.
        """
        self._ocr = ocr
        self._min_useful_text_length = max(0, min_useful_text_length)

    def read(
        self, source: bytes | str | Path, file_name: str | None = None
    ) -> ExtractedDocument:
        resolved_name = self._resolve_file_name(source, file_name)
        document = self._open(source)
        try:
            pages = [self._read_page(document, index) for index in range(document.page_count)]
        finally:
            document.close()
        return ExtractedDocument(file_name=resolved_name, pages=pages)

    # ----------------------------------------------------------------- helpers

    @staticmethod
    def _resolve_file_name(source: bytes | str | Path, file_name: str | None) -> str:
        if file_name:
            return file_name
        if isinstance(source, (str, Path)):
            return Path(source).name
        return "documento.pdf"

    @staticmethod
    def _open(source: bytes | str | Path) -> fitz.Document:
        try:
            if isinstance(source, bytes):
                return fitz.open(stream=source, filetype="pdf")
            return fitz.open(str(source))
        except Exception as exc:  # erro de I/O / arquivo corrompido
            raise DocumentReadError(f"Não foi possível abrir o PDF: {exc}") from exc

    def _read_page(self, document: fitz.Document, index: int) -> ExtractedPage:
        page = document.load_page(index)
        text = page.get_text("text") or ""
        page_number = index + 1

        if self._is_useful_text(text):
            return ExtractedPage(
                page_number=page_number, text=text.strip(), source=PageSource.PDF_TEXT
            )

        ocr_text = self._ocr_page(page)
        logger.info(
            "OCR página=%s pdf_chars=%s ocr_chars=%s ocr_preview=%r",
            page_number,
            len(text or ""),
            len(ocr_text or ""),
            (ocr_text or "")[:300].replace("\n", " "),
        )
        combined_text = self._combine_pdf_text_and_ocr_text(
            pdf_text=text,
            ocr_text=ocr_text,
        )

        self._dump_debug_text(
            page_number=page_number,
            pdf_text=text,
            ocr_text=ocr_text,
            combined_text=combined_text,
        )
        
        return ExtractedPage(
            page_number=page_number,
            text=combined_text.strip(),
            source=PageSource.OCR,
        )

    def _is_useful_text(self, text: str) -> bool:
        return len(text.strip()) >= self._min_useful_text_length

    @staticmethod
    def _combine_pdf_text_and_ocr_text(pdf_text: str, ocr_text: str) -> str:
        pdf_text = (pdf_text or "").strip()
        ocr_text = (ocr_text or "").strip()

        if pdf_text and ocr_text:
            return f"{pdf_text}\n\n[OCR]\n{ocr_text}"

        return ocr_text or pdf_text
    
    def _ocr_page(self, page: fitz.Page) -> str:
        try:
            pixmap = page.get_pixmap(dpi=_OCR_RENDER_DPI)
            png_bytes = pixmap.tobytes("png")
        except Exception as exc:  # pragma: no cover - falha de rasterização
            raise DocumentReadError(
                f"Falha ao rasterizar a página {page.number + 1} para OCR: {exc}"
            ) from exc
        return self._ocr.extract_text(png_bytes)


    def _dump_debug_text(
        self,
        page_number: int,
        pdf_text: str,
        ocr_text: str,
        combined_text: str,
    ) -> None:
        if os.getenv("POC_DEBUG_OCR_TEXT", "false").lower() not in {"1", "true", "yes", "sim"}:
            return

        output_dir = Path(os.getenv("POC_DEBUG_OCR_DIR", "/tmp/poc_iptu_ocr_debug"))
        output_dir.mkdir(parents=True, exist_ok=True)

        page_label = f"page_{page_number:03d}"

        (output_dir / f"{page_label}_pdf_text.txt").write_text(
            pdf_text or "",
            encoding="utf-8",
        )

        (output_dir / f"{page_label}_ocr_text.txt").write_text(
            ocr_text or "",
            encoding="utf-8",
        )

        (output_dir / f"{page_label}_combined_text.txt").write_text(
            combined_text or "",
            encoding="utf-8",
        )