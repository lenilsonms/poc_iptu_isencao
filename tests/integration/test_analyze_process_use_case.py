"""Teste de integração do AnalyzeProcessUseCase (PDF real -> conclusão).

Exercita o fluxo de entrada completo com adapters REAIS de leitura (PyMuPDF) e montagem de
checklist + núcleo determinístico, fakeando apenas as etapas de LLM (classificação/extração).
Verifica que a saída reproduz o caso-ouro, agora a partir de um PDF de verdade.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from poc_iptu.adapters import PyMuPdfDocumentReader
from poc_iptu.adapters.ocr import NoOpOcr
from poc_iptu.application import AnalyzeProcessRequest, build_analyze_process_use_case
from poc_iptu.domain import ChecklistStatus, ConclusionStatus
from tests.fakes.llm_fakes import FakeGoldenCaseClassification, FakeGoldenCaseExtraction
from tests.fakes.pdf_factory import build_pdf_with_text_pages

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


@pytest.fixture(scope="module")
def result():
    pdf = build_pdf_with_text_pages(
        [
            "PEDIDO INICIAL — Isenção de IPTU exercício 2024 — Decreto nº 34.767/2018",
            "RG do requerente",
            "Matrícula do imóvel",
            "Carta de concessão de aposentadoria",
            "Ficha cadastral JUCESP",
        ]
    )
    ocr = NoOpOcr()
    use_case = build_analyze_process_use_case(
        config_dir=CONFIG_DIR,
        document_reader=PyMuPdfDocumentReader(ocr),
        classifier=FakeGoldenCaseClassification(),
        field_extractor=FakeGoldenCaseExtraction(),
        ocr=ocr,
        llm_provider="fake",
        llm_model="fake-golden",
    )
    request = AnalyzeProcessRequest(source=pdf, file_name="SEI_5737.pdf", process_id="SEI-5737")
    return use_case.execute(request)


def test_pdf_foi_lido(result):
    assert result.file_name == "SEI_5737.pdf"
    assert result.total_page_count == 5
    assert result.ocr_page_count == 0


def test_conclusao_reproduz_o_caso_ouro(result):
    assert result.conclusion.status == ConclusionStatus.INDEFERIMENTO_SUGERIDO


def test_checklist_derivado_bate_com_o_gabarito(result):
    by_code = {item.code: item for item in result.checklist}
    assert by_code["COMPROVANTE_RESIDENCIA"].status == ChecklistStatus.NAO_APRESENTADO
    assert by_code["EXTRATO_RENDIMENTO_FONTE_PAGADORA"].status == ChecklistStatus.VERIFICAR
    assert by_code["COMPROVANTE_OUTRAS_RENDAS"].status == ChecklistStatus.VERIFICAR
    # Demais obrigatórios satisfeitos -> o único ausente é a residência.
    assert result.conclusion.missing_required_documents == ["COMPROVANTE_RESIDENCIA"]


def test_fundamento_cita_decreto_34767_e_nao_42621(result):
    basis = result.conclusion.legal_basis
    assert any("34.767" in b for b in basis), basis
    assert any("art. 3º" in b for b in basis), basis
    assert any("art. 7º" in b for b in basis), basis
    assert all("42.621" not in b for b in basis), basis


def test_metadados_de_auditoria_preenchidos(result):
    meta = result.metadata
    assert meta.legal_references_version == "1.2.0-poc-p0-fixes"
    assert meta.business_rules_version == "1.2.0-poc-p0-fixes"
    assert meta.checklist_version == "1.0.0-poc"
    assert meta.ocr_engine == "noop"
    assert meta.source_page_semantics == "PDF_PAGE"
    assert meta.llm_provider == "fake"


def test_minuta_gerada_e_contem_secoes_obrigatorias(result):
    # A minuta agora é gerada pelo DecisionDraftService no fluxo do caso de uso.
    minuta = result.draft_text
    assert minuta is not None
    assert "DECISÃO ADMINISTRATIVA DE 1ª INSTÂNCIA" in minuta
    for titulo in ("RELATÓRIO", "ADMISSIBILIDADE", "CONCLUSÃO SUGERIDA", "CIÊNCIA E RECURSO", "RASTREABILIDADE"):
        assert titulo in minuta, titulo
    # Ciência/recurso com o prazo e a JRF.
    assert "Junta de Recursos Fiscais" in minuta
    assert "30 dias" in minuta
    # Fundamento correto e CPF mascarado no corpo da minuta.
    assert "Decreto nº 34.767/2018" in minuta
    assert "***.***.***-**" in minuta
    # Guardrail: nunca "DEFIRO".
    import re
    assert re.search(r"\bDEFIRO\b", minuta) is None


def test_cpf_circula_mascarado(result):
    assert result.applicant.cpf_masked == "***.***.***-**"
