"""Geração de PDFs sintéticos para testes do leitor.

Cria PDFs em memória com PyMuPDF: páginas textuais (extração direta) e páginas sem texto
(que disparam o caminho de OCR no leitor). Evita depender de arquivos binários no repositório.
"""

from __future__ import annotations

import fitz


def build_pdf_with_text_pages(texts: list[str]) -> bytes:
    """PDF com uma página textual por item de `texts`."""
    document = fitz.open()
    try:
        for text in texts:
            page = document.new_page()
            page.insert_text((72, 72), text, fontsize=12)
        return document.tobytes()
    finally:
        document.close()


def build_pdf_text_then_imageonly(text_first_page: str) -> bytes:
    """PDF com 1 página textual seguida de 1 página SEM texto (dispara OCR no leitor)."""
    document = fitz.open()
    try:
        first = document.new_page()
        first.insert_text((72, 72), text_first_page, fontsize=12)
        # Segunda página: apenas um retângulo desenhado, sem nenhuma camada de texto.
        second = document.new_page()
        second.draw_rect(fitz.Rect(72, 72, 300, 200), fill=(0.9, 0.9, 0.9))
        return document.tobytes()
    finally:
        document.close()
