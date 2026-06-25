"""Testes dos adapters Azure de LLM com cliente de chat falso.

Validam a montagem do prompt, o parsing do JSON e o mapeamento para o domínio — e o pipeline
completo do caso de uso usando o caminho Azure (com transporte falso), reproduzindo o caso-ouro.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from poc_iptu.adapters import PyMuPdfDocumentReader
from poc_iptu.adapters.llm import (
    AzureDocumentClassification,
    AzureFieldExtraction,
    PromptLibrary,
    load_allowed_document_types,
)
from poc_iptu.adapters.llm.serialization import LlmResponseError
from poc_iptu.adapters.ocr import NoOpOcr
from poc_iptu.application import AnalyzeProcessRequest, build_analyze_process_use_case
from poc_iptu.domain import (
    BenefitType,
    ConclusionStatus,
    ExtractedDocument,
    ExtractedPage,
    IncomeStatus,
    PageSource,
    PropertyRelationshipType,
)
from tests.fakes.chat_fakes import ScriptedChatClient
from tests.fakes.pdf_factory import build_pdf_with_text_pages

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"

_CLASSIFICATION_JSON = json.dumps(
    {
        "documents": [
            {"document_type": "RG", "page_start": 3, "page_end": 3, "evidence": "RG do requerente", "confidence": 0.98},
            {"document_type": "MATRICULA_IMOVEL", "page_start": 5, "page_end": 5, "evidence": "Matrícula", "confidence": 0.93},
            {"document_type": "CARTA_CONCESSAO_BENEFICIO", "page_start": 7, "page_end": 7, "evidence": "Carta INSS", "confidence": 0.95},
            {"document_type": "DECLARACAO_ISENTO_IRPF", "page_start": 13, "page_end": 13, "evidence": "Isento IRPF", "confidence": 0.9},
            {"document_type": "DECLARACAO_OCUPACAO_IMOVEIS", "page_start": 14, "page_end": 14, "evidence": "Ocupação", "confidence": 0.92},
            {"document_type": "CARNE_IPTU", "page_start": 15, "page_end": 15, "evidence": "Carnê IPTU", "confidence": 0.94},
            {"document_type": "JUCESP_FICHA_CADASTRAL", "page_start": 11, "page_end": 11, "evidence": "JUCESP", "confidence": 0.88},
            {"document_type": "TIPO_INEXISTENTE_NA_TAXONOMIA", "page_start": 99, "page_end": 99, "evidence": "x", "confidence": 0.99},
        ]
    },
    ensure_ascii=False,
)

_EXTRACTION_JSON = json.dumps(
    {
        "request": {"benefit_type": "APOSENTADO", "requested_year": 2024, "explicit_decree_mention": "Decreto nº 34.767/2018", "page": 1},
        "applicant": {"name": "MIGUEL ANGEL CAMACHO VISCARRA", "cpf_masked": "***.***.***-**", "estado_civil": None, "process_indicates_spouse_or_partner": False, "has_representative": False, "has_civil_incapacity": False, "has_disability_requiring_legal_representative": False},
        "property": {"registration_number": "111.62.26.0166.01.000", "relationship_type": "PROPRIETARIO", "multiple_inscriptions_detected": True, "residence_confirmed": False},
        "income": {"benefit_condition": "APOSENTADO", "benefit_document_found": True, "income_document_found": False, "other_sources_flag": "JUCESP_MEI", "income_status": "VERIFICAR"},
    },
    ensure_ascii=False,
)


@pytest.fixture(scope="module")
def prompts():
    return PromptLibrary.from_yaml(CONFIG_DIR / "prompts.yaml")


def _doc() -> ExtractedDocument:
    return ExtractedDocument(
        file_name="proc.pdf",
        pages=[ExtractedPage(page_number=1, text="conteúdo", source=PageSource.PDF_TEXT)],
    )


def test_classificacao_parseia_e_descarta_tipo_fora_da_taxonomia(prompts):
    client = ScriptedChatClient(_CLASSIFICATION_JSON)
    adapter = AzureDocumentClassification(client, prompts, load_allowed_document_types(CONFIG_DIR))

    docs = adapter.classify(_doc())

    tipos = [d.document_type for d in docs]
    assert "RG" in tipos
    assert "JUCESP_FICHA_CADASTRAL" in tipos
    assert "TIPO_INEXISTENTE_NA_TAXONOMIA" not in tipos  # guardrail
    assert client.calls == 1
    # O prompt levou os tipos permitidos e as páginas.
    assert "RG" in client.last_user


def test_extracao_parseia_e_mapeia_para_dominio(prompts):
    client = ScriptedChatClient(_EXTRACTION_JSON)
    adapter = AzureFieldExtraction(client, prompts)

    fields = adapter.extract(_doc(), [])

    assert fields.request.benefit_type == BenefitType.APOSENTADO
    assert fields.request.explicit_decree_mention == "Decreto nº 34.767/2018"
    assert fields.property.relationship_type == PropertyRelationshipType.PROPRIETARIO
    assert fields.property.multiple_inscriptions_detected is True
    assert fields.income.income_status == IncomeStatus.VERIFICAR
    assert fields.applicant.cpf_masked == "***.***.***-**"


def test_extracao_rejeita_json_invalido(prompts):
    adapter = AzureFieldExtraction(ScriptedChatClient("isto não é json"), prompts)
    with pytest.raises(LlmResponseError):
        adapter.extract(_doc(), [])


def test_pipeline_completo_via_caminho_azure_reproduz_caso_ouro(prompts):
    """Caso de uso ponta a ponta usando os adapters Azure com transporte falso."""
    ocr = NoOpOcr()
    use_case = build_analyze_process_use_case(
        config_dir=CONFIG_DIR,
        document_reader=PyMuPdfDocumentReader(ocr),
        classifier=AzureDocumentClassification(
            ScriptedChatClient(_CLASSIFICATION_JSON), prompts, load_allowed_document_types(CONFIG_DIR)
        ),
        field_extractor=AzureFieldExtraction(ScriptedChatClient(_EXTRACTION_JSON), prompts),
        ocr=ocr,
        llm_provider="azure-openai",
        llm_model="azure-openai:gpt-4o",
        prompt_version=prompts.version,
    )
    pdf = build_pdf_with_text_pages(["Pedido", "RG", "Matrícula"])
    result = use_case.execute(AnalyzeProcessRequest(source=pdf, file_name="x.pdf", process_id="P-1"))

    assert result.conclusion.status == ConclusionStatus.INDEFERIMENTO_SUGERIDO
    assert result.conclusion.missing_required_documents == ["COMPROVANTE_RESIDENCIA"]
    assert any("34.767" in b for b in result.conclusion.legal_basis)
    assert result.metadata.prompt_version == "1.0.0-poc"
    assert result.metadata.llm_provider == "azure-openai"
    # Minuta gerada de ponta a ponta.
    assert "DECISÃO ADMINISTRATIVA" in (result.draft_text or "")
