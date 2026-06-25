"""Adapter de OCR com PaddleOCR.

PaddleOCR é uma dependência pesada (instalar com `pip install paddleocr`). Por isso o import
é PREGUIÇOSO: a classe pode ser referenciada e injetada sem PaddleOCR instalado; o erro só
ocorre — com mensagem clara — se o OCR for de fato acionado sem a biblioteca disponível.

Alternativa de produção: um adapter equivalente para Azure Document Intelligence pode
implementar o mesmo OcrPort e ser injetado no lugar deste, sem alterar o leitor de PDF.
"""

from __future__ import annotations

from ...domain.errors import PocIptuError
from ...ports.ocr import OcrPort


class OcrEngineUnavailableError(PocIptuError):
    """PaddleOCR não está instalado/disponível no ambiente."""


class PaddleOcr(OcrPort):
    """OCR baseado em PaddleOCR, inicializado sob demanda."""

    def __init__(self, lang: str = "pt") -> None:
        self._lang = lang
        self._engine = None  # inicialização preguiçosa

    @property
    def engine_name(self) -> str:
        return f"paddleocr:{self._lang}"

    def extract_text(self, page_image_png: bytes) -> str:
        engine = self._get_engine()
        result = engine.ocr(page_image_png)
        return self._join_recognized_text(result)

    # ----------------------------------------------------------------- helpers

    def _get_engine(self):
        if self._engine is None:
            try:
                from paddleocr import PaddleOCR  # import preguiçoso
            except ImportError as exc:
                raise OcrEngineUnavailableError(
                    "PaddleOCR não está instalado. Instale com 'pip install paddleocr' "
                    "ou injete outro OcrPort (ex.: Azure Document Intelligence)."
                ) from exc
            self._engine = PaddleOCR(use_angle_cls=True, lang=self._lang)
        return self._engine

    @staticmethod
    def _join_recognized_text(ocr_result) -> str:
        """Concatena o texto reconhecido pelo PaddleOCR, tolerando formatos de retorno."""
        if not ocr_result:
            return ""
        lines: list[str] = []
        for page in ocr_result:
            if not page:
                continue
            for entry in page:
                # entry tipicamente: [bbox, (texto, confiança)]
                try:
                    text = entry[1][0]
                except (IndexError, TypeError):
                    continue
                if text:
                    lines.append(str(text))
        return "\n".join(lines)
