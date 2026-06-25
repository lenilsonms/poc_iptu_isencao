"""Testes do DecisionDraftService (geração determinística da minuta)."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

from poc_iptu.config import ConfigLoader
from poc_iptu.domain import (
    BenefitType,
    ChecklistItemResult,
    ChecklistStatus,
    ConclusionResult,
    ConclusionStatus,
    IncomeAnalysis,
    IncomeStatus,
    PropertyQualification,
    PropertyRelationshipType,
    RequestIdentification,
)
from poc_iptu.domain.pipeline_models import (
    AnalysisMetadata,
    ApplicantQualification,
    ProcessAnalysisResult,
)
from poc_iptu.drafting import DecisionDraftService, DraftGenerationError

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


@pytest.fixture(scope="module")
def service():
    config = ConfigLoader(CONFIG_DIR).load()
    return DecisionDraftService(config.conclusion_mapping)


def _metadata() -> AnalysisMetadata:
    return AnalysisMetadata(
        analysis_id="an-123",
        created_at=datetime(2026, 6, 23, 12, 0, tzinfo=timezone.utc),
        app_version="0.1.0",
        legal_references_version="1.2.0-poc-p0-fixes",
        business_rules_version="1.2.0-poc-p0-fixes",
        checklist_version="1.0.0-poc",
        llm_provider="fake",
        llm_model="fake-golden",
        ocr_engine="noop",
        pii_policy="CPF mascarado.",
    )


def _result(
    status: ConclusionStatus,
    *,
    legal_basis=None,
    missing=None,
    verify=None,
    checklist=None,
    cpf_masked="***.***.***-**",
    generate_merit=True,
) -> ProcessAnalysisResult:
    conclusion = ConclusionResult(
        status=status,
        main_reason="motivo",
        missing_required_documents=missing or [],
        items_to_verify=verify or [],
        legal_basis=legal_basis or [],
        generate_merit_draft=generate_merit,
    )
    return ProcessAnalysisResult(
        process_id="PAT-1",
        file_name="proc.pdf",
        request=RequestIdentification(benefit_type=BenefitType.APOSENTADO, requested_year=2024),
        applicant=ApplicantQualification(name="Fulano de Tal", cpf_masked=cpf_masked),
        property=PropertyQualification(
            registration_number="111.62.26.0166.01.000",
            relationship_type=PropertyRelationshipType.PROPRIETARIO,
        ),
        income=IncomeAnalysis(
            benefit_condition=BenefitType.APOSENTADO,
            benefit_document_found=True,
            income_document_found=True,
            income_status=IncomeStatus.OK,
        ),
        documents=[],
        checklist=checklist or [],
        conclusion=conclusion,
        metadata=_metadata(),
    )


def _golden_indeferimento_result() -> ProcessAnalysisResult:
    checklist = [
        ChecklistItemResult(
            code="COMPROVANTE_RESIDENCIA",
            label="Comprovante de residência",
            required=True,
            status=ChecklistStatus.NAO_APRESENTADO,
        ),
        ChecklistItemResult(
            code="EXTRATO_RENDIMENTO_FONTE_PAGADORA",
            label="Extrato de rendimento da fonte pagadora",
            required=True,
            status=ChecklistStatus.VERIFICAR,
            page=7,
            evidence="documento de renda insuficiente",
            confidence=0.8,
        ),
    ]
    return _result(
        ConclusionStatus.INDEFERIMENTO_SUGERIDO,
        legal_basis=["Decreto nº 34.767/2018, art. 3º", "Decreto nº 34.767/2018, art. 7º"],
        missing=["COMPROVANTE_RESIDENCIA"],
        verify=["EXTRATO_RENDIMENTO_FONTE_PAGADORA", "COMPROVANTE_OUTRAS_RENDAS"],
        checklist=checklist,
    )


def test_minuta_de_merito_tem_todas_as_secoes_na_ordem(service):
    draft = service.generate(_golden_indeferimento_result())
    assert draft.is_merit_draft is True
    codes = [s.code for s in draft.sections]
    assert codes == [
        "RELATORIO",
        "ADMISSIBILIDADE",
        "ANALISE_DOCUMENTAL",
        "CONCLUSAO",
        "CIENCIA_E_RECURSO",
        "RASTREABILIDADE",
    ]
    assert draft.sections[0].title == "I. RELATÓRIO"
    assert draft.sections[4].title == "V. CIÊNCIA E RECURSO"


def test_secao_ciencia_recurso_traz_prazo_e_jrf(service):
    draft = service.generate(_golden_indeferimento_result())
    ciencia = next(s for s in draft.sections if s.code == "CIENCIA_E_RECURSO")
    assert "Junta de Recursos Fiscais" in ciencia.body
    assert "30 dias" in ciencia.body
    assert "5.420/1999" in ciencia.body


def test_conclusao_traz_texto_canonico_e_fundamento(service):
    draft = service.generate(_golden_indeferimento_result())
    conclusao = next(s for s in draft.sections if s.code == "CONCLUSAO")
    assert "INDEFERIMENTO" in conclusao.body
    assert "Decreto nº 34.767/2018, art. 3º" in conclusao.body
    assert "Decreto nº 34.767/2018, art. 7º" in conclusao.body
    assert "COMPROVANTE_RESIDENCIA" in conclusao.body


def test_cpf_mascarado_aparece_no_cabecalho(service):
    draft = service.generate(_golden_indeferimento_result())
    assert "***.***.***-**" in draft.text


def test_rejeita_cpf_nao_mascarado(service):
    result = _result(ConclusionStatus.INDEFERIMENTO_SUGERIDO, cpf_masked="123.456.789-00")
    with pytest.raises(DraftGenerationError):
        service.generate(result)


def test_apto_nunca_escreve_defiro(service):
    draft = service.generate(_result(ConclusionStatus.APTO_PARA_ANALISE_DE_DEFERIMENTO))
    assert re.search(r"\bDEFIRO\b", draft.text) is None
    assert "apto à análise de deferimento" in draft.text.lower()


def test_fora_do_escopo_gera_aviso_curto_sem_secoes(service):
    draft = service.generate(
        _result(ConclusionStatus.FORA_DO_ESCOPO_POC, generate_merit=False)
    )
    assert draft.is_merit_draft is False
    assert draft.sections == []
    assert "fora do escopo" in draft.text.lower()
    # Sem mérito: não há seção de ciência/recurso.
    assert "CIÊNCIA E RECURSO" not in draft.text


def test_pagina_sem_evidencia_nao_e_citada(service):
    # Item com página mas SEM evidência: a minuta não pode citar a página.
    checklist = [
        ChecklistItemResult(
            code="DOCUMENTO_IMOVEL",
            label="Documento do imóvel",
            required=True,
            status=ChecklistStatus.OK,
            page=5,
            evidence=None,
        )
    ]
    draft = service.generate(
        _result(ConclusionStatus.VERIFICAR_MANUALMENTE, checklist=checklist)
    )
    assert "página 5" not in draft.text
