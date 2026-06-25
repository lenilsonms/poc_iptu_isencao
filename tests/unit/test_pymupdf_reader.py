"""Testes do leitor de PDF (PyMuPDF) e do acionamento seletivo de OCR."""

from __future__ import annotations

from poc_iptu.adapters import PyMuPdfDocumentReader
from poc_iptu.adapters.ocr import NoOpOcr
from poc_iptu.domain import PageSource
from poc_iptu.ports.ocr import OcrPort
from tests.fakes.pdf_factory import (
    build_pdf_text_then_imageonly,
    build_pdf_with_text_pages,
)


class SpyOcr(OcrPort):
    """OCR de teste: registra as chamadas e devolve um texto conhecido."""

    def __init__(self, canned_text: str = "TEXTO RECONHECIDO VIA OCR") -> None:
        self.calls = 0
        self._canned_text = canned_text

    @property
    def engine_name(self) -> str:
        return "spy"

    def extract_text(self, page_image_png: bytes) -> str:
        self.calls += 1
        assert page_image_png[:4] == b"\x89PNG", "OCR deve receber um PNG válido."
        return self._canned_text


def test_le_paginas_textuais_sem_acionar_ocr():
    pdf = build_pdf_with_text_pages(["Pedido inicial de isenção", "Documentos do imóvel"])
    ocr = SpyOcr()
    reader = PyMuPdfDocumentReader(ocr)

    document = reader.read(pdf, file_name="processo.pdf")

    assert document.file_name == "processo.pdf"
    assert len(document.pages) == 2
    assert all(p.source == PageSource.PDF_TEXT for p in document.pages)
    assert "Pedido inicial" in document.pages[0].text
    assert ocr.calls == 0  # nenhuma página exigiu OCR
    assert document.ocr_page_count == 0


def test_aciona_ocr_em_pagina_sem_texto_util():
    pdf = build_pdf_text_then_imageonly("Página textual com conteúdo")
    ocr = SpyOcr(canned_text="CONTEUDO DA PAGINA ESCANEADA")
    reader = PyMuPdfDocumentReader(ocr)

    document = reader.read(pdf)

    assert len(document.pages) == 2
    # Página 1: texto direto. Página 2: sem texto -> OCR.
    assert document.pages[0].source == PageSource.PDF_TEXT
    assert document.pages[1].source == PageSource.OCR
    assert document.pages[1].text == "CONTEUDO DA PAGINA ESCANEADA"
    assert ocr.calls == 1
    assert document.ocr_page_count == 1


def test_ocr_noop_mantem_pipeline_funcional():
    pdf = build_pdf_text_then_imageonly("Página textual")
    reader = PyMuPdfDocumentReader(NoOpOcr())

    document = reader.read(pdf)

    # Sem OCR real, a página escaneada fica com texto vazio, mas o pipeline não quebra.
    assert document.pages[1].source == PageSource.OCR
    assert document.pages[1].text == ""


def test_le_a_partir_de_caminho_em_disco(tmp_path):
    pdf_path = tmp_path / "processo_em_disco.pdf"
    pdf_path.write_bytes(build_pdf_with_text_pages(["Conteúdo"]))
    reader = PyMuPdfDocumentReader(NoOpOcr())

    document = reader.read(pdf_path)

    assert document.file_name == "processo_em_disco.pdf"
    assert "Conteúdo" in document.pages[0].text
