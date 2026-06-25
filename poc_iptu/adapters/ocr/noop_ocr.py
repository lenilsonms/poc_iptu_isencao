"""OCR no-op.

Implementação trivial do OcrPort que não reconhece texto. Útil quando o ambiente não tem
OCR configurado ou quando o PDF é integralmente textual. Mantém o pipeline funcional sem
exigir dependências pesadas.
"""

from __future__ import annotations

from ...ports.ocr import OcrPort


class NoOpOcr(OcrPort):
    """Não executa OCR; retorna sempre string vazia."""

    @property
    def engine_name(self) -> str:
        return "noop"

    def extract_text(self, page_image_png: bytes) -> str:
        return ""
